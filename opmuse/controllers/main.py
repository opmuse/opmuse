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
from repoze.who._compat import get_cookies
from opmuse.library import library_dao
from opmuse.utils import HTTPRedirect
from opmuse.ws import WsController
from opmuse.covers import covers
from opmuse.jinja import render_template
from opmuse.controllers.queue import Queue
from opmuse.controllers.users import Users
from opmuse.controllers.settings import Settings
from opmuse.controllers.library import Library
from opmuse.controllers.dashboard import Dashboard
from opmuse.controllers.admin import Admin
from opmuse.controllers.stream import Stream


class Styles:
    @cherrypy.expose
    def default(self, *args, **kwargs):
        file = os.path.join(*args)
        cherrypy.response.headers['Content-Type'] = 'text/css'

        path = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            '..', 'public_static', 'styles'
        )

        csspath = os.path.join(path, file)

        if os.path.exists(csspath):
            return cherrypy.lib.static.serve_file(csspath)

        ext = os.path.splitext(file)
        lesspath = os.path.join(path, "%s%s" % (ext[0], ".less"))

        return cherrypy.lib.static.serve_file(lesspath)


class Root:
    @staticmethod
    def handle_error(status, message, traceback, version):
        return render_template("error.html", {
            'status': status,
            'message': message,
            'traceback': traceback,
            'version': version
        })

    styles = Styles()
    queue = Queue()
    users = Users()
    settings = Settings()
    library = Library()
    ws = WsController()
    dashboard = Dashboard()
    admin = Admin()
    stream = Stream()

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
    def logout(self, came_from = None):
        who_api = get_api(cherrypy.request.wsgi_environ)

        headers = who_api.forget()

        cherrypy.response.multiheaders = headers

        raise HTTPRedirect('/?came_from=%s' % came_from)

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='login.html')
    @cherrypy.tools.multiheaders()
    def login(self, login = None, password = None, came_from = None):
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

        return {}

    @cherrypy.expose
    def index(self, came_from = None):
        if cherrypy.request.user is None:
            raise cherrypy.InternalRedirect('/index_unauth?came_from=%s' % came_from)
        else:
            raise cherrypy.InternalRedirect('/index_auth')

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='index_unauth.html')
    def index_unauth(self, came_from = None):
        if 'Referer' not in cherrypy.request.headers:
            raise HTTPRedirect('/login')

        return {}

    @cherrypy.expose
    def index_auth(self):
        raise cherrypy.InternalRedirect('/dashboard')

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.authorize(roles=['admin'])
    def cover_refresh(self, type, slug):
        try:
            covers.refresh(type, slug)
        except ValueError:
            raise cherrypy.NotFound()

        return b''

    @cherrypy.expose
    @cherrypy.tools.expires(secs=3600 * 24 * 30, force=True)
    @cherrypy.tools.authenticated(needs_auth=True)
    def cover(self, type, slug, hash = None, refresh = None, size="default"):
        try:
            mime, cover = covers.get_cover(type, slug, size)
        except ValueError:
            raise cherrypy.NotFound()

        if cover is None:
            cherrypy.response.headers['Content-Type'] = 'image/png'

            if size == "large":
                placeholder = 'cover_large_placeholder.png'
            else:
                placeholder = 'cover_placeholder.png'

            return cherrypy.lib.static.serve_file(os.path.join(
                os.path.abspath(os.path.dirname(__file__)),
                '..', 'public_static', 'images', placeholder
            ))
        else:
            cherrypy.response.headers['Content-Type'] = mime

            return cover

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='play.m3u')
    def play_m3u(self):
        cherrypy.response.headers['Content-Type'] = 'audio/x-mpegurl'

        cookies = get_cookies(cherrypy.request.wsgi_environ)
        # TODO use "cookie_name" prop from authtkt plugin...
        auth_tkt = cookies.get('auth_tkt').value

        stream_ssl = cherrypy.request.app.config.get('opmuse').get('stream.ssl')

        if stream_ssl is False:
            scheme = 'http'
        else:
            scheme = cherrypy.request.scheme

        forwarded_host = cherrypy.request.headers.get('X-Forwarded-Host')

        if forwarded_host is not None:
            host = forwarded_host.split(",")[0].strip()
        else:
            host = cherrypy.request.headers.get('host')

        if stream_ssl is False:
            if ':' in host:
                host = host[:host.index(':')]

            host = '%s:%s' % (host, cherrypy.config['server.socket_port'])

        url = "%s://%s/stream?auth_tkt=%s" % (scheme, host, auth_tkt)

        cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=play.m3u'

        return {'url': url}
