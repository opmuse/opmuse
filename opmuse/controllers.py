import os
import re
import datetime
import cherrypy
import tempfile
import shutil
import rarfile
import mimetypes
import base64
import mmh3
import random
from urllib.request import urlretrieve
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
from opmuse.library import Artist, Album, Track, TrackPath, library_dao, LibraryProcess
from opmuse.security import User, hash_password
from opmuse.messages import messages
from opmuse.utils import HTTPRedirect
from opmuse.image import image as image_service
from opmuse.search import search
from opmuse.ws import WsController
from opmuse.wikipedia import wikipedia
from opmuse.remotes import remotes


class Edit:
    @cherrypy.expose
    @cherrypy.tools.jinja(filename='library/edit.html')
    @cherrypy.tools.authenticated()
    def default(self, ids = ''):
        ids = ids.split(',')

        tracks = library_dao.get_tracks_by_ids(ids)

        return {'tracks': tracks}

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='library/edit_submit.html')
    @cherrypy.tools.authenticated()
    def submit(self, ids, artists, albums, tracks, dates, numbers, discs, yes = False, no = False):

        move = False

        if yes:
            move = True

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

        if not isinstance(discs, list):
            discs = [discs]

        update_tracks = []

        for index, id in enumerate(ids):
            update_tracks.append({
                "id": id,
                "artist": artists[index],
                "album": albums[index],
                "track": tracks[index],
                "date": dates[index],
                "number": numbers[index],
                "disc": discs[index]
            })

        tracks, messages = library_dao.update_tracks_tags(update_tracks, move)

        return {'tracks': tracks, 'messages': messages}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def move(self, ids, where = None):

        filenames = []

        for id in ids.split(','):
            if id == "":
                continue

            track_paths = cherrypy.request.database.query(TrackPath).filter_by(track_id=id).all()

            for track_path in track_paths:
                filenames.append(track_path.path)
                cherrypy.request.database.delete(track_path.track)

        cherrypy.request.database.commit()

        if where == "va":
            artist_name = 'Various Artists'
        else:
            artist_name = None

        tracks, messages = library_dao.add_files(
            filenames, move = True, remove_dirs = True, artist_name = artist_name
        )

        raise HTTPRedirect('/%s/%s' % (tracks[0].artist.slug, tracks[0].album.slug))


class Remove:
    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def default(self, ids):
        artist = album = None

        for id in ids.split(','):
            if id == "":
                continue

            artist, album = library_dao.remove(id)

        if album is not None:
            raise HTTPRedirect('/%s/%s' % (artist.slug, album.slug))
        elif artist is not None:
            raise HTTPRedirect('/%s' % artist.slug)
        else:
            raise HTTPRedirect('/library/albums/new')


class Upload:
    @cherrypy.expose
    @cherrypy.tools.jinja(filename='library/upload.html')
    @cherrypy.tools.authenticated()
    def default(self):
        return {}

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='library/upload_add.html')
    @cherrypy.tools.authenticated()
    def add(self, archive_password = None):

        if archive_password is not None and len(archive_password) == 0:
            archive_password = None

        content_disposition = cherrypy.request.headers.get('content-disposition')

        filename = content_disposition[content_disposition.index('filename=') + 9:]

        if filename.startswith('"') and filename.endswith('"'):
            filename = filename[1:-1]

        filename = unquote(filename)

        ext = os.path.splitext(filename)[1].lower()[1:]

        tempdir = tempfile.mkdtemp()

        filename = os.path.join(tempdir, filename)

        filenames = []

        rarfile.PATH_SEP = '/'

        messages = []

        with open(filename, 'wb') as fileobj:
            fileobj.write(cherrypy.request.rfile.read())

        if ext == "zip":
            try:
                zip = ZipFile(filename)

                if archive_password is not None:
                    zip.setpassword(archive_password.encode())

                zip.extractall(tempdir)

                for name in zip.namelist():
                    # ignore hidden files, e.g. OSX archive weird and such
                    if name.startswith("."):
                        continue

                    filenames.append(os.path.join(tempdir, name).encode('utf8'))

            except Exception as error:
                messages.append("%s: %s" % (os.path.basename(filename), error))

        elif ext == "rar":
            try:
                rar = RarFile(filename)

                if archive_password is None and rar.needs_password():
                    messages.append("%s needs password but none provided." % os.path.basename(filename))
                else:
                    if archive_password is not None:
                        rar.setpassword(archive_password)

                    rar.extractall(tempdir)

                    for name in rar.namelist():
                        if name.startswith("."):
                            continue

                        filenames.append(os.path.join(tempdir, name).encode('utf8'))

            except Exception as error:
                messages.append("%s: %s" % (os.path.basename(filename), error))

        else:
            filenames.append(filename.encode('utf8'))

        for filename in filenames:
            # update modified time to now, we don't want the time from the zip
            # archive or whatever
            os.utime(filename, None)

        tracks, add_files_messages = library_dao.add_files(filenames, move = True, remove_dirs = False)

        messages += add_files_messages

        shutil.rmtree(tempdir)

        return {'tracks': tracks, 'messages': messages}


