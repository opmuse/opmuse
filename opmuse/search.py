# Copyright 2012-2014 Mattias Fliesberg
#
# This file is part of opmuse.
#
# opmuse is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# opmuse is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with opmuse.  If not, see <http://www.gnu.org/licenses/>.

import os
import cherrypy
from cherrypy.process.plugins import Monitor
import whoosh.index
import whoosh.fields
from whoosh.writing import IndexingError
from whoosh.analysis import (RegexTokenizer, SpaceSeparatedTokenizer,
                             LowercaseFilter, StemFilter, DoubleMetaphoneFilter, IDTokenizer)
from whoosh.qparser import QueryParser
from whoosh.query import Term, Or
from opmuse.database import get_database
import opmuse.library
from opmuse.utils import memoize

index_names = ['Artist', 'Album', 'Track']
write_handlers = {}

for index_name in index_names:
    write_handlers[index_name] = None


def log(msg):
    cherrypy.log(msg, context='search')


class SearchError(Exception):
    pass


class WriteHandler:
    def __init__(self, name, index):
        self.name = name
        self.index = index
        self._deletes = []
        self._updates = {}

        self.stopped = False

    def delete_document(self, id):
        if self.stopped:
            raise SearchError("We're stopped, not accepting any more deletes")

        self._deletes.append(id)

    def update_document(self, id, name, slug, filename=None):
        if self.stopped:
            raise SearchError("We're stopped, not accepting any more updates")

        self._updates[id] = (name, slug, filename)

    def commit(self):
        updates = deletes = 0

        with self.index.writer() as writer:
            while len(self._updates) > 0:
                id, values = self._updates.popitem()
                name, slug, filename = values

                writer.add_document(
                    id=id, name=name, stemmed_name=name, metaphone_name=name,
                    exact_name=name, exact_metaphone_name=name,
                    filename=filename,
                    slug=slug
                )
                updates += 1

            while len(self._deletes) > 0:
                id = self._deletes.pop()

                try:
                    writer.delete_document(id)
                except IndexingError as e:
                    log("Error while deleting %d in %s (%s)." % (id, self.name, e))
                    continue

                deletes += 1

        if updates > 0 or deletes > 0:
            log("in %s: %d updates and %d deletes." % (self.name, updates, deletes))


class Search:

    @property
    def index_dir(self):
        cache_path = cherrypy.config['opmuse'].get('cache.path')
        return os.path.join(cache_path, 'index')

    def delete_track(self, track):
        write_handler = write_handlers["Track"]

        if write_handler is None:
            log("Write handler for Track isn't initialized")
            return

        write_handler.delete_document(track.id)

    def delete_album(self, album):
        write_handler = write_handlers["Album"]

        if write_handler is None:
            log("Write handler for Album isn't initialized")
            return

        write_handler.delete_document(album.id)

    def delete_artist(self, artist):
        write_handler = write_handlers["Artist"]

        if write_handler is None:
            log("Write handler for Artist isn't initialized")
            return

        write_handler.delete_document(artist.id)

    def add_track(self, track):
        write_handler = write_handlers["Track"]

        if write_handler is None:
            log("Write handler for Track isn't initialized")
            return

        filename = ""

        for path in track.paths:
            name = os.path.splitext(path.filename)[0]
            filename = "%s %s" % (filename, name)

        write_handler.update_document(str(track.id), name=track.name, slug=track.slug, filename=filename)

    def add_album(self, album):
        write_handler = write_handlers["Album"]

        if write_handler is None:
            log("Write handler for Album isn't initialized")
            return

        write_handler.update_document(str(album.id), name=album.name, slug=album.slug)

    def add_artist(self, artist):
        write_handler = write_handlers["Artist"]

        if write_handler is None:
            log("Write handler for Artist isn't initialized")
            return

        write_handler.update_document(str(artist.id), name=artist.name, slug=artist.slug)

    def get_results_track(self, query, exact=False, exact_metaphone=False):
        return self._query("Track", query, exact, exact_metaphone)

    def get_results_album(self, query, exact=False, exact_metaphone=False):
        return self._query("Album", query, exact, exact_metaphone)

    def get_results_artist(self, query, exact=False, exact_metaphone=False):
        return self._query("Artist", query, exact, exact_metaphone)

    def query_track(self, query, exact=False, exact_metaphone=False):
        results = self.get_results_track(query, exact, exact_metaphone)
        return self._fetch_by_keys(opmuse.library.Track, results)

    def query_album(self, query, exact=False, exact_metaphone=False):
        results = self.get_results_album(query, exact, exact_metaphone)
        return self._fetch_by_keys(opmuse.library.Album, results)

    def query_artist(self, query, exact=False, exact_metaphone=False):
        results = self.get_results_artist(query, exact, exact_metaphone)
        return self._fetch_by_keys(opmuse.library.Artist, results)

    def _fetch_by_keys(self, entity, results):
        if len(results) == 0:
            return []

        ids = tuple([result[0] for result in results])

        entities = self._fetch_by_ids(entity, ids)

        return self._sort_by_score(entities, results)

    @memoize
    def _fetch_by_ids(self, entity, ids):
        return get_database().query(entity).filter(entity.id.in_(ids)).all()

    def _sort_by_score(self, entities, results):
        indexed_results = {}

        for id, score in results:
            indexed_results[id] = score

        for entity in entities:
            entity._SEARCH_SCORE = indexed_results[entity.id]

        return sorted(entities, key=lambda entity: indexed_results[entity.id], reverse=True)

    @memoize
    def _query(self, index_name, query, exact=False, exact_metaphone=False):
        write_handler = write_handlers[index_name]

        if exact:
            terms = [
                (QueryParser("exact_name", write_handler.index.schema)
                    .term_query("exact_name", query, Term))
            ]
        elif exact_metaphone:
            terms = [
                (QueryParser("exact_name", write_handler.index.schema)
                    .term_query("exact_name", query, Term)),
                (QueryParser("exact_metaphone_name", write_handler.index.schema)
                    .term_query("exact_metaphone_name", query, Term))
            ]
        else:
            terms = [
                QueryParser("name", write_handler.index.schema).parse(query),
                QueryParser("metaphone_name", write_handler.index.schema).parse(query),
                QueryParser("stemmed_name", write_handler.index.schema).parse(query),
                QueryParser("filename", write_handler.index.schema).parse(query),
                QueryParser("slug", write_handler.index.schema).parse(query),
            ]

        # TODO cache/reuse the searcher object within requests/threads, maybe with
        #      a thread local storage
        with write_handler.index.searcher() as searcher:
            results = searcher.search(Or([term for term in terms if term is not None]))
            return set([(int(result['id']), result.score) for result in results])


