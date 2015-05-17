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
