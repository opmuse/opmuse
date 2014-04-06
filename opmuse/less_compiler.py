import os
import subprocess


class LessCompiler:
    def compile(self, path=None):
        from opmuse.utils import get_staticdir

        stylespath = os.path.join(get_staticdir(), 'styles')

        lesspath = os.path.join(os.path.dirname(__file__), '..', 'vendor', 'less.js')

        if path is None:
            path = os.path.join(stylespath, 'main.css')
        else:
            path = os.path.join(os.getcwd(), path)

        subprocess.call([
            os.path.join(lesspath, 'bin', 'lessc'),
            os.path.join(stylespath, 'main.less'),
            path
        ], cwd=stylespath)


less_compiler = LessCompiler()
