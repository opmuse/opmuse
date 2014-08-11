import os
import subprocess


class LessCompiler:
    def compile(self, path=None, no_opmuse=False):
        """
        Compiles less to css.

        path
            where to write compiled css.
        no_opmuse
            if true we generate a css without some opmuse
            specific rules. useful for docs and other stuff.
        """

        if no_opmuse:
            no_opmuse = "true"
        else:
            no_opmuse = "false"

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
            "--global-var=no_opmuse=%s" % no_opmuse,
            main_less, path
        ], cwd=stylespath)


less_compiler = LessCompiler()
