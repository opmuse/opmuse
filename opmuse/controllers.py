import os
import re
import cherrypy
from opmuse.playlist import playlist_model
from opmuse.transcoder import transcoder
from repoze.who.api import get_api

class Playlist:

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='partials/playlist-tracks.html')
    def list(self):
        user_id = cherrypy.session.get('user_id')
        return {'playlists': playlist_model.getPlaylists(user_id)}

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
    def default(self, *args):
        file = os.path.join(*args)
        cherrypy.response.headers['Content-Type'] = 'text/css'

        path = os.path.join(os.path.abspath("."), "public", "styles")

        csspath = os.path.join(path, file)

        if os.path.exists(csspath):
            return cherrypy.lib.static.serve_file(csspath)

        ext = os.path.splitext(file)
        lesspath = os.path.join(path, "%s%s" % (ext[0], ".less"))

        return cherrypy.lib.static.serve_file(lesspath)


class Root(object):
    styles = Styles()
    playlist = Playlist()

    @cherrypy.expose
    @cherrypy.tools.multiheaders()
    def logout(self):
        who_api = get_api(cherrypy.request.wsgi_environ)

        headers = who_api.forget()

        cherrypy.response.multiheaders = headers

        raise cherrypy.HTTPRedirect('/')

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
        else:
            user_id = cherrypy.session.get('user_id')


        cherrypy.response.headers['Content-Type'] = 'audio/ogg'

        def track_generator():
            while True:
                track = playlist_model.getNextTrack(user_id)

                # TODO play silence..
                if track is None:
                    raise cherrypy.HTTPError(409)

                yield track.paths[0].path

                if slug == "one":
                    break

        return transcoder.transcode(track_generator())

