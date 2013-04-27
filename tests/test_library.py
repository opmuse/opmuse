import os
from opmuse.library import Library, Artist
from main import setup, teardown
from nose.tools import with_setup

@with_setup(setup, teardown)
class TestLibrary:
    def test_tracks(self):

        library = Library(os.path.join(os.path.dirname(__file__), "../sample_library"))
        library.start()

        artist = session.query(Artist).one()

        assert artist.name == "opmuse"
        assert artist.albums[0].name == "opmuse"
        assert artist.albums[0].tracks[0].name == "opmuse"

