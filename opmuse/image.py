import subprocess


class Image:

    FNULL = open('/dev/null', 'w')

    def resize(self, source, dest, width, height = None, gravity = 'center', offset = None):
        if height is None:
            height = width

        extent = '%dx%d' % (width, height)

        if offset is not None:
            extent += offset

        process = subprocess.Popen([
            'convert',
            '-resize', '%dx%d^' % (width, height),
            '-gravity', gravity,
            '-extent', extent,
            source, dest
        ], shell = False, stdout = self.FNULL, stderr = self.FNULL, stdin = None)

        process.wait()

        return process.returncode == 0

image = Image()
