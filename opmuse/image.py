# Copyright 2012-2014 Mattias Fliesberg
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
