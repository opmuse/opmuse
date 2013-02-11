import io
import os
import time
import subprocess
import re
import cherrypy
import calendar
import datetime
import fcntl
import select


def log(msg):
    cherrypy.log(msg, context='transcoding')


class FFMPEGError(Exception):
    pass


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
            cherrypy.engine.publish('transcoding.end', track=track)


class Transcoder:
    def transcode(self):
        raise NotImplementedError()

    @staticmethod
    def outputs():
        raise NotImplementedError()


class FFMPEGTranscoder(Transcoder):

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
                                        stderr = subprocess.PIPE, stdin = None)

        cherrypy.request.ffmpegtranscoder_subprocess = self.process
        cherrypy.request.transcoding_track = self.track

        return self.transcode

    def __exit__(self, type, value, traceback):
        self.process.wait()

        if self.process.returncode != 0:
            raise FFMPEGError('ffmpeg returned non-zero status "%d".' % self.process.returncode)

        cherrypy.request.ffmpegtranscoder_subprocess = None

    @staticmethod
    def set_nonblocking(fileno):
        fcntl.fcntl(
            fileno, fcntl.F_SETFL, fcntl.fcntl(fileno, fcntl.F_GETFL) | os.O_NONBLOCK,
        )

    def read_process(self):
        FFMPEGTranscoder.set_nonblocking(self.process.stderr.fileno())

        poll = select.poll()

        poll.register(self.process.stdout, select.POLLIN | select.POLLHUP)
        poll.register(self.process.stderr, select.POLLIN | select.POLLHUP)

        pollc = 2

        events = poll.poll()

        bitrate = self.bitrate()

        use_ffmpeg_bitrate = False

        if bitrate is None:
            bitrate = self.initial_bitrate()
            use_ffmpeg_bitrate = True

        while pollc > 0 and len(events) > 0:
            info = data = None

            for event in events:
                rfd, event = event

                if event & select.POLLIN:
                    if rfd == self.process.stdout.fileno():
                        data = self.process.stdout.read(bitrate)

                    if rfd == self.process.stderr.fileno():
                        readx = select.select([self.process.stderr.fileno()], [], [])[0]

                        if readx:
                            chunk = self.process.stderr.read()

                            if len(chunk) > 0:
                                match = re.match(b'.*bitrate=[ ]*(?P<bitrate>[0-9.]+)', chunk)

                                if match:
                                    info = match.groupdict()

                if event & select.POLLHUP:
                    poll.unregister(rfd)
                    pollc = pollc - 1

                if pollc > 0:
                    events = poll.poll()

            yield data, bitrate

            if use_ffmpeg_bitrate and info is not None:
                bitrate = int(float(info['bitrate'].decode()) * 1024 / 8)

    def transcode(self):

        # how many seconds to stay ahead of the client
        seconds_keep_ahead = 15
        # ... and if we fall behind more than this try to slowly adjust
        seconds_adjust = 5

        start_time = time.time()

        streamed = 0
        chunks = 0

        for data, bitrate in self.read_process():

            yield data

            streamed += bitrate
            chunks += 1

            # we pace the streaming so we don't have to send more than
            # the client can chew. this is also good for transcoding.{start,end}
            # events that lastfm uses so it can more accurately know how much
            # the client has actually played.
            #
            # what we do is try to stay seconds_keep_ahead seconds ahead of the
            # client, no more, no less...

            # we estimate how much we've sent by using the latest bitrate we
            # received from ffmpeg...
            seconds = streamed / bitrate

            seconds_ahead = seconds - (time.time() - start_time)

            # ... and then we just continue (if wait below 0) or wait until we are
            # no more than seconds_keep_ahead ahead
            wait = seconds_ahead - seconds_keep_ahead + 1

            wait_adjust = (wait - seconds_adjust) / 10

            if wait > 1:
                wait = 1

                if wait_adjust > 0:
                    wait += wait_adjust

            elif wait < 0:
                wait = 0

            cherrypy.engine.publish('transcoding.progress', progress={
                'seconds': seconds,
                'bitrate': bitrate,
                'seconds_ahead': seconds_ahead,
            }, track=self.track)

            if False:
                log('Streaming at %d b/s, we\'re %.2fs ahead (total %ds) and waiting for %.2fs.' %
                    (bitrate, seconds_ahead, seconds, wait))

            if wait > 0:
                time.sleep(wait)

    def initial_bitrate(self):
        """
        If bitrate() isn't implemented this needs to be implemented for an
        initial bitrate to use before we get one from ffmpeg.
        """
        raise NotImplementedError()

    def bitrate(self):
        """
        Should return the approximate bitrate this transcoder produces, so we
        can approximately pace the streaming properly. If this isn't specified
        we use whatever ffmpeg tells us.
        """
        return None


class CopyFFMPEGTranscoder(FFMPEGTranscoder):
    ffmpeg_output_args = ["-acodec", "copy", "-f", "EXT"]
    ffmpeg_input_args = []

    def outputs():
        return None

    def initial_bitrate(self):
        # used when track has no bitrate
        return int(192000 / 8)

    def bitrate(self):
        if self.track.bitrate is not None and self.track.bitrate != 0:
            return int(self.track.bitrate / 8)
        else:
            # just use the one ffmpeg outputs
            return None


class Mp3FFMPEGTranscoder(FFMPEGTranscoder):
    # -aq 0 should be v0
    ffmpeg_output_args = ["-acodec", "libmp3lame", "-f", "mp3", "-aq", "0"]
    ffmpeg_input_args = []

    def outputs():
        return 'audio/mp3'

    def initial_bitrate(self):
        # lame v0's target bitrate is 245kbit/s (but is of course VBR)
        return int(245000 / 8)


class OggFFMPEGTranscoder(FFMPEGTranscoder):
    ffmpeg_output_args = ["-acodec", "libvorbis", "-f", "ogg", "-aq", "6"]
    ffmpeg_input_args = []

    def outputs():
        return 'audio/ogg'

    def initial_bitrate(self):
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
        ['GStreamer', ['audio/ogg', 'audio/mp3']],
        ['iPad', ['audio/mp3']],
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

            cherrypy.engine.publish('transcoding.start', track=track)

            with transcoder(track) as transcode:
                for data in transcode():
                    yield data

transcoding = Transcoding()
