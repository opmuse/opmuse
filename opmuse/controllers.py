import os
import re
import datetime
import cherrypy
from repoze.who.api import get_api
from repoze.who._compat import get_cookies
from collections import OrderedDict
from opmuse.queues import queue_model
from opmuse.transcoding import transcoding
from opmuse.lastfm import SessionKey, lastfm
from opmuse.library import Artist, Album, Track, library
from opmuse.who import User
from sqlalchemy.orm.exc import NoResultFound

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

class Users:
    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='users.html')
    def default(self, login = None):
        if login is not None:
            raise cherrypy.InternalRedirect('/users/user/%s' % login)

        users = (cherrypy.request.database.query(User)
            .order_by(User.login).all())

        return {'users': users}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='user.html')
    def user(self, login):
        try:
            user = (cherrypy.request.database.query(User)
                .filter_by(login=login)
                .order_by(User.login).one())
        except NoResultFound:
            raise cherrypy.NotFound()

        queues = queue_model.getQueues(user.id)

        return {'user': user, 'queues': queues}

class Queue:

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='queue.html')
    def list(self):
        user_id = cherrypy.request.user.id
        return {'queues': queue_model.getQueues(user_id)}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def add(self, slug):
        queue_model.addTrack(slug)

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def add_album(self, slug):
        queue_model.addAlbum(slug)

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def remove(self, slug):
        queue_model.removeTrack(slug)

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def clear(self, what = None):
        if what is not None and what == 'played':
            queue_model.clear_played()
        else:
            queue_model.clear()


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
    queue = Queue()
    lastfm = Lastfm()
    users = Users()

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
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='index.html')
    def index(self):
        return {}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='track.html')
    def track(self, slug):
        track = library.get_track_by_slug(slug)

        if track is None:
            raise cherrypy.NotFound()

        return {'track': track}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='album.html')
    def album(self, artist_slug, album_slug):
        artist = library.get_artist_by_slug(artist_slug)
        album = library.get_album_by_slug(album_slug)

        if artist is None or album is None:
            raise cherrypy.NotFound()

        return {'artist': artist, 'album': album}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='artist.html')
    def artist(self, slug):
        artist = library.get_artist_by_slug(slug)

        if artist is None:
            raise cherrypy.NotFound()

        return {'artist': artist}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='invalid_tracks.html')
    def invalid_tracks(self):

        tracks = (cherrypy.request.database.query(Track)
            .filter(Track.valid == False).all())

        return {'tracks': tracks}


    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='library.html')
    def library(self):
        tracks = library.get_new_tracks(datetime.datetime.now() - datetime.timedelta(days=30))

        added = OrderedDict({})

        for title in ('Today', 'Yesterday', '7 Days', '14 Days', '30 Days'):
            added[title] = []

        today = datetime.date.today()

        for track in tracks:
            if track.added.date() == today:
                added['Today'].append(track)
            elif track.added.date() == today - datetime.timedelta(days=1):
                added['Yesterday'].append(track)
            elif track.added.date() >= today - datetime.timedelta(days=7):
                added['7 Days'].append(track)
            elif track.added.date() >= today - datetime.timedelta(days=14):
                added['14 Days'].append(track)
            else:
                added['30 Days'].append(track)

        for title, tracks in added.items():
            added[title] = sorted(tracks,
                key = lambda track : (track.artist.name, track.album.name, track.number, track.name)
            )

        return {'added': added}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='play.m3u')
    def play_m3u(self):
        cherrypy.response.headers['Content-Type'] = 'audio/x-mpegurl'

        cookies = get_cookies(cherrypy.request.wsgi_environ)
        # TODO use "cookie_name" prop from authtkt plugin...
        auth_tkt = cookies.get('auth_tkt').value

        url = "%s/stream?auth_tkt=%s" % (cherrypy.request.base, auth_tkt)

        cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=play.m3u'

        return {'url': url }

    @cherrypy.expose
    @cherrypy.tools.transcodingsubprocess()
    @cherrypy.tools.authenticated()
    @cherrypy.config(**{'response.stream': True})
    def stream(self, **kwargs):

        user_id = cherrypy.request.user.id

        track = queue_model.getNextTrack(user_id)

        transcoder, format = transcoding.determine_transcoder(
            track,
            cherrypy.request.headers['User-Agent'],
            [accept.value for accept in cherrypy.request.headers.elements('Accept')]
        )

        cherrypy.log(
            '%s is streaming "%s" in %s (original was %s)' %
            (cherrypy.request.user.login, track, format, track.format)
        )

        cherrypy.response.headers['Content-Type'] = format

        def track_generator():
            yield track

        return transcoding.transcode(track_generator(), transcoder)

