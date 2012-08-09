import io
import os
import subprocess
import cherrypy

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
                stdin = io.open(filename, buffering = 8192)
                cmd = ffmpeg % "-"

            p = subprocess.Popen(cmd, shell = True, stdout = subprocess.PIPE,
                                 stderr = FNULL, stdin = stdin)

            cherrypy.request.transcoder_subprocess = p

            while True:
                data = p.stdout.read(8192)

                if len(data) == 0:
                    break

                yield data

            p.wait()

