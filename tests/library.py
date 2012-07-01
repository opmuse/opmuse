import os, unittest
from opmuse.library import Library

class LibraryTest(unittest.TestCase):
    def test_tracks(self):
        library = Library(os.path.join(os.path.dirname(__file__), "../sample_library"))
        tracks = library.get_tracks()

        self.assertEqual(tracks[0].artist.name, "opmuse")
        self.assertEqual(tracks[0].album.name, "opmuse")
        self.assertEqual(tracks[0].name, "opmuse")

