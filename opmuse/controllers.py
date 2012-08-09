import os
import re
import cherrypy
from opmuse.playlist import playlist_model
from opmuse.transcoder import Transcoder
from repoze.who.api import get_api

class Playlist:

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='partials/playlist-tracks.html')
    def list(self):
        return {'playlist': playlist_model.getTracks()}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def add(self, slug):
        playlist_model.addTrack(slug)

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def add_album(self, slug):
        playlist_model.addAlbum(slug)

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def remove(self, slug):
        playlist_model.removeTrack(slug)

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def clear(self):
        playlist_model.clear()


class Styles(object):
    @cherrypy.expose
    def default(self, file):
        cherrypy.response.headers['Content-Type'] = 'text/css'

        path = os.path.join(os.path.abspath("."), "public", "styles")

        csspath = os.path.join(path, file)

        if os.path.exists(csspath):
            return cherrypy.lib.static.serve_file(csspath)

        ext = os.path.splitext(file)
        lesspath = os.path.join(path, "%s%s" % (ext[0], ".less"))

        if os.path.exists(lesspath):
            from lesscpy.lessc import parser
            p = parser.LessParser()
            p.parse(
                filename=lesspath,
                debuglevel=0
            )

            items = {
                'nl': '\n',
                'tab': '\t',
                'ws': ' ',
                'eb': '\n'
            }

            return ''.join([u.fmt(items) for u in p.result if u]).strip()


class Root(object):
    styles = Styles()
    playlist = Playlist()

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

                raise cherrypy.HTTPRedirect(came_from)

        return {}

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='index.html')
    def index(self):
        return {}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='album.html')
    def album(self, slug):
        library = cherrypy.engine.library.library
        return {'album': library.get_album_by_slug(slug)}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='artist.html')
    def artist(self, slug):
        library = cherrypy.engine.library.library
        return {'artist': library.get_artist_by_slug(slug)}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='library.html')
    def library(self):
        library = cherrypy.engine.library.library
        return {'artists': library.get_artists()}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='play.m3u')
    def play_m3u(self):
        cherrypy.response.headers['Content-Type'] = 'audio/x-mpegurl'
        return {}

    @cherrypy.expose
    @cherrypy.tools.transcodingsubprocess()
    @cherrypy.config(**{'response.stream': True})
    # TODO reimplement Accept header support
    # TODO implement some sort of security here :|
    def stream(self, slug = None, **kwargs):

        user_id = None

        if slug is not None and re.compile("^[0-9]+$").match(slug):
            user_id = slug

        tracks = playlist_model.getTracks(user_id)

        if len(tracks) == 0:
            raise cherrypy.HTTPError(409)

        cherrypy.response.headers['Content-Type'] = 'audio/ogg'

        return Transcoder().transcode([track.paths[0].path for track in tracks])