class WhooshPlugin(Monitor):

    def __init__(self, bus):
        Monitor.__init__(self, bus, self.run, frequency=30)

        self._running = False
        self._stopped = False

    def run(self):
        self._running = True

        for name, write_handler in write_handlers.items():
            write_handler.commit()

        self._running = False

    def start(self):
        self._stopped = False

        for index_name in index_names:
            index_path = os.path.join(search.index_dir, index_name)

            if whoosh.index.exists_in(index_path):
                index = whoosh.index.open_dir(index_path)
            else:
                if not os.path.exists(index_path):
                    os.makedirs(index_path)

                schema = whoosh.fields.Schema(
                    id=whoosh.fields.ID(stored=True, unique=True),
                    name=whoosh.fields.TEXT(
                        analyzer=RegexTokenizer() | LowercaseFilter()
                    ),
                    stemmed_name=whoosh.fields.TEXT(
                        analyzer=SpaceSeparatedTokenizer() | LowercaseFilter() | StemFilter()
                    ),
                    metaphone_name=whoosh.fields.TEXT(
                        analyzer=SpaceSeparatedTokenizer() | LowercaseFilter() | DoubleMetaphoneFilter()
                    ),
                    exact_name=whoosh.fields.TEXT(
                        analyzer=IDTokenizer() | LowercaseFilter()
                    ),
                    exact_metaphone_name=whoosh.fields.TEXT(
                        analyzer=IDTokenizer() | LowercaseFilter() | DoubleMetaphoneFilter()
                    ),
                    slug=whoosh.fields.TEXT(
                        analyzer=RegexTokenizer(r"[^_]+") | LowercaseFilter()
                    ),
                    filename=whoosh.fields.TEXT(
                        analyzer=RegexTokenizer(r"[^ \t\r\n_\.]+") | LowercaseFilter()
                    ),
                )

                index = whoosh.index.create_in(index_path, schema)

            write_handler = WriteHandler(index_name, index)

            write_handlers[index_name] = write_handler

        Monitor.start(self)

    start.priority = 120

    def stop(self):
        Monitor.stop(self)

        if self._stopped:
            return

        self._stopped = True

        for name, write_handler in write_handlers.items():
            write_handlers[name] = None
            write_handler.stopped = True
            write_handler.commit()


search = Search()
