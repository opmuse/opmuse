from opmuse.transcoding import transcoding, CopyFFMPEGTranscoder, OggFFMPEGTranscoder
from opmuse.library import Track
from test_library import library_start
from main import setup_db, teardown_db
from nose.tools import with_setup

@with_setup(setup_db, teardown_db)
class TestTranscoding:
    def test_determine_transcoder(self):
        library_start()

        ogg_track = self.session.query(Track).filter(Track.name=="opmuse").one()

        # MPD ogg
        transcoder, format = transcoding.determine_transcoder(ogg_track, "Music Player Daemon 0.18.8", ['*/*'])

        assert format == "audio/ogg"
        assert transcoder == CopyFFMPEGTranscoder

        # firefox ogg
        transcoder, format = transcoding.determine_transcoder(ogg_track,
            "Mozilla/5.0 (X11; Linux x86_64; rv:27.0) Gecko/20100101 Firefox/27.0 FirePHP/0.7.4",
            ['audio/webm', 'audio/wav', 'audio/ogg', 'audio/*', 'application/ogg', 'video/*', '*/*'])

        assert format == "audio/ogg"
        assert transcoder == CopyFFMPEGTranscoder

        # chrome ogg
        transcoder, format = transcoding.determine_transcoder(ogg_track,
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1700.107 Safari/537.36",
            ['*/*'])

        assert format == "audio/ogg"
        assert transcoder == CopyFFMPEGTranscoder

        mp3_track = self.session.query(Track).filter(Track.name=="opmuse mp3").one()

        # MPD mp3
        transcoder, format = transcoding.determine_transcoder(mp3_track, "Music Player Daemon 0.18.8", ['*/*'])

        assert format == "audio/mp3"
        assert transcoder == CopyFFMPEGTranscoder

        # firefox mp3
        transcoder, format = transcoding.determine_transcoder(mp3_track,
            "Mozilla/5.0 (X11; Linux x86_64; rv:27.0) Gecko/20100101 Firefox/27.0 FirePHP/0.7.4",
            ['audio/webm', 'audio/wav', 'audio/ogg', 'audio/*', 'application/ogg', 'video/*', '*/*'])

        assert format == "audio/ogg"
        assert transcoder == OggFFMPEGTranscoder

        # chrome mp3
        transcoder, format = transcoding.determine_transcoder(mp3_track,
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1700.107 Safari/537.36",
            ['*/*'])

        assert format == "audio/mp3"
        assert transcoder == CopyFFMPEGTranscoder
