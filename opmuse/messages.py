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

import json
import cherrypy


class Messages:
    def warning(self, text):
        self.publish('warning', text)

    def info(self, text):
        self.publish('info', text)

    def danger(self, text):
        self.publish('danger', text)

    def success(self, text):
        self.publish('success', text)

    def publish(self, type, text):
        cherrypy.response.headers['X-Opmuse-Message'] = json.dumps({
            'type': type,
            'text': text
        })


messages = Messages()
