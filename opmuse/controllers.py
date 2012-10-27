import os
import re
import datetime
import cherrypy
import tempfile
import shutil
import rarfile
from urllib.parse import unquote
from zipfile import ZipFile
from rarfile import RarFile
from repoze.who.api import get_api
from repoze.who._compat import get_cookies
from collections import OrderedDict
from sqlalchemy.orm.exc import NoResultFound
from opmuse.queues import queue_dao
from opmuse.transcoding import transcoding
from opmuse.lastfm import SessionKey, lastfm
from opmuse.library import Artist, Album, Track, library_dao
from opmuse.security import User
from opmuse.messages import messages
from opmuse.utils import HTTPRedirect

class Tag:
    @cherrypy.expose
    @cherrypy.tools.jinja(filename='tag.html')
    @cherrypy.tools.authenticated()
    def default(self, ids):
        ids = ids.split(',')

        tracks = library_dao.get_tracks_by_ids(ids)

        return {'tracks': tracks}

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='tag_edit.html')
    @cherrypy.tools.authenticated()
    def edit(self, ids, artists, albums, tracks, dates, numbers):

        update_tracks = self.get_tracks(ids, artists, albums, tracks, dates, numbers)

        library_path = library_dao.get_library_path().encode('utf8')

        return {"update_tracks": update_tracks}

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='tag_move.html')
    @cherrypy.tools.authenticated()
    def move(self, ids, artists, albums, tracks, dates, numbers, yes = False, no = False):

        move = False

        if yes:
            move = True

        update_tracks = self.get_tracks(ids, artists, albums, tracks, dates, numbers)

        tracks, messages = library_dao.update_tracks_tags(update_tracks, move)

        return {'tracks': tracks, 'messages': messages}

    def get_tracks(self, ids, artists, albums, tracks, dates, numbers):
        if not isinstance(ids, list):
            ids = [ids]

        if not isinstance(artists, list):
            artists = [artists]

        if not isinstance(albums, list):
            albums = [albums]

        if not isinstance(tracks, list):
            tracks = [tracks]

        if not isinstance(dates, list):
            dates = [dates]

        if not isinstance(numbers, list):
            numbers = [numbers]

        update_tracks = []

        for index, id in enumerate(ids):
            update_tracks.append({
                "id": id,
                "artist": artists[index],
                "album": albums[index],
                "track": tracks[index],
                "date": dates[index],
                "number": numbers[index]
            })

        return update_tracks


class Remove:
    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def album(self, id):
        album = (cherrypy.request.database.query(Album)
            .filter_by(id=id).one())

        artists = library_dao.remove_album(album)

        messages.success('Removed album "%s"' % album.name)

        if len(artists) == 1:
            raise HTTPRedirect('/artist/%s' % artists[0].slug)
        else:
            raise HTTPRedirect('/library')


class Upload:
    @cherrypy.expose
    @cherrypy.tools.jinja(filename='upload.html')
    @cherrypy.tools.authenticated()
    def default(self):
        return {}

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='upload_add.html')
    @cherrypy.tools.authenticated()
    def add(self):

        filename = cherrypy.request.headers.elements('content-disposition')[0].params['filename']

        if filename.startswith('"') and filename.endswith('"'):
            filename = filename[1:-1]

        filename = unquote(filename)

        ext = os.path.splitext(filename)[1].lower()[1:]

        tempdir = tempfile.mkdtemp()

        filename = os.path.join(tempdir, filename)

        filenames = []

        rarfile.PATH_SEP = '/'

        with open(filename, 'wb') as fileobj:
            fileobj.write(cherrypy.request.rfile.read())

        if ext == "zip":
            zip = ZipFile(filename)
            zip.extractall(tempdir)

            for name in zip.namelist():
                filenames.append(os.path.join(tempdir, name).encode('utf8'))
        elif ext == "rar":
            rar = RarFile(filename)
            rar.extractall(tempdir)

            for name in rar.namelist():
                filenames.append(os.path.join(tempdir, name).encode('utf8'))
        else:
            filenames.append(filename.encode('utf8'))

        for filename in filenames:
            # update modified time to now, we don't want the time from the zip
            # archive or whatever
            os.utime(filename, None)

        tracks, messages = library_dao.add_files(filenames, move = True)

        shutil.rmtree(tempdir)

        return {'tracks': tracks, 'messages': messages}

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

class You:
    lastfm = Lastfm()

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='you.html')
    def default(self):
        return {}

class Users:
    you = You()

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

        queues = queue_dao.get_queues(user.id)

        lastfm_user = lastfm.get_user(user.lastfm_user)

        return {
            'user': user,
            'queues': queues,
            'lastfm_user': lastfm_user
        }