class You:

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='users/you_lastfm.html')
    @cherrypy.tools.authenticated()
    def lastfm(self):

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
                    raise HTTPRedirect('/users/you/lastfm')
            else:
                session_key = SessionKey()
                auth_url = session_key.get_auth_url()
                cherrypy.session['lastfm_session_key'] = session_key

        return {
            'auth_url': auth_url,
            'new_auth': new_auth
        }

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='users/you_settings.html')
    @cherrypy.tools.authenticated()
    def settings(self):
        return {"user": cherrypy.request.user}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def settings_submit(self, login = None, mail = None, password1 = None, password2 = None):

        user = cherrypy.request.user

        if mail == '':
            mail = None

        if password1 == '':
            password1 = None

        if password2 == '':
            password2 = None

        if mail is not None and user.mail != mail:
            user.mail = mail
            messages.success('Your mail was changed.')

        if password1 is not None and password2 is not None:
            if password1 != password2:
                messages.warning('The passwords do not match.')
            else:
                user.password = hash_password(password1, user.salt)
                messages.success('Your password was changed.')

        raise HTTPRedirect('/users/you/settings')


class Users:
    you = You()

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='users/users.html')
    def users(self):

        users = (cherrypy.request.database.query(User).order_by(User.login).all())

        return {'users': users}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='users/user.html')
    def user(self, login):
        try:
            user = (cherrypy.request.database.query(User)
                    .filter_by(login=login)
                    .order_by(User.login).one())
        except NoResultFound:
            raise cherrypy.NotFound()

        lastfm_user = cherrypy.request.lastfm_users.get(user)

        return {
            'user': user,
            'lastfm_user': lastfm_user
        }


class Queue:

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='queue.html')
    def list(self):
        # XXX queues is set in QueueTool
        return {}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def add(self, ids):
        queue_dao.add_tracks(ids.split(','))

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def remove(self, ids):
        queue_dao.remove_tracks(ids.split(','))

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def clear(self, what = None):
        if what is not None and what == 'played':
            queue_dao.clear_played()
        else:
            queue_dao.clear()


class Styles(object):
    @cherrypy.expose
    def default(self, *args, **kwargs):
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


