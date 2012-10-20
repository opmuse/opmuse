import io
import os
import time
import subprocess
import re
import cherrypy
import calendar
import datetime
from pydispatch import dispatcher

class FFMPEGTranscoderSubprocessTool(cherrypy.Tool):
    """
    This tool makes sure the ffmpeg subprocess is ended
    properly when a request is cancelled
    """
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_end_request',
                               self.end, priority=20)

    def end(self):
        if (hasattr(cherrypy.request, 'ffmpegtranscoder_subprocess') and
            cherrypy.request.ffmpegtranscoder_subprocess is not None):

            p = cherrypy.request.ffmpegtranscoder_subprocess
            p.stdout.read()
            p.wait()

        if (hasattr(cherrypy.request, 'transcoding_track') and
            cherrypy.request.transcoding_track is not None):

            track = cherrypy.request.transcoding_track
            dispatcher.send(signal='end_transcoding', sender=track)


class Transcoder:
    def transcode(self):
        raise NotImplementedError()

    @staticmethod
    def outputs():
        raise NotImplementedError()

class FFMPEGTranscoder(Transcoder):

    FNULL = open('/dev/null', 'w')

    def __init__(self, track):
        self.track = track

    def __enter__(self):
        filename = self.track.paths[0].path

        ext = os.path.splitext(os.path.basename(filename))[1].lower()[1:]

        artist = self.track.artist.name
        album = self.track.album.name
        title = self.track.name
        track_number = self.track.number if self.track.number is not None else 0

        args = (['ffmpeg'] +
            self.ffmpeg_input_args +
            ['-i', filename] +
            # always produce stereo output
            ['-ac', '2'] +
            # strip any video streams
            ['-vn'] +
            self.ffmpeg_output_args + [
                '-metadata', 'artist=%s' % artist,
                '-metadata', 'album=%s' % album,
                '-metadata', 'title=%s' % title,
                '-metadata', 'tracknumber=%s' % track_number,
                '-'
            ])

        for index, arg in enumerate(args):
            if not isinstance(arg, bytes):
                arg = arg.encode('utf8')

            args[index] = arg.replace(b'EXT', ext)

        self.process = subprocess.Popen(args, shell = False, stdout = subprocess.PIPE,
                                        stderr = self.FNULL,
                                        stdin = None)

        cherrypy.request.ffmpegtranscoder_subprocess = self.process
        cherrypy.request.transcoding_track = self.track

        return self.transcode

    def __exit__(self, type, value, traceback):
        self.process.wait()
        cherrypy.request.ffmpegtranscoder_subprocess = None

    def transcode(self):

        # total seconds transcoded
        seconds = 0

        # how many seconds to stay ahead of the client
        seconds_keep_ahead = 10

        start_time = time.time()
        one_second = .95

        bitrate = self.bitrate()

        while True:
            data = self.process.stdout.read(bitrate)

            if len(data) == 0:
                break

            yield data

            seconds += 1

            # we pace the streaming so we don't have to send more than
            # the client can chew. this is also good for start/end_transcoding
            # events that lastfm uses so it can more accurately know how much
            # the client has actually played.
            #
            # what we do is try to stay seconds_keep_ahead seconds ahead of the
            # client, no more, no less...

            seconds_ahead = seconds * one_second - (time.time() - start_time)

            if seconds_ahead < seconds_keep_ahead:
                wait = one_second - (seconds_keep_ahead - seconds_ahead)
            else:
                wait = one_second

            if wait > 0:
                time.sleep(wait)

    def bitrate(self):
        """
        Should return the approximate bitrate this transcoder produces, so we
        can approximately pace the streaming properly
        """
        raise NotImplementedError()


class CopyFFMPEGTranscoder(FFMPEGTranscoder):
    ffmpeg_output_args = ["-acodec", "copy", "-f", "EXT"]
    ffmpeg_input_args = []

    def outputs():
        return None

    def bitrate(self):
        if self.track.bitrate is not None and self.track.bitrate != 0:
            return int(self.track.bitrate / 8)
        else:
            # default to a bitrate of 128kbit/s
            return int(128000 / 8)

class Mp3FFMPEGTranscoder(FFMPEGTranscoder):
    # -aq 0 should be v0
    ffmpeg_output_args = ["-acodec", "libmp3lame", "-f", "mp3", "-aq", "0"]
    ffmpeg_input_args = []

    def outputs():
        return 'audio/mp3'

    def bitrate(self):
        # lame v0's target bitrate is 245kbit/s (but is of course VBR)
        return int(245000 / 8)

class OggFFMPEGTranscoder(FFMPEGTranscoder):
    ffmpeg_output_args = ["-acodec", "libvorbis", "-f", "ogg", "-aq", "6"]
    ffmpeg_input_args = []

    def outputs():
        return 'audio/ogg'

    def bitrate(self):
        # -aq 6 is about 192kbit/s
        return int(192000 / 8)

class Transcoding:
    # list of players that don't supply proper Accept headers, basically...
    # don't have audio/flac here, always transcode it seeing as it's lossless...
    players = [
        ['Music Player Daemon', ['audio/ogg', 'audio/mp3']],
        ['foobar2000', ['audio/ogg', 'audio/mp3']],
        ['Windows.*Chrome', ['audio/ogg', 'audio/mp3']],
        ['Linux.*Chrome', ['audio/ogg']],
        ['Windows-Media-Player', ['audio/mp3']],
        ['NSPlayer', ['audio/mp3']],
        ['WinampMPEG', ['audio/mp3']],
        ['iTunes.*Windows', ['audio/mp3']],
        ['iTunes.*Macintosh', ['audio/mp3']],
        ['VLC', ['audio/ogg', 'audio/mp3']],
        # This matches Nokia N9s default player
        ['GStreamer', ['audio/ogg', 'audio/mp3']]
    ]

    transcoders = [Mp3FFMPEGTranscoder, OggFFMPEGTranscoder]

    def determine_transcoder(self, track, user_agent, accepts):
        if not (len(accepts) == 0 or len(accepts) == 1 and accepts[0] == '*/*'):
            transcoder, format = self._determine_transcoder(track, accepts)
            if transcoder is not None:
                return transcoder, format

        for player, formats in self.players:
            if re.search(player, user_agent):
                transcoder, format = self._determine_transcoder(track, formats)
                if transcoder is not None:
                    return transcoder, format
                break

        if track.format == 'audio/ogg':
            return CopyFFMPEGTranscoder, 'audio/ogg'
        else:
            return OggFFMPEGTranscoder, 'audio/ogg'

    def _determine_transcoder(self, track, formats):
        if track.format in formats:
            return CopyFFMPEGTranscoder, track.format

        for format in formats:
            for transcoder in self.transcoders:
                if transcoder.outputs() == format:
                    return transcoder, format

        return None, None

    def transcode(self, tracks, transcoder = None):
        if transcoder is None:
            transcoder = CopyFFMPEGTranscoder

        for track in tracks:

            start_time = time.time()

            if isinstance(transcoder, Transcoder):
                raise Exception("transcoder must be an instance of Transcoder")

            dispatcher.send(signal='start_transcoding', sender=track)

            with transcoder(track) as transcode:
                for data in transcode():
                    yield data

            total_time = int(time.time() - start_time)

transcoding = Transcoding()

