import subprocess

class Image:

    FNULL = open('/dev/null', 'w')

    def resize(self, source, dest, width, height = None):
        if height is None:
            height = width

        process = subprocess.Popen([
            'identify',
            '-format',
            '%w %h',
            source
        ], shell = False, stdout = subprocess.PIPE, stderr = self.FNULL, stdin = None)

        process.wait()

        dimension = process.stdout.read()

        source_width, source_height = dimension.strip().split(b' ')

        source_width, source_height = int(source_width), int(source_height)

        if source_width > source_height:
            resize = '>x%d' % height
        else:
            resize = '%dx>' % width

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