class Library(object):
    upload = Upload()
    edit = Edit()

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='library/track.html')
    def track(self, slug):
        track = library_dao.get_track_by_slug(slug)

        if track is None:
            raise cherrypy.NotFound()

        remotes.update_track(track)

        remotes_artist = remotes.get_artist(track.artist)
        remotes_album = remotes.get_album(track.album)
        remotes_track = remotes.get_track(track)

        return {
            'track': track,
            'remotes_artist': remotes_artist,
            'remotes_album': remotes_album,
            'remotes_track': remotes_track,
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='library/album.html')
    def album(self, artist_slug, album_slug):
        album = library_dao.get_album_by_slug(album_slug)

        if album is None:
            raise cherrypy.NotFound()

        remotes.update_album(album)

        remotes_artists = []

        for artist in album.artists:
            remotes.update_artist(artist)
            remotes_artists.append(remotes.get_artist(artist))

        for track in album.tracks:
            remotes.update_track(track)

        remotes_album = remotes.get_album(album)

        dirs = {}

        for track in album.tracks:
            if track.paths[0].pretty_dir not in dirs:
                dirs[track.paths[0].pretty_dir] = []

            dirs[track.paths[0].pretty_dir].append(track)

        dirs = sorted(dirs.items(), key = lambda d: d[0])

        # calculate colspan here and not in template because jinja makes it really difficult
        colspan = 4

        if len(album.artists) > 1:
            colspan += 1

        for track in album.tracks:
            if track.invalid:
                colspan += 1
                break

        disc = False

        for track in album.tracks:
            if track.disc is not None:
                disc = True
                colspan += 1
                break

        return {
            'album': album,
            'dirs': dirs,
            'remotes_artists': remotes_artists,
            'remotes_album': remotes_album,
            'colspan': colspan,
            'disc': disc
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='library/tracks.html')
    def tracks(self, view, page = None):
        if page is None:
            page = 1

        page = int(page)

        page_size = 18

        offset = page_size * (page - 1)

        tracks = []

        return {'tracks': tracks, 'page': page, 'view': view}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='library/artists.html')
    def artists(self, view, page = None):
        if page is None:
            page = 1

        page = int(page)

        page_size = 18

        offset = page_size * (page - 1)

        if view == "new":
            artists = library_dao.get_artists(page_size, offset)
        elif view == "random":
            artists = library_dao.get_random_artists(page_size)
            page = None
        elif view == "yours":
            artists = []

            lastfm_user = cherrypy.request.lastfm_users.get(cherrypy.request.user)

            if lastfm_user is not None:
                index = 0

                for artist in lastfm_user['top_artists_overall']:
                    artist_results = search.query_artist(artist['name'])

                    if len(artist_results) > 0:
                        artists.append(artist_results[0])

            page = None
        else:
            artists = library_dao.get_invalid_artists(page_size, offset)

        for artist in artists:
            remotes.update_artist(artist)

            for album in artist.albums:
                remotes.update_album(album)

        return {'artists': artists, 'page': page, 'view': view}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='library/albums.html')
    def albums(self, view, page = None):

        if page is None:
            page = 1

        page = int(page)

        page_size = 18

        offset = page_size * (page - 1)

        if view == "new":
            albums = library_dao.get_new_albums(page_size, offset)
        elif view == "random":
            albums = library_dao.get_random_albums(page_size)
            page = None
        elif view == "va":
            albums = library_dao.get_va_albums(page_size, offset)
        elif view == "yours":
            albums = []

            lastfm_user = cherrypy.request.lastfm_users.get(cherrypy.request.user)

            if lastfm_user is not None:
                index = 0

                for album in lastfm_user['top_albums_overall']:
                    album_results = search.query_album(album['name'])

                    if len(album_results) > 0:
                        albums.append(album_results[0])

            page = None
        else:
            albums = library_dao.get_invalid_albums(page_size, offset)

        for album in albums:
            remotes.update_album(album)

            for artist in album.artists:
                remotes.update_artist(artist)

        return {'albums': albums, 'page': page, 'view': view}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='library/artist.html')
    def artist(self, slug):
        artist = library_dao.get_artist_by_slug(slug)

        if artist is None:
            raise cherrypy.NotFound()

        remotes.update_artist(artist)

        for album in artist.albums:
            remotes.update_album(album)

        remotes_artist = remotes.get_artist(artist)

        namesakes = set()

        for query in artist.name.split(' '):
            if len(re.sub("[^a-zA-Z0-9]+", '', query)) > 4:
                for artist_result in search.query_artist(query):
                    if artist != artist_result:
                        namesakes.add(artist_result)
                        if len(namesakes) >= 5:
                            break

        return {
            'artist': artist,
            'remotes_artist': remotes_artist,
            'namesakes': namesakes
        }


