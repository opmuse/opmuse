import subprocess

class Image:

    FNULL = open('/dev/null', 'w')

    def resize(self, source, dest, width, height = None):
        if height is None:
            height = width

        process = subprocess.Popen([
            'identify',
            '-format',
            '%w %h,',
            source
        ], shell = False, stdout = subprocess.PIPE, stderr = self.FNULL, stdin = None)

        process.wait()

        dimension = process.stdout.read().strip()

        resize = None

        if len(dimension) > 0:
            # in case of i.e. gifs there might be multiple frames so split by ","
            # first and then just use the first frame for our source width/height
            source_width, source_height = dimension.split(b',')[0].split(b' ')

            source_width, source_height = int(source_width), int(source_height)

            if source_width < source_height:
                resize = '%dx>' % width

        if resize is None:
            resize = '>x%d' % height

        process = subprocess.Popen([
            'convert',
            '-resize', resize,
            '-gravity', 'center',
            '-extent', '%dx%d' % (width, height),
            source, dest
        ], shell = False, stdout = self.FNULL, stderr = self.FNULL, stdin = None)

        process.wait()

        return process.returncode == 0

image = Image()
