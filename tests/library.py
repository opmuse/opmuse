import os, unittest
from opmuse.library import Library, Artist
from opmuse.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# TODO implement fixtures for tests...
class LibraryTest(unittest.TestCase):
    def test_tracks(self):
        db_path = 'tests/opmuse.db'

        if os.path.exists(db_path):
            os.remove(db_path)

        engine = create_engine('sqlite:///./%s' % db_path)
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()

        Library(os.path.join(os.path.dirname(__file__), "../sample_library"), session)

        artist = session.query(Artist).one()

        self.assertEqual(artist.name, "opmuse")
        self.assertEqual(artist.albums[0].name, "opmuse")
        self.assertEqual(artist.albums[0].tracks[0].name, "opmuse")

