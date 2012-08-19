import os
import re
import cherrypy
from opmuse.playlist import playlist_model
from opmuse.transcoder import transcoder
from opmuse.lastfm import SessionKey, lastfm
from opmuse.library import Artist, Album, Track, library
from repoze.who.api import get_api
from repoze.who._compat import get_cookies

class Lastfm:
    @cherrypy.expose
    @cherrypy.tools.jinja(filename='lastfm.html')
    @cherrypy.tools.authenticated()
    def default(self):

        auth_url = authenticated_user = new_auth = None

        if cherrypy.request.user.lastfm_session_key is None:
            if 'lastfm_session_key' in cherrypy.session:
                session_key = cherrypy.session['lastfm_session_key']
                auth_url = session_key.get_auth_url()
                key = session_key.get_session_key()

                if key is not None:
                    cherrypy.session.pop('lastfm_session_key')
                    cherrypy.request.user.lastfm_session_key = key
                    cherrypy.request.user.lastfm_user = lastfm.get_authenticated_user_name()
                    auth_url = None
                    new_auth = True
            else:
                session_key = SessionKey()
                auth_url = session_key.get_auth_url()
                cherrypy.session['lastfm_session_key'] = session_key

        return {
            'auth_url': auth_url,
            'new_auth': new_auth
        }

class Playlist:

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='partials/playlist-tracks.html')
    def list(self):
        user_id = cherrypy.request.user.id
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

        path = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            '..', 'public', 'styles'
        )

        csspath = os.path.join(path, file)

        if os.path.exists(csspath):
            return cherrypy.lib.static.serve_file(csspath)

        ext = os.path.splitext(file)
        lesspath = os.path.join(path, "%s%s" % (ext[0], ".less"))

        return cherrypy.lib.static.serve_file(lesspath)


class Root(object):
    styles = Styles()
    playlist = Playlist()
    lastfm = Lastfm()

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
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='search.html')
    def search(self, query):
        artists = Artist.search_query(query).all()
        albums = Album.search_query(query).all()
        tracks = Track.search_query(query).all()

        results = {}

        for artist in artists:
            results[artist.id] = {
                'entity': artist,
                'albums': {}
            }

        for album in albums:
            for artist in album.artists:
                if artist.id not in results:
                    results[artist.id] = {
                        'entity': artist,
                        'albums': {}
                    }

                results[artist.id]['albums'][album.id] = {
                    'entity': album,
                    'tracks': {}
                }

        for track in tracks:
            if track.artist.id not in results:
                results[track.artist.id] = {
                    'entity': track.artist,
                    'albums': {}
                }

            if track.album.id not in results[track.artist.id]['albums']:
                results[track.artist.id]['albums'][track.album.id] = {
                    'entity': track.album,
                    'tracks': {}
                }

            results[track.artist.id]['albums'][track.album.id]['tracks'][track.id] = {
                'entity': track
            }

        return {'results': results}

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='index.html')
    def index(self):
        return {}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='track.html')
    def track(self, slug):
        return {'track': library.get_track_by_slug(slug)}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='album.html')
    def album(self, artist_slug, album_slug):
        artist = library.get_artist_by_slug(artist_slug)
        album = library.get_album_by_slug(album_slug)
        return {'artist': artist, 'album': album}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='artist.html')
    def artist(self, slug):
        return {'artist': library.get_artist_by_slug(slug)}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='library.html')
    def library(self):
        return {'artists': library.get_artists()}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='play.m3u')
    def play_m3u(self):
        cherrypy.response.headers['Content-Type'] = 'audio/x-mpegurl'
        cookies = get_cookies(cherrypy.request.wsgi_environ)
        # TODO use "cookie_name" prop from authtkt plugin...
        auth_tkt = cookies.get('auth_tkt').value
        return {'auth_tkt': auth_tkt}

    @cherrypy.expose
    @cherrypy.tools.transcodingsubprocess()
    @cherrypy.tools.authenticated()
    @cherrypy.config(**{'response.stream': True})
    # TODO reimplement Accept header support
    def stream(self, slug = None, **kwargs):

        user_id = cherrypy.request.user.id

        cherrypy.response.headers['Content-Type'] = 'audio/ogg'

        def track_generator():
            while True:
                yield playlist_model.getNextTrack(user_id)

                if slug == "one":
                    break

        return transcoder.transcode(track_generator())