class Queue:

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='queue.html')
    def list(self):
        user_id = cherrypy.request.user.id
        return {'queues': queue_dao.get_queues(user_id)}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def add(self, slug):
        queue_dao.add_track(slug)

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def add_album(self, slug):
        queue_dao.add_album(slug)

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def remove(self, slug):
        queue_dao.remove_track(slug)

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def clear(self, what = None):
        if what is not None and what == 'played':
            queue_dao.clear_played()
        else:
            queue_dao.clear()


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
    upload = Upload()
    remove = Remove()
    tag = Tag()
    users = Users()

    @cherrypy.expose
    @cherrypy.tools.multiheaders()
    def logout(self):
        who_api = get_api(cherrypy.request.wsgi_environ)

        headers = who_api.forget()

        cherrypy.response.multiheaders = headers

        raise HTTPRedirect('/')

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

                if came_from is not None:
                    raise HTTPRedirect(came_from)
                else:
                    raise HTTPRedirect('/')

        return {}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='search.html')
    def search(self, query, type = None):

        artists = Artist.search_query(query).all()
        albums = None
        tracks = None

        # only search for artists
        if type == 'artist':
            albums = []
            tracks = []

        if albums is None:
            albums = Album.search_query(query).all()

        if tracks is None:
            tracks = Track.search_query(query).all()

        if len(artists) + len(albums) + len(tracks) == 1:
            for artist in artists:
                raise HTTPRedirect('/artist/%s' % artist.slug)
            for album in albums:
                raise HTTPRedirect('/album/%s/%s' % (album.artists[0].slug, album.slug))
            for track in tracks:
                raise HTTPRedirect('/track/%s' % track.slug)

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
    def index(self):
        if cherrypy.request.user is None:
            raise cherrypy.InternalRedirect('/index_unauth')
        else:
            raise cherrypy.InternalRedirect('/index_auth')

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='index_unauth.html')
    def index_unauth(self):
        return {}

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='index_auth.html')
    def index_auth(self):
        return {}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='track.html')
    def track(self, slug):
        track = library_dao.get_track_by_slug(slug)

        if track is None:
            raise cherrypy.NotFound()

        lastfm_artist = lastfm.get_artist(track.artist.name)
        lastfm_album = lastfm.get_album(track.artist.name, track.album.name)

        return {
            'track': track,
            'artist': track.artist,
            'lastfm_album': lastfm_album,
            'lastfm_artist': lastfm_artist
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def cover(self, slug):
        album = library_dao.get_album_by_slug(slug)

        if album is None or album.cover_path is None:
            raise cherrypy.NotFound()

        return cherrypy.lib.static.serve_file(album.cover_path.decode('utf8', 'replace'))

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='album.html')
    def album(self, artist_slug, album_slug):
        artist = library_dao.get_artist_by_slug(artist_slug)
        album = library_dao.get_album_by_slug(album_slug)

        if artist is None or album is None:
            raise cherrypy.NotFound()

        lastfm_artist = lastfm.get_artist(artist.name)
        lastfm_album = lastfm.get_album(artist.name, album.name)

        return {
            'artist': artist,
            'album': album,
            'lastfm_album': lastfm_album,
            'lastfm_artist': lastfm_artist
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='artist.html')
    def artist(self, slug):
        artist = library_dao.get_artist_by_slug(slug)

        if artist is None:
            raise cherrypy.NotFound()

        lastfm_artist = lastfm.get_artist(artist.name)

        namesakes = set()

        for query in artist.name.split(' '):
            if len(re.sub("[^a-zA-Z0-9]+", '', query)) > 4:
                for artist_result in Artist.search_query(query).all():
                    if artist != artist_result:
                        namesakes.add(artist_result)
                        if len(namesakes) >= 5:
                            break

        return {
            'lastfm_artist': lastfm_artist,
            'artist': artist,
            'namesakes': namesakes
        }

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
    def library(self, page = None):
        users = cherrypy.request.database.query(User).all()

        if page is None:
            page = 1

        page = int(page)

        page_size = 18

        offset = page_size * (page - 1)

        showcase_albums = library_dao.get_new_albums(page_size, offset)

        return {'showcase_albums': showcase_albums, 'page': page}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='play.m3u')
    def play_m3u(self):
        cherrypy.response.headers['Content-Type'] = 'audio/x-mpegurl'

        cookies = get_cookies(cherrypy.request.wsgi_environ)
        # TODO use "cookie_name" prop from authtkt plugin...
        auth_tkt = cookies.get('auth_tkt').value

        if cherrypy.request.app.config.get('opmuse').get('stream.ssl') == False:
            scheme = 'http'
        else:
            scheme = cherrypy.request.scheme

        host = cherrypy.request.headers.get('X-Forwarded-Host')

        if host is None:
            host = cherrypy.request.headers.get('host')

        url = "%s://%s/stream?auth_tkt=%s" % (scheme, host, auth_tkt)

        cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=play.m3u'

        return {'url': url }

    @cherrypy.expose
    @cherrypy.tools.transcodingsubprocess()
    @cherrypy.tools.authenticated()
    @cherrypy.config(**{'response.stream': True})
    def stream(self, **kwargs):

        user_id = cherrypy.request.user.id

        track = queue_dao.get_next_track(user_id, repeat = False)

        if track is None:
            raise cherrypy.HTTPError(status=409)

        user_agent = cherrypy.request.headers['User-Agent']

        transcoder, format = transcoding.determine_transcoder(
            track,
            user_agent,
            [accept.value for accept in cherrypy.request.headers.elements('Accept')]
        )

        cherrypy.log(
            '%s is streaming "%s" in %s (original was %s) with "%s"' %
            (cherrypy.request.user.login, track, format, track.format, user_agent)
        )

        cherrypy.response.headers['Content-Type'] = format

        def track_generator():
            yield track

        return transcoding.transcode(track_generator(), transcoder)