class Root(object):
    styles = Styles()
    queue = Queue()
    remove = Remove()
    users = Users()
    library = Library()
    ws = WsController()

    @cherrypy.expose
    def __profile__(self, *args, **kwargs):
        return b'Profiler is disabled, enable it with --profile'

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
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='search.html')
    def search(self, query, type = None):

        artists = search.query_artist(query)
        albums = None
        tracks = None

        # only search for artists
        if type == 'artist':
            albums = []
            tracks = []

        if albums is None:
            albums = search.query_album(query)

        if tracks is None:
            tracks = search.query_track(query)

        if len(artists) + len(albums) + len(tracks) == 1:
            for artist in artists:
                raise HTTPRedirect('/%s' % artist.slug)
            for album in albums:
                raise HTTPRedirect('/%s/%s' % (album.artists[0].slug, album.slug))
            for track in tracks:
                raise HTTPRedirect('/library/track/%s' % track.slug)

        results = OrderedDict({})

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
    @cherrypy.tools.jinja(filename='index_auth.html')
    def index_auth(self):

        artist_names = set()

        users = (cherrypy.request.database.query(User)
                 .order_by(User.login).limit(8).all())

        for user in users:
            if user.lastfm_user is None:
                continue

            lastfm_user = cherrypy.request.lastfm_users.get(user)

            if lastfm_user is None:
                continue

            for recent_track in lastfm_user['recent_tracks']:
                artist_names.add(recent_track['artist'])

        artist_names = list(artist_names)

        random.shuffle(artist_names)

        artists = []

        index = 0

        for artist_name in artist_names:
            results = search.query_artist(artist_name)

            if len(results) > 0:
                artists.append(results[0])

                index += 1

                if index >= 16:
                    break

        return {'users': users, 'artists': artists}

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def cover(self, type, slug, hash = None):

        cover = self.get_cover(type, slug)

        if cover is None:
            cherrypy.response.headers['Content-Type'] = 'image/png'

            return cherrypy.lib.static.serve_file(os.path.join(
                os.path.abspath(os.path.dirname(__file__)),
                '..', 'public', 'images', 'cover_placeholder.png'
            ))
        else:
            return cover

    def get_cover(self, type, slug):
        entity = None

        if type == "album":
            entity = library_dao.get_album_by_slug(slug)

            if entity is None:
                raise cherrypy.NotFound()

            for artist in entity.artists:
                if artist.cover_path is None:
                    cherrypy.engine.bgtask.put(self.fetch_artist_cover, artist.id)

            if entity.cover_path is None or not os.path.exists(entity.cover_path):
                entity.cover_path = None
                cherrypy.engine.bgtask.put(self.fetch_album_cover, entity.id)
                for artist in entity.artists:
                    if artist.cover is not None:
                        cherrypy.response.headers['Content-Type'] = self.guess_mime(artist)
                        return artist.cover

        elif type == "artist":
            entity = library_dao.get_artist_by_slug(slug)

            if entity is None:
                raise cherrypy.NotFound()

            if entity.cover_path is None or not os.path.exists(entity.cover_path):
                entity.cover_path = None
                cherrypy.engine.bgtask.put(self.fetch_artist_cover, entity.id)

        if entity is None:
            raise cherrypy.NotFound()

        if entity.cover_path is not None:
            if entity.cover is None:
                cover_ext = os.path.splitext(entity.cover_path)[1].decode('utf8')
                temp_cover = tempfile.mktemp(cover_ext).encode('utf8')

                if image_service.resize(entity.cover_path, temp_cover, 220):

                    with open(temp_cover, 'rb') as file:
                        entity.cover = file.read()
                        entity.cover_hash = base64.b64encode(mmh3.hash_bytes(entity.cover))

                    os.remove(temp_cover)

            cherrypy.response.headers['Content-Type'] = self.guess_mime(entity)

            return entity.cover

    def guess_mime(self, entity):
        mimetype = mimetypes.guess_type(entity.cover_path.decode('utf8', 'replace'))
        return mimetype[0] if mimetype is not None else 'image/jpeg'

    def fetch_album_cover(self, album_id, _database):
        album = _database.query(Album).filter_by(id=album_id).one()

        artist = album.artists[0]

        lastfm_album = lastfm.get_album(artist.name, album.name)

        if lastfm_album is None or lastfm_album['cover'] is None:
            return

        cover, resize_cover, cover_ext = self.retrieve_and_resize(lastfm_album['cover'])

        track_dirs = set()

        for track in album.tracks:
            for path in track.paths:
                track_dirs.add(os.path.dirname(path.path))

        for track_dir in track_dirs:
            if not os.path.exists(track_dir):
                os.makedirs(track_dir)

            cover_dest = os.path.join(
                track_dir, ('%s%s' % (album.slug, cover_ext)).encode('utf8')
            )

            if not os.path.exists(cover_dest):
                with open(cover_dest, 'wb') as file:
                    file.write(cover)

            album.cover_path = cover_dest

        album.cover = resize_cover
        album.cover_hash = base64.b64encode(mmh3.hash_bytes(album.cover))

        _database.commit()

    def retrieve_and_resize(self, image_url):
        image_ext = os.path.splitext(image_url)[1]

        album_dirs = set()

        temp_image = tempfile.mktemp(image_ext).encode('utf8')
        resize_temp_image = tempfile.mktemp(image_ext).encode('utf8')
        urlretrieve(image_url, temp_image)

        if not image_service.resize(temp_image, resize_temp_image, 220):
            os.remove(temp_image)
            os.remove(resize_temp_image)
            return None

        resize_image = None
        image = None

        with open(resize_temp_image, 'rb') as file:
            resize_image = file.read()

        os.remove(resize_temp_image)

        with open(temp_image, 'rb') as file:
            image = file.read()

        os.remove(temp_image)

        return image, resize_image, image_ext

    def fetch_artist_cover(self, artist_id, _database):
        artist = (_database.query(Artist).filter_by(id=artist_id).one())

        lastfm_artist = lastfm.get_artist(artist.name)

        if lastfm_artist is None or lastfm_artist['cover'] is None:
            return

        cover, resize_cover, cover_ext = self.retrieve_and_resize(lastfm_artist['cover'])

        track_dirs = set()

        for album in artist.albums:
            for track in album.tracks:
                for path in track.paths:
                    track_dirs.add(os.path.dirname(path.path))

        for track_dir in track_dirs:

            if not os.path.exists(track_dir):
                os.makedirs(track_dir)

            cover_dest = os.path.join(
                track_dir, ('%s%s' % (artist.slug, cover_ext)).encode('utf8')
            )

            if not os.path.exists(cover_dest):
                with open(cover_dest, 'wb') as file:
                    file.write(cover)

            artist.cover_path = cover_dest

        artist.cover = resize_cover
        artist.cover_hash = base64.b64encode(mmh3.hash_bytes(artist.cover))

        _database.commit()

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    @cherrypy.tools.jinja(filename='play.m3u')
    def play_m3u(self):
        cherrypy.response.headers['Content-Type'] = 'audio/x-mpegurl'

        cookies = get_cookies(cherrypy.request.wsgi_environ)
        # TODO use "cookie_name" prop from authtkt plugin...
        auth_tkt = cookies.get('auth_tkt').value

        if cherrypy.request.app.config.get('opmuse').get('stream.ssl') is False:
            scheme = 'http'
        else:
            scheme = cherrypy.request.scheme

        forwarded_host = cherrypy.request.headers.get('X-Forwarded-Host')

        if forwarded_host is not None:
            host = forwarded_host.split(",")[0].strip()
        else:
            host = cherrypy.request.headers.get('host')

        url = "%s://%s/stream?auth_tkt=%s" % (scheme, host, auth_tkt)

        cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=play.m3u'

        return {'url': url}

    @cherrypy.expose
    @cherrypy.tools.transcodingsubprocess()
    @cherrypy.tools.authenticated()
    @cherrypy.config(**{'response.stream': True})
    def stream(self, **kwargs):

        user_id = cherrypy.request.user.id

        queue = queue_dao.get_next(user_id)

        if queue is None:
            raise cherrypy.HTTPError(status=409)

        user_agent = cherrypy.request.headers['User-Agent']

        transcoder, format = transcoding.determine_transcoder(
            queue.track,
            user_agent,
            [accept.value for accept in cherrypy.request.headers.elements('Accept')]
        )

        cherrypy.log(
            '%s is streaming "%s" in %s (original was %s) with "%s"' %
            (cherrypy.request.user.login, queue.track, format, queue.track.format, user_agent)
        )

        cherrypy.response.headers['Content-Type'] = format

        def track_generator():
            yield queue.track, queue.current_seconds

        return transcoding.transcode(track_generator(), transcoder)
