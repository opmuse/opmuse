import os
import cherrypy
from cherrypy.process.plugins import Monitor
import whoosh.index
import whoosh.fields
from whoosh.writing import BufferedWriter, IndexingError
from whoosh.analysis import (RegexTokenizer, SpaceSeparatedTokenizer,
    LowercaseFilter, StemFilter, DoubleMetaphoneFilter)
from whoosh.qparser import MultifieldParser
from whoosh.query import Term
from opmuse.database import get_database
import opmuse.library

index_names = ['Artist', 'Album', 'Track']
write_handlers = {}


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
                    exact_name=name.lower()
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

    def query_track(self, query, exact = False):
        results = self._query("Track", query, exact)
        return self._fetch_by_keys(opmuse.library.Track, results)

    def query_album(self, query, exact = False):
        results = self._query("Album", query, exact)
        return self._fetch_by_keys(opmuse.library.Album, results)

    def query_artist(self, query, exact = False):
        results = self._query("Artist", query, exact)
        return self._fetch_by_keys(opmuse.library.Artist, results)

    def _fetch_by_keys(self, entity, results):
        ids = [result[0] for result in results]

        entities = get_database().query(entity).filter(entity.id.in_(ids)).all()

        return self._sort_by_score(entities, results)

    def _sort_by_score(self, entities, results):
        indexed_results = {}

        for id, score in results:
            indexed_results[id] = score

        return sorted(entities, key=lambda entity: indexed_results[entity.id])

    def _query(self, index_name, query, exact = False):
        write_handler = write_handlers[index_name]

        if exact:
            whoosh_query = Term('exact_name', query.lower())
        else:
            parser = MultifieldParser(list(write_handler.index.schema._fields.keys()), write_handler.index.schema)
            whoosh_query = parser.parse(query)

        results = write_handler.index.searcher().search(whoosh_query)

        return set([(int(result['id']), result.score) for result in results])


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
        indexdir = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            '..', 'cache', 'index'
        )

        for index_name in index_names:
            index_path = os.path.join(indexdir, index_name)

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
                    exact_name = whoosh.fields.ID()
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
