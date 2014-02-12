import os
import subprocess


class LessCompiler:
    def __init__(self):
        self.stylespath = os.path.join(os.path.dirname(__file__), '..', 'public_static', 'styles')

    def compile(self, path=None):
        lesspath = os.path.join(os.path.dirname(__file__), '..', 'vendor', 'less.js')

        if path is None:
            path = os.path.join(self.stylespath, 'main.css')
        else:
            path = os.path.join(os.getcwd(), path)

        subprocess.call([
            os.path.join(lesspath, 'bin', 'lessc'),
            os.path.join(self.stylespath, 'main.less'),
            path
        ], cwd=self.stylespath)


less_compiler = LessCompiler()
