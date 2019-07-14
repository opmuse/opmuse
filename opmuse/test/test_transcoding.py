# Copyright 2012-2015 Mattias Fliesberg
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

import magic
import mmh3
import base64
from opmuse.transcoding import transcoding, CopyFFMPEGTranscoder, OggFFMPEGTranscoder, Mp3FFMPEGTranscoder
from opmuse.library import Track
from .test_library import library_start
from . import setup_db, teardown_db


class TestTranscoding:
    def setup_method(self):
        setup_db(self)

    def teardown_method(self):
        teardown_db(self)

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
        user_agent = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) " +
                      "Chrome/32.0.1700.107 Safari/537.36")
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
        user_agent = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) " +
                      "Chrome/32.0.1700.107 Safari/537.36")
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
            assert "Ogg" in magic.from_buffer(data)
            break
        else:
            assert False

        # test mp3
        def track_generator():
            yield self.session.query(Track).filter(Track.name == "opmuse mp3").one(), 0

        for data in transcoding.transcode(track_generator()):
            assert "ID3" in magic.from_buffer(data)
            break
        else:
            assert False

        # TODO test skipping

        # test ogg to mp3
        def track_generator():
            yield self.session.query(Track).filter(Track.name == "opmuse").one(), 0

        for data in transcoding.transcode(track_generator(), Mp3FFMPEGTranscoder):
            assert "ID3" in magic.from_buffer(data)
            break
        else:
            assert False

        # test mp3 to ogg
        def track_generator():
            yield self.session.query(Track).filter(Track.name == "opmuse mp3").one(), 0

        for data in transcoding.transcode(track_generator(), OggFFMPEGTranscoder):
            assert "Ogg" in magic.from_buffer(data)
            break
        else:
            assert False
