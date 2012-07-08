import io
import subprocess

class Transcoder:
    def transcode(self, filename):
        fileobj = io.open(filename, buffering = 1024)

        # TODO only works on unix...
        FNULL = open('/dev/null', 'w')

        # -aq 6 is about 192kbit/s
        p = subprocess.Popen("ffmpeg -i - -acodec libvorbis -f ogg -aq 6 -",
                             shell = True, stdout = subprocess.PIPE,
                             stderr = FNULL, stdin = fileobj)

        while True:
            line = p.stdout.readline()

            if not line:
                break

            yield line

