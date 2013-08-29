import os
import time
import subprocess
import re
import cherrypy
import fcntl
import select
import logging
import signal


def debug(msg):
    cherrypy.log.error(msg, context='transcoding', severity=logging.DEBUG)


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
            p.send_signal(signal.SIGTERM)
            p.stdout.read()
            p.wait()

        if (hasattr(cherrypy.request, 'transcoding_track') and
            cherrypy.request.transcoding_track is not None):

            track = cherrypy.request.transcoding_track

            cherrypy.engine.publish('transcoding.end', track=track)

            debug('"%s" transcoding ended.' % track)


class Transcoder:
    def transcode(self):
        raise NotImplementedError()

    @staticmethod
    def outputs():
        raise NotImplementedError()


class FFMPEGTranscoder(Transcoder):

    def __init__(self, track, skip_seconds):
        self.track = track
        self.skip_seconds = skip_seconds

        ffmpeg_cmd = cherrypy.request.app.config.get('opmuse').get('transcoding.ffmpeg_cmd')

        if ffmpeg_cmd is not None:
            self.ffmpeg_cmd = ffmpeg_cmd
        else:
            self.ffmpeg_cmd = 'ffmpeg'

    def __enter__(self):
        self.filename = self.track.paths[0].path
        self.pretty_filename = self.track.paths[0].pretty_path

        ext = os.path.splitext(os.path.basename(self.filename))[1].lower()[1:]

        artist = self.track.artist.name if self.track.artist is not None else ''
        album = self.track.album.name if self.track.album is not None else ''
        title = self.track.name
        track_number = self.track.number if self.track.number is not None else 0

        if self.skip_seconds is not None:
            skip_seconds_args = ['-ss', str(self.skip_seconds)]
        else:
            skip_seconds_args = []

        args = ([self.ffmpeg_cmd] +
                skip_seconds_args +
                self.ffmpeg_input_args +
                # reads input at native frame rate, e.g. very handy for streaming.
                ['-re'] +
                ['-i', self.filename] +
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
                ]
        )

        for index, arg in enumerate(args):
            if not isinstance(arg, bytes):
                arg = arg.encode('utf8')

            args[index] = arg.replace(b'EXT', ext)

        self.process = subprocess.Popen(args, shell = False, stdout = subprocess.PIPE,
                                        stderr = subprocess.PIPE, stdin = None)

        cherrypy.request.ffmpegtranscoder_subprocess = self.process
        cherrypy.request.transcoding_track = self.track

        debug('transcoding with: %s' % b' '.join(args).decode('utf8', 'replace'))

        return self.transcode

    def __exit__(self, type, value, traceback):
        self.process.wait()

        if self.process.returncode != 0:
            raise FFMPEGError('ffmpeg returned non-zero status "%d".' % self.process.returncode)

        cherrypy.request.ffmpegtranscoder_subprocess = None

        cherrypy.engine.publish('transcoding.done', track=self.track)

        debug('"%s" transcoding done.' % self.track)

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

        initial_bitrate = self.initial_bitrate()

        bitrate = initial_bitrate
        seconds = 0

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
                                match = re.match(b'.*time=[ ]*(?P<time>[0-9.:]+).*bitrate=[ ]*(?P<bitrate>[0-9.]+)', chunk)

                                if match:
                                    info = match.groupdict()

                if event & select.POLLHUP:
                    poll.unregister(rfd)
                    pollc = pollc - 1

                if pollc > 0:
                    events = poll.poll()

            # this is here for when we don't get the output from ffmpeg and we assume we've read 1 second
            # of data seeing as we should have an approximate bitrate at least.
            seconds += 1

            yield data, bitrate, seconds

            if info is not None:
                bitrate = int(float(info['bitrate'].decode()) * 1024 / 8)

                match = re.match(b'(?P<hours>[0-9]+):(?P<minutes>[0-9]+):(?P<seconds>[0-9.]+)', info['time'])

                if match:
                    time_info = match.groupdict()

                    if time_info is not None:
                        hours = time_info['hours'].decode()
                        minutes = time_info['minutes'].decode()
                        seconds = time_info['seconds'].decode()
                        seconds = float(hours) * 60 * 60 + float(minutes) * 60 + float(seconds)

    def transcode(self):
        # we wait this long before we start streaming to the client as a way to fool ffmpeg
        # to keep the stream a couple of seconds before the client. this way the client can
        # buffer more than it's regular wait-before-starting-playing-cache-filling thingie.
        # this hopefully fixes choppy play for certain tracks in certain players.
        #
        # it would be nice if we could do this with ffmpeg directly so we could skip this
        # artificial wait, but i don't know how.
        seconds_keepahead = 3

        time.sleep(seconds_keepahead)

        start_time = time.time()

        for data, bitrate, seconds in self.read_process():

            yield data

            wall_time = time.time() - start_time

            if self.skip_seconds is not None:
                seconds += self.skip_seconds
                wall_time += self.skip_seconds

            seconds_ahead = seconds - wall_time

            cherrypy.engine.publish('transcoding.progress', progress={
                'seconds': seconds,
                'bitrate': bitrate,
                'seconds_ahead': seconds_ahead,
            }, track=self.track)

            debug('"%s" transcoding at %d b/s, we\'re %.2fs ahead (total %ds).' %
                 (self.pretty_filename, bitrate, seconds_ahead, seconds))

    def initial_bitrate(self):
        """
        initial bitrate to use before we get one from ffmpeg.
        """
        raise NotImplementedError()


class CopyFFMPEGTranscoder(FFMPEGTranscoder):
    ffmpeg_output_args = ["-acodec", "copy", "-f", "EXT"]
    ffmpeg_input_args = []

    def outputs():
        return None

    def initial_bitrate(self):
        if self.track.bitrate is not None and self.track.bitrate != 0:
            return int(self.track.bitrate / 8)
        else:
            # this value is veeery arbitrary because we don't know the format
            # audio quality or nothing... but on the other hand all tracks should
            # have a bitrate
            return int(192000 / 8)


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

        for track, skip_seconds in tracks:

            start_time = time.time()

            if isinstance(transcoder, Transcoder):
                raise Exception("transcoder must be an instance of Transcoder")

            cherrypy.engine.publish('transcoding.start', track=track)

            with transcoder(track, skip_seconds) as transcode:
                for data in transcode():
                    yield data

transcoding = Transcoding()
