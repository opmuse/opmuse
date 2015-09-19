# Copyright 2012-2015 Mattias Fliesberg
#
# This file is part of opmuse.
#
# opmuse is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# opmuse is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with opmuse.  If not, see <http://www.gnu.org/licenses/>.

import os
import subprocess
from subprocess import CalledProcessError
import glob


def log(msg, traceback=False):
    try:
        import cherrypy
    except ImportError:
        return

    cherrypy.log(msg, context='compilers', traceback=traceback)


class LessCompiler:
    def __init__(self):
        from opmuse.utils import get_staticdir

        self.dir_from = os.path.join(os.path.dirname(__file__), '..', 'less')
        self.dir_to = os.path.join(get_staticdir(), 'styles')

    def compile(self, script=None, path=None, no_opmuse=False):
        """
        Compiles less to css.

        script
            script name, ignored for LessCompiler (used by JsCompiler)
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

        lesspath = os.path.join(os.path.dirname(__file__), '..', 'node_modules', 'less')

        if path is None:
            path = os.path.join(self.dir_to, 'main.css')
        else:
            path = os.path.join(os.getcwd(), path)

        lessc = os.path.join(lesspath, 'bin', 'lessc')
        main_less = os.path.join(self.dir_from, 'main.less')

        try:
            subprocess.check_call([
                lessc,
                "--global-var=no_opmuse=%s" % no_opmuse,
                main_less, path
            ], cwd=self.dir_to)

            log("Compiled main.css")
        except CalledProcessError as e:
            log("Failed to compile main.css", traceback=True)


less_compiler = LessCompiler()


class JsCompiler:
    def __init__(self):
        from opmuse.utils import get_staticdir
        self.dir_from = os.path.join(os.path.dirname(__file__), '..', 'javascript')
        self.dir_to = os.path.join(get_staticdir(), 'scripts')

    def compile(self, script=None, path=None):
        """
        Compiles es6 js to es5 js.

        path
            where to write compiled js.
        """

        if script is None:
            for script in glob.glob(os.path.join(self.dir_from, '*.js')):
                self._compile(script, path)
        else:
            self._compile(script, path)

    def _compile(self, script, path):
        basename = os.path.basename(script)

        if path is None:
            path = os.path.join(self.dir_to, basename)
        else:
            path = os.path.join(os.getcwd(), path, basename)

        traceur_path = os.path.join(os.path.dirname(__file__), '..', 'node_modules', 'traceur', 'traceur')

        try:
            subprocess.check_call([
                traceur_path,
                '--script', script,
                '--out', path
            ], cwd=self.dir_from)

            log("compiled %s" % basename)
        except CalledProcessError as e:
            log("Failed to compile %s" % basename, traceback=True)


js_compiler = JsCompiler()
