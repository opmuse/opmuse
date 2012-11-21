import subprocess

class Image:

    FNULL = open('/dev/null', 'w')

    def resize(self, source, dest, width, height = None):
        if height is None:
            height = width

        process = subprocess.Popen([
            'convert',
            '-resize', '%dx%d^' % (width, height),
            '-gravity', 'center',
            '-extent', '%dx%d' % (width, height),
            source, dest
        ], shell = False, stdout = self.FNULL, stderr = self.FNULL, stdin = None)

        process.wait()

        return process.returncode == 0

image = Image()
