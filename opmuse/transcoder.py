import io
import subprocess

class Transcoder:
    def transcode(self, filenames):
        for filename in filenames:
            fileobj = io.open(filename, buffering = 1024)

            # TODO only works on unix...
            FNULL = open('/dev/null', 'w')

            # -aq 6 is about 192kbit/s
            p = subprocess.Popen("ffmpeg -i - -acodec libvorbis -f ogg -aq 6 -",
                                 shell = True, stdout = subprocess.PIPE,
                                 stderr = FNULL, stdin = fileobj)

            data = p.stdout.read()

            p.kill()

            yield data

