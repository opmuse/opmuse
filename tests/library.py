import os, unittest
import cherrypy
from opmuse.boot import configure
from opmuse.library import Library, Artist
from opmuse.database import Base, get_raw_session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# TODO implement fixtures for tests...
class LibraryTest(unittest.TestCase):
    def test_tracks(self):
        db_path = 'tests/opmuse.db'

        if os.path.exists(db_path):
            os.remove(db_path)

        configure()

        cherrypy.tree.apps[''].config['opmuse']['database.url'] = 'sqlite:///./%s' % db_path

        session = get_raw_session(create_all = True)

        library = Library(os.path.join(os.path.dirname(__file__), "../sample_library"))
        library.start()

        artist = session.query(Artist).one()

        self.assertEqual(artist.name, "opmuse")
        self.assertEqual(artist.albums[0].name, "opmuse")
        self.assertEqual(artist.albums[0].tracks[0].name, "opmuse")

