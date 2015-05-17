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
import cherrypy
from opmuse.covers import covers
from opmuse.boot import get_staticdir


class Cover:
    @cherrypy.expose
    @cherrypy.tools.expires(secs=3600 * 24 * 30, force=True)
    @cherrypy.tools.authenticated(needs_auth=True)
    def default(self, type, slug, hash=None, refresh=None, size="default"):
        try:
            mime, cover = covers.get_cover(type, slug, size)
        except ValueError:
            raise cherrypy.NotFound()

        if cover is None:
            if size == "large":
                placeholder = 'cover_large_placeholder.png'
            else:
                placeholder = 'cover_placeholder.png'

            images_path = os.path.join(get_staticdir(), 'images')

            return cherrypy.lib.static.serve_file(os.path.join(images_path, placeholder))
        else:
            cherrypy.response.headers['Content-Type'] = mime

            return cover

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    def refresh(self, type, slug):
        try:
            covers.refresh(type, slug)
        except ValueError:
            raise cherrypy.NotFound()

        return b''
