import io
import os
import time
import subprocess
import re
import cherrypy
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
        if hasattr(cherrypy.request, 'ffmpegtranscoder_subprocess'):
            p = cherrypy.request.ffmpegtranscoder_subprocess
            p.stdout.read()
            p.wait()


class Transcoder:
    def transcode(self, track):
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

        return self.transcode

    def __exit__(self, type, value, traceback):
        self.process.wait()

    def transcode(self):
        while True:
            data = self.process.stdout.read(8192)

            if len(data) == 0:
                break

            yield data

class CopyFFMPEGTranscoder(FFMPEGTranscoder):
    ffmpeg_output_args = ["-acodec", "copy", "-f", "EXT"]
    ffmpeg_input_args = []

    def outputs():
        return None

class Mp3FFMPEGTranscoder(FFMPEGTranscoder):
    # -aq 0 should be v0
    ffmpeg_output_args = ["-acodec", "libmp3lame", "-f", "mp3", "-aq", "0"]
    ffmpeg_input_args = []

    def outputs():
        return 'audio/mp3'

class OggFFMPEGTranscoder(FFMPEGTranscoder):
    # -aq 6 is about 192kbit/s
    ffmpeg_output_args = ["-acodec", "libvorbis", "-f", "ogg", "-aq", "6"]
    ffmpeg_input_args = []

    def outputs():
        return 'audio/ogg'

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
    ]

    transcoders = [Mp3FFMPEGTranscoder, OggFFMPEGTranscoder]

    def __init__(self):
        self.silence_seconds = 2
        self.silence = self.generate_silence(self.silence_seconds)

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

            if track is None:
                yield self.silence
                time.sleep(self.silence_seconds)
                continue

            if isinstance(transcoder, Transcoder):
                raise Exception("transcoder must be an instance of Transcoder")

            dispatcher.send(signal='start_transcoding', sender=track)

            with transcoder(track) as transcode:
                for data in transcode():
                    yield data

            total_time = int(time.time() - start_time)

            # wait to send next track until this track has played (this assumes
            # the player doesn't pause or anything)
            # we do this to get more correct "now playing" status in the queue
            if track.duration is not None and track.duration != 0:
                time.sleep(track.duration - total_time)

            dispatcher.send(signal='end_transcoding', sender=track)

    # TODO rewrite to FFMPEGTranscoder or at least a Transcoder?
    def generate_silence(self, seconds = 1):

        FNULL = open('/dev/null', 'w')

        zero_cmd = 'dd if=/dev/zero bs=%d count=%d' % (44100 * 2 * 2, seconds)

        zero_proc = subprocess.Popen(zero_cmd, shell = True, stdout = subprocess.PIPE,
                             stderr = FNULL, stdin = None)

        artist = album = 'opmuse'
        title = 'Your queue is empty, enjoy the silence...'

        cmd = ('ffmpeg -ac 2 -ar 44100 -acodec pcm_s16le -f s16le ' +
            '-i - -acodec libvorbis -f ogg -aq 0 ' +
            '-metadata artist="%s" -metadata album="%s" -metadata title="%s" ' % (artist, album, title) +
            '-')

        proc = subprocess.Popen(cmd, shell = True, stdout = subprocess.PIPE,
                             stderr = FNULL, stdin = zero_proc.stdout)

        data = proc.stdout.read()

        proc.wait()
        zero_proc.wait()

        return data


transcoding = Transcoding()

