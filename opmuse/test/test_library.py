import os
from opmuse.library import Library, Artist
from . import setup_db, teardown_db
from nose.tools import with_setup


def library_start():
    library = Library(os.path.join(os.path.dirname(__file__), "../../sample_library"),
                      use_opmuse_txt=False)
    library.start()


@with_setup(setup_db, teardown_db)
class TestLibrary:
    def test_tracks(self):

        library_start()

        artists = self.session.query(Artist).order_by(Artist.name).all()

        assert len(artists) == 2

        assert artists[0].name == "opmuse"
        assert artists[0].albums[0].name == "opmuse"
        assert artists[0].albums[0].tracks[0].name == "opmuse"

        assert artists[1].name == "opmuse mp3"
        assert artists[1].albums[0].name == "opmuse mp3"
        assert artists[1].albums[0].tracks[0].name == "opmuse mp3"
