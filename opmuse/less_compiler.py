import os
import subprocess


class LessCompiler:
    def compile(self, path=None, fluid=True):
        if fluid:
            fluid = "true"
        else:
            fluid = "false"

        from opmuse.utils import get_staticdir

        stylespath = os.path.join(get_staticdir(), 'styles')

        lesspath = os.path.join(os.path.dirname(__file__), '..', 'vendor', 'less.js')

        if path is None:
            path = os.path.join(stylespath, 'main.css')
        else:
            path = os.path.join(os.getcwd(), path)

        lessc = os.path.join(lesspath, 'bin', 'lessc')
        main_less = os.path.join(stylespath, 'main.less')

        subprocess.check_call([
            lessc,
            "--global-var=fluid=%s" % fluid,
            main_less, path
        ], cwd=stylespath)


less_compiler = LessCompiler()
