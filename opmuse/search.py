import os
import cherrypy
from cherrypy.process.plugins import Monitor
import whoosh.index
import whoosh.fields
from whoosh.writing import BufferedWriter
from whoosh.analysis import StemmingAnalyzer
from whoosh.qparser import MultifieldParser
import opmuse.library

index_names = ['Artist', 'Album', 'Track']

write_handlers = {}

class WriteHandler:
    def __init__(self, index):
        self.index = index
        self._deletes = []
        self._updates = {}

    def delete_document(self, id):
        self._deletes.append(id)

    def update_document(self, id, **kwargs):
        self._updates[id] = kwargs

    def commit(self):
        with self.index.writer() as writer:
            while len(self._updates) > 0:
                id, kwargs = self._updates.popitem()
                writer.add_document(id = id, **kwargs)

            while len(self._deletes) > 0:
                id = self._deletes.pop()
                writer.delete_document(id)


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

    def query_track(self, query):
        keys = self._query("Track", query)
        return self._fetch_by_keys(opmuse.library.Track, keys)

    def query_album(self, query):
        keys = self._query("Album", query)
        return self._fetch_by_keys(opmuse.library.Album, keys)

    def query_artist(self, query):
        keys = self._query("Artist", query)
        return self._fetch_by_keys(opmuse.library.Artist, keys)

    def _fetch_by_keys(self, entity, keys):
        return cherrypy.request.database.query(entity).filter(entity.id.in_(keys))

    def _query(self, index_name, query):
        write_handler = write_handlers[index_name]
        parser = MultifieldParser(list(write_handler.index.schema._fields.keys()), write_handler.index.schema)
        results = write_handler.index.searcher().search(parser.parse(query))
        return set([x['id'] for x in results])


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
                    name = whoosh.fields.TEXT(analyzer=StemmingAnalyzer())
                )

                index = whoosh.index.create_in(index_path, schema)

            write_handler = WriteHandler(index)

            write_handlers[index_name] = write_handler

        Monitor.start(self)

    start.priority = 120

    def stop(self):
        Monitor.stop(self)

        for name, write_handler in write_handlers.items():
            write_handler.commit()


search = Search()
