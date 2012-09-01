import io
import os
import time
import subprocess
import cherrypy
from pydispatch import dispatcher

class TranscodingSubprocessTool(cherrypy.Tool):
    """
    This tool makes sure the ffmpeg subprocess is ended
    properly when a request is cancelled
    """
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_end_request',
                               self.end, priority=20)

    def end(self):
        if hasattr(cherrypy.request, 'transcoder_subprocess'):
            p = cherrypy.request.transcoder_subprocess
            p.stdout.read()
            p.wait()


class Transcoding:
    def __init__(self):
        self.silence_seconds = 2
        self.silence = self.generate_silence(self.silence_seconds)

    def transcode(self, tracks):
        for track in tracks:

            start_time = time.time()

            if track is None:
                yield self.silence
                time.sleep(self.silence_seconds)
                continue

            filename = track.paths[0].path

            ext = os.path.splitext(os.path.basename(filename))[1].lower()[1:]

            # TODO only works on unix...
            FNULL = open('/dev/null', 'w')

            artist = track.artist.name
            album = track.album.name
            title = track.name
            track_number = track.number if track.number is not None else 0

            # -aq 6 is about 192kbit/s
            ffmpeg = ('ffmpeg -i "%s" -acodec libvorbis -f ogg -aq 6 ' +
                '-metadata artist="%s" -metadata album="%s" -metadata title="%s" -metadata tracknumber="%d" ' %
                    (artist, album, title, track_number) +
                '-')

            # TODO "hack" for mp4 until we can get mp4's to stream properly
            #       maybe use https://github.com/danielgtaylor/qtfaststart ?
            if ext == "mp4":
                stdin = None
                cmd = ffmpeg % filename
            else:
                stdin = io.open(filename, buffering = 8192)
                cmd = ffmpeg % "-"

            p = subprocess.Popen(cmd, shell = True, stdout = subprocess.PIPE,
                                 stderr = FNULL, stdin = stdin)

            cherrypy.request.transcoder_subprocess = p

            dispatcher.send(signal='start_transcoding', sender=track)

            while True:
                data = p.stdout.read(8192)

                if len(data) == 0:
                    break

                yield data

            p.wait()

            total_time = int(time.time() - start_time)

            # wait to send next track until this track has played (this assumes
            # the player doesn't pause or anything)
            # we do this to get more correct "now playing" status in the queue
            if track.duration is not None and track.duration != 0:
                time.sleep(track.duration - total_time)

            dispatcher.send(signal='end_transcoding', sender=track)

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

