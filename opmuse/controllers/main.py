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

import os
import cherrypy
import mimetypes
from repoze.who.api import get_api
from opmuse.library import library_dao
from opmuse.utils import HTTPRedirect
from opmuse.ws import WsController
from opmuse.jinja import render_template
from opmuse.controllers.queue import Queue
from opmuse.controllers.users import Users
from opmuse.controllers.settings import Settings
from opmuse.controllers.library import Library
from opmuse.controllers.love import Love
from opmuse.controllers.dashboard import Dashboard
from opmuse.controllers.admin import Admin
from opmuse.controllers.cover import Cover
from opmuse.controllers.play import Play
from opmuse.messages import messages


class Root:
    @staticmethod
    def handle_error(status, message, traceback, version):
        return render_template("error.html", {
            'status': status,
            'message': message,
            'traceback': traceback,
            'version': version
        })

    queue = Queue()
    users = Users()
    settings = Settings()
    library = Library()
    love = Love()
    ws = WsController()
    dashboard = Dashboard()
    admin = Admin()
    cover = Cover()
    play = Play()

    @cherrypy.expose
    def __profile__(self, *args, **kwargs):
        return b'Profiler is disabled, enable it with --profile'

    @cherrypy.expose
    @cherrypy.tools.expires(secs=3600 * 24 * 30, force=True)
    @cherrypy.tools.authenticated(needs_auth=True)
    # TODO add some extra security to this function... maybe
    def download(self, file):
        library_path = library_dao.get_library_path()

        ext = os.path.splitext(file)

        content_type = mimetypes.types_map.get(ext[1], None)

        # viewable in most browsers
        if content_type in ('image/jpeg', "image/png", "image/gif", 'application/pdf',
                            'text/x-nfo', 'text/plain', 'text/x-sfv', 'audio/x-mpegurl'):
            disposition = None

            if content_type in ('text/x-nfo', 'text/x-sfv', 'audio/x-mpegurl'):
                content_type = 'text/plain'

        # download...
        else:
            disposition = 'attachement'
            content_type = None

        return cherrypy.lib.static.serve_file(os.path.join(library_path, file),
                                              content_type=content_type, disposition=disposition)

    @cherrypy.expose
    def search(self, *args, **kwargs):
        if len(args) > 1:
            raise cherrypy.InternalRedirect('/library/search/%s/%s' % (args[0], args[1]))
        elif len(args) > 0:
            raise cherrypy.InternalRedirect('/library/search/%s' % args[0])
        else:
            raise cherrypy.InternalRedirect('/library/search')

    @cherrypy.expose
    def default(self, *args, **kwargs):
        if len(args) == 1:
            raise cherrypy.InternalRedirect('/library/artist/%s' % args[0])
        elif len(args) == 2:
            raise cherrypy.InternalRedirect('/library/album/%s/%s' % (args[0], args[1]))

        raise cherrypy.NotFound()

    @cherrypy.expose
    @cherrypy.tools.multiheaders()
    def logout(self, came_from=None):
        who_api = get_api(cherrypy.request.wsgi_environ)

        headers = who_api.forget()

        cherrypy.response.multiheaders = headers

        raise HTTPRedirect('/login?came_from=%s' % came_from)

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='login.html')
    @cherrypy.tools.multiheaders()
    def login(self, login=None, password=None, came_from=None):
        if login is not None and password is not None:
            who_api = get_api(cherrypy.request.wsgi_environ)

            creds = {
                'login': login,
                'password': password
            }

            authenticated, headers = who_api.login(creds)

            if authenticated:
                if cherrypy.response.header_list is None:
                    cherrypy.response.header_list = []

                cherrypy.response.multiheaders = headers

                if came_from is not None and came_from != "None":
                    raise HTTPRedirect(came_from)
                else:
                    raise HTTPRedirect('/')
            else:
                messages.danger('Username and/or password is incorrect.')
        elif hasattr(cherrypy.request, 'user') and cherrypy.request.user is not None:
            raise HTTPRedirect('/')

        return {}

    @cherrypy.expose
    def index(self):
        if cherrypy.request.user is None:
            raise cherrypy.InternalRedirect('/index_unauth')
        else:
            raise cherrypy.InternalRedirect('/index_auth')

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='index_unauth.html')
    def index_unauth(self):
        if 'Referer' not in cherrypy.request.headers:
            raise HTTPRedirect('/login')

        return {}

    @cherrypy.expose
    def index_auth(self):
        raise cherrypy.InternalRedirect('/dashboard')
