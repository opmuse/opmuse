import magic
import mmh3
import base64
from opmuse.transcoding import transcoding, CopyFFMPEGTranscoder, OggFFMPEGTranscoder, Mp3FFMPEGTranscoder
from opmuse.library import Track
from .test_library import library_start
from . import setup_db, teardown_db
from nose.tools import with_setup


@with_setup(setup_db, teardown_db)
class TestTranscoding:
    def test_determine_transcoder(self):
        library_start()

        ogg_track = self.session.query(Track).filter(Track.name == "opmuse").one()

        # MPD ogg
        transcoder, format = transcoding.determine_transcoder(ogg_track, "Music Player Daemon 0.18.8", ['*/*'])

        assert format == "audio/ogg"
        assert transcoder == CopyFFMPEGTranscoder

        # firefox ogg
        user_agent = "Mozilla/5.0 (X11; Linux x86_64; rv:27.0) Gecko/20100101 Firefox/27.0 FirePHP/0.7.4"
        accepts = ['audio/webm', 'audio/wav', 'audio/ogg', 'audio/*', 'application/ogg', 'video/*', '*/*']
        transcoder, format = transcoding.determine_transcoder(ogg_track, user_agent, accepts)

        assert format == "audio/ogg"
        assert transcoder == CopyFFMPEGTranscoder

        # chrome ogg
        user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1700.107 Safari/537.36"
        accepts = ['*/*']
        transcoder, format = transcoding.determine_transcoder(ogg_track, user_agent, accepts)

        assert format == "audio/ogg"
        assert transcoder == CopyFFMPEGTranscoder

        mp3_track = self.session.query(Track).filter(Track.name == "opmuse mp3").one()

        # MPD mp3
        transcoder, format = transcoding.determine_transcoder(mp3_track, "Music Player Daemon 0.18.8", ['*/*'])

        assert format == "audio/mp3"
        assert transcoder == CopyFFMPEGTranscoder

        # firefox mp3
        user_agent = "Mozilla/5.0 (X11; Linux x86_64; rv:27.0) Gecko/20100101 Firefox/27.0 FirePHP/0.7.4",
        accepts = ['audio/webm', 'audio/wav', 'audio/ogg', 'audio/*', 'application/ogg', 'video/*', '*/*']
        transcoder, format = transcoding.determine_transcoder(mp3_track, user_agent, accepts)

        assert format == "audio/ogg"
        assert transcoder == OggFFMPEGTranscoder

        # chrome mp3
        user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1700.107 Safari/537.36"
        accepts = ['*/*']
        transcoder, format = transcoding.determine_transcoder(mp3_track, user_agent, accepts)

        assert format == "audio/mp3"
        assert transcoder == CopyFFMPEGTranscoder

    def test_transcode(self):
        library_start()

        # test ogg
        def track_generator():
            yield self.session.query(Track).filter(Track.name == "opmuse").one(), 0

        for data in transcoding.transcode(track_generator()):
            assert magic.from_buffer(data) == b"Ogg data, Vorbis audio, stereo, 44100 Hz, ~64000 bps"
            break
        else:
            assert False

        # test mp3
        def track_generator():
            yield self.session.query(Track).filter(Track.name == "opmuse mp3").one(), 0

        for data in transcoding.transcode(track_generator()):
            assert magic.from_buffer(data) == (b'Audio file with ID3 version 2.4.0, contains: MPEG ADTS,' +
                                               b' layer III, v1, 128 kbps, 44.1 kHz, JntStereo')
            break
        else:
            assert False

        # TODO test skipping

        # test ogg to mp3
        def track_generator():
            yield self.session.query(Track).filter(Track.name == "opmuse").one(), 0

        for data in transcoding.transcode(track_generator(), Mp3FFMPEGTranscoder):
            assert magic.from_buffer(data) == (b'Audio file with ID3 version 2.4.0, contains: MPEG ADTS,' +
                                               b' layer III, v1, 320 kbps, 44.1 kHz, JntStereo')
            break
        else:
            assert False

        # test mp3 to ogg
        def track_generator():
            yield self.session.query(Track).filter(Track.name == "opmuse mp3").one(), 0

        for data in transcoding.transcode(track_generator(), OggFFMPEGTranscoder):
            assert magic.from_buffer(data) == b'Ogg data, Vorbis audio, stereo, 44100 Hz, ~192000 bps'
            break
        else:
            assert False
