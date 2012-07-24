import io
import os
import subprocess

class Transcoder:
    def transcode(self, filenames):
        for filename in filenames:

            ext = os.path.splitext(os.path.basename(filename))[1].lower()[1:]

            # TODO only works on unix...
            FNULL = open('/dev/null', 'w')

            # -aq 6 is about 192kbit/s
            ffmpeg = "ffmpeg -i '%s' -acodec libvorbis -f ogg -aq 6 -"

            # TODO "hack" for mp4 until we can get mp4's to stream properly
            #       maybe use https://github.com/danielgtaylor/qtfaststart ?
            if ext == "mp4":
                stdin = None
                cmd = ffmpeg % filename
            else:
                stdin = io.open(filename, buffering = 1024)
                cmd = ffmpeg % "-"

            p = subprocess.Popen(cmd, shell = True, stdout = subprocess.PIPE,
                                 stderr = FNULL, stdin = stdin)

            data = p.stdout.read()

            p.kill()

            yield data

