# Copyright 2012-2013 Mattias Fliesberg
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
from whoosh.writing import BufferedWriter, IndexingError
from whoosh.analysis import (RegexTokenizer, SpaceSeparatedTokenizer,
                             LowercaseFilter, StemFilter, DoubleMetaphoneFilter, IDTokenizer)
from whoosh.qparser import QueryParser
from whoosh.query import Term, Or
from opmuse.database import get_database
from opmuse.cache import cache
import opmuse.library

index_names = ['Artist', 'Album', 'Track']
write_handlers = {}

INDEXDIR = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    '..', 'cache', 'index'
)


def log(msg):
    cherrypy.log(msg, context='search')


class WriteHandler:
    def __init__(self, name, index):
        self.name = name
        self.index = index
        self._deletes = []
        self._updates = {}

    def delete_document(self, id):
        self._deletes.append(id)

    def update_document(self, id, name):
        self._updates[id] = name

    def commit(self):
        updates = deletes = 0
        with self.index.writer() as writer:
            while len(self._updates) > 0:
                id, name = self._updates.popitem()
                writer.add_document(
                    id = id, name=name, stemmed_name=name, metaphone_name=name,
                    exact_name=name, exact_metaphone_name=name
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

    def delete_track(self, track):
        write_handler = write_handlers["Track"]
        write_handler.delete_document(track.id)

    def delete_album(self, album):
        write_handler = write_handlers["Album"]
        write_handler.delete_document(album.id)

    def delete_artist(self, artist):
        write_handler = write_handlers["Artist"]
        write_handler.delete_document(artist.id)

    def add_track(self, track):
        write_handler = write_handlers["Track"]
        write_handler.update_document(str(track.id), name = track.name)

    def add_album(self, album):
        write_handler = write_handlers["Album"]
        write_handler.update_document(str(album.id), name = album.name)

    def add_artist(self, artist):
        write_handler = write_handlers["Artist"]
        write_handler.update_document(str(artist.id), name = artist.name)

    def query_track(self, query, exact = False, exact_metaphone = False, cache_age = None):
        results = self._query("Track", query, exact, exact_metaphone, cache_age)
        return self._fetch_by_keys(opmuse.library.Track, results)

    def query_album(self, query, exact = False, exact_metaphone = False, cache_age = None):
        results = self._query("Album", query, exact, exact_metaphone, cache_age)
        return self._fetch_by_keys(opmuse.library.Album, results)

    def query_artist(self, query, exact = False, exact_metaphone = False, cache_age = None):
        results = self._query("Artist", query, exact, exact_metaphone, cache_age)
        return self._fetch_by_keys(opmuse.library.Artist, results)

    def _fetch_by_keys(self, entity, results):
        ids = [result[0] for result in results]

        entities = get_database().query(entity).filter(entity.id.in_(ids)).all()

        return self._sort_by_score(entities, results)

    def _sort_by_score(self, entities, results):
        indexed_results = {}

        for id, score in results:
            indexed_results[id] = score

        for entity in entities:
            entity.__SEARCH_SCORE = indexed_results[entity.id]

        return sorted(entities, key=lambda entity: indexed_results[entity.id], reverse=True)

    def _query(self, index_name, query, exact = False, exact_metaphone = False, cache_age = None):
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
                QueryParser("stemmed_name", write_handler.index.schema).parse(query)
            ]

        terms = Or([term for term in terms if term is not None])

        cache_key = "%s.%s" % (index_name, terms)

        if cache_age is None or cache.needs_update(cache_key, cache_age):
            results = write_handler.index.searcher().search(terms)

            ret = set([(int(result['id']), result.score) for result in results])

            if cache_age is not None and len(ret) > 0:
                cache.set(cache_key, ret)
        else:
            ret = cache.get(cache_key)

        return ret


class WhooshPlugin(Monitor):

    def __init__(self, bus):
        Monitor.__init__(self, bus, self.run, frequency = 30)

        self._running = False

    def run(self):
        self._running = True

        for name, write_handler in write_handlers.items():
            write_handler.commit()

        self._running = False

    def start(self):
        for index_name in index_names:
            index_path = os.path.join(INDEXDIR, index_name)

            if whoosh.index.exists_in(index_path):
                index = whoosh.index.open_dir(index_path)
            else:
                if not os.path.exists(index_path):
                    os.makedirs(index_path)

                schema = whoosh.fields.Schema(
                    id = whoosh.fields.ID(stored=True, unique=True),
                    name = whoosh.fields.TEXT(
                        analyzer=RegexTokenizer() | LowercaseFilter()
                    ),
                    stemmed_name = whoosh.fields.TEXT(
                        analyzer=SpaceSeparatedTokenizer() | LowercaseFilter() | StemFilter()
                    ),
                    metaphone_name = whoosh.fields.TEXT(
                        analyzer=SpaceSeparatedTokenizer() | LowercaseFilter() | DoubleMetaphoneFilter()
                    ),
                    exact_name = whoosh.fields.TEXT(
                        analyzer=IDTokenizer() | LowercaseFilter()
                    ),
                    exact_metaphone_name = whoosh.fields.TEXT(
                        analyzer=IDTokenizer() | LowercaseFilter() | DoubleMetaphoneFilter()
                    )
                )

                index = whoosh.index.create_in(index_path, schema)

            write_handler = WriteHandler(index_name, index)

            write_handlers[index_name] = write_handler

        Monitor.start(self)

    start.priority = 120

    def stop(self):
        Monitor.stop(self)

        for name, write_handler in write_handlers.items():
            write_handler.commit()


search = Search()
