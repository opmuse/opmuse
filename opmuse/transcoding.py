# Copyright 2012-2014 Mattias Fliesberg
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

import os
import time
import subprocess
import re
import cherrypy
import fcntl
import select
import logging
import signal
from subprocess import TimeoutExpired


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
        transcoding_transcoder = None

        if (hasattr(cherrypy.request, 'transcoding_transcoder') and
                cherrypy.request.transcoding_transcoder is not None):

            transcoding_transcoder = cherrypy.request.transcoding_transcoder

            cherrypy.request.transcoding_transcoder = None

            transcoding_transcoder.stop()

        if (hasattr(cherrypy.request, 'transcoding_track') and
                cherrypy.request.transcoding_track is not None):

            transcoding_track = cherrypy.request.transcoding_track

            cherrypy.request.transcoding_track = None

            cherrypy.engine.publish('transcoding.end',
                                    track=transcoding_track,
                                    transcoder=transcoding_transcoder)

            debug('"%s" transcoding ended.' % transcoding_track)


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
        self.stderr = None
        self.success = False
        self.error = None
        self.stopped = False
        self.process = None

        if cherrypy.request.app is not None:
            ffmpeg_cmd = cherrypy.request.app.config.get('opmuse').get('transcoding.ffmpeg_cmd')
        else:
            ffmpeg_cmd = None

        if ffmpeg_cmd is not None:
            self.ffmpeg_cmd = ffmpeg_cmd
        else:
            self.ffmpeg_cmd = 'ffmpeg'

    def __enter__(self):
        cherrypy.engine.publish('transcoding.start', transcoder=self, track=self.track)

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
                    '-'])

        for index, arg in enumerate(args):
            if not isinstance(arg, bytes):
                arg = arg.encode('utf8')

            args[index] = arg.replace(b'EXT', ext)

        cherrypy.request.transcoding_track = self.track
        cherrypy.request.transcoding_transcoder = self

        try:
            self.process = subprocess.Popen(args, shell = False, stdout = subprocess.PIPE,
                                            stderr = subprocess.PIPE, stdin = None)
        except Exception as e:
            self.error = 'Got "%s" when starting ffmpeg.' % str(e)
            return

        debug('transcoding with: %s' % b' '.join(args).decode('utf8', 'replace'))

        return self.transcode

    def __exit__(self, type, value, traceback):
        if self.process is not None:
            try:
                self.process.wait(10)
            except TimeoutExpired:
                self.stop()

        if self.process is not None and not self.stopped and self.process.returncode != 0:
            stderr_lines = self.stderr.decode('utf8', 'replace').split("\n")

            try:
                stderr_lines.remove("")
            except ValueError:
                pass

            self.error = stderr_lines[-1]

            log('ffmpeg returned non-zero status "%d" and "%s".' % (self.process.returncode, self.error))
        elif self.error is not None:
            log('Got exception "%s".' % (self.error))
        else:
            self.success = True

        cherrypy.engine.publish('transcoding.done', track=self.track)

        debug('"%s" transcoding done.' % self.track)

    def stop(self):
        if self.stopped:
            return

        if self.process is not None:
            try:
                self.process.send_signal(signal.SIGTERM)
                self.process.stdout.read()
                self.process.wait()
            except ProcessLookupError:
                pass

        self.stopped = True

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

                            self.stderr = chunk

                            if len(chunk) > 0:
                                match = re.match(b'.*time=[ ]*(?P<time>[0-9.:]+).*bitrate=[ ]*(?P<bitrate>[0-9.]+)',
                                                 chunk)

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
        seconds_keepahead = 2

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
                'seconds_ahead': seconds_ahead
            }, transcoder=self, track=self.track)

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
    players = [
        ['Music Player Daemon', ['audio/mp3', 'audio/ogg']],
        ['foobar2000', ['audio/mp3', 'audio/ogg']],
        ['Windows.*Chrome', ['audio/mp3', 'audio/ogg']],
        ['Linux.*Chrome', ['audio/mp3', 'audio/ogg']],
        ['VLC', ['audio/mp3', 'audio/ogg']],
        # This matches Nokia N9s default player
        ['GStreamer', ['audio/mp3', 'audio/ogg']]
    ]
    """
    if a player doesn't supply a usable Accept header we will look through this
    to figure out what formats it supports

     - we don't put audio/flac here, always transcode it to mp3 or ogg
     - we prioritze mp3 over ogg because we've had some lag-issues with ogg,
       at least when transcoding from flac to ogg...
     - we default to mp3
    """

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

        if track.format == 'audio/mp3':
            return CopyFFMPEGTranscoder, 'audio/mp3'
        else:
            return Mp3FFMPEGTranscoder, 'audio/mp3'

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
            if isinstance(transcoder, Transcoder):
                raise Exception("transcoder must be an instance of Transcoder")

            with transcoder(track, skip_seconds) as transcode:
                # error occured in __enter__
                if transcode is None:
                    return

                for data in transcode():
                    yield data

transcoding = Transcoding()
