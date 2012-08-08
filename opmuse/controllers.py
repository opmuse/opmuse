import os
import cherrypy
import opmuse.playlist
from opmuse.transcoder import Transcoder
from repoze.who.api import get_api

class Playlist:
    def __init__(self):
        self.model = opmuse.playlist.Model()

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='playlist-tracks.html')
    def list(self):
        return {'playlist': self.model.getTracks()}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def add(self, slug):
        self.model.addTrack(slug)

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def add_album(self, slug):
        self.model.addAlbum(slug)

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def remove(self, track_number):
        self.model.removeTrack(track_number)

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def clear(self):
        self.model.clear()


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
    @cherrypy.config(**{'response.stream': True})
    # TODO reimplement Accept header support
    def stream(self, **kwargs):

        playlist = cherrypy.session.get('playlist', [])

        if len(playlist) == 0:
            raise cherrypy.HTTPError(409)

        cherrypy.response.headers['Content-Type'] = 'audio/ogg'

        for track in playlist:
            cherrypy.request.database.add(track)

        return Transcoder().transcode([track.paths[0].path for track in playlist])

