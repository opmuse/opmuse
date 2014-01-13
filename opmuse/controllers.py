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
import re
import datetime
import cherrypy
import tempfile
import shutil
import rarfile
import random
import math
import time
import mimetypes
import string
from datetime import timedelta
from urllib.parse import unquote
from zipfile import ZipFile
from rarfile import RarFile
from repoze.who.api import get_api
from repoze.who._compat import get_cookies
from collections import OrderedDict
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm import joinedload, undefer
from sqlalchemy import func, distinct, or_
from opmuse.queues import queue_dao
from opmuse.transcoding import transcoding
from opmuse.lastfm import SessionKey, lastfm, LastfmError
from opmuse.library import (Album, Artist, Track, TrackPath, library_dao,
                            Library as LibraryService, TrackStructureParser)
from opmuse.security import User, Role, hash_password
from opmuse.messages import messages
from opmuse.utils import HTTPRedirect
from opmuse.search import search
from opmuse.ws import WsController
from opmuse.wikipedia import wikipedia
from opmuse.remotes import remotes
from opmuse.covers import covers
from opmuse.jinja import render_template
from opmuse.database import get_database
from opmuse.cache import cache
from opmuse.sizeof import total_size


class Edit:
    @cherrypy.expose
    @cherrypy.tools.jinja(filename='library/edit.html')
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.authorize(roles=['admin'])
    def default(self, ids = ''):
        ids = ids.split(',')

        tracks = library_dao.get_tracks_by_ids(ids)

        return {'tracks': tracks}

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='library/edit_result.html')
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.authorize(roles=['admin'])
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

        tracks = Edit._sort_tracks(tracks)

        hierarchy = Library._produce_track_hierarchy(tracks)

        return {'hierarchy': hierarchy, 'messages': messages}

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='library/edit_result.html')
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.authorize(roles=['admin'])
    def move(self, ids, where = None):

        filenames = []

        ids = ids.split(',')

        for id in ids:
            if id == "":
                continue

            track_paths = get_database().query(TrackPath).filter_by(track_id=id).all()

            for track_path in track_paths:
                filenames.append(track_path.path)
                get_database().delete(track_path.track)

        get_database().commit()

        if where == "va":
            artist_name = 'Various Artists'
        else:
            artist_name = None

        tracks, messages = library_dao.add_files(
            filenames, move = True, remove_dirs = True, artist_name_override = artist_name
        )

        tracks = Edit._sort_tracks(tracks)

        hierarchy = Library._produce_track_hierarchy(tracks)

        return {'hierarchy': hierarchy, 'messages': messages}

    @staticmethod
    def _sort_tracks(tracks):
        return sorted(tracks, key = lambda track: (
                      track.artist.name if track.artist is not None else '',
                      track.album.name if track.album is not None else '',
                      track.number if track.number is not None else '0',
                      track.name))


class Remove:
    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='remove/modal.html')
    def modal(self, ids, title = None):
        ids = ids.split(',')

        tracks = library_dao.get_tracks_by_ids(ids)

        if title is None:
            title = ''

        return {
            'tracks': tracks,
            'title': title
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    def default(self, ids):
        artist = album = None

        for id in ids.split(','):
            if id == "":
                continue

            artist, album = library_dao.remove(id)

        if album is not None and artist is not None:
            raise HTTPRedirect('/%s/%s' % (artist.slug, album.slug))
        elif artist is not None:
            raise HTTPRedirect('/%s' % artist.slug)
        elif album is not None:
            raise HTTPRedirect('/unknown/%s' % album.slug)
        else:
            raise HTTPRedirect('/library/albums')


class Search:
    CACHE_RECENT_KEY = "search_recent"
    MAX_RECENT = 10

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.json_out()
    def api(self, type, query):
        if type == "artist":
            entities = search.query_artist(query)
        elif type == "album":
            entities = search.query_album(query)
        elif type == "track":
            entities = search.query_track(query)
        else:
            raise cherrypy.NotFound()

        return [entity.name for entity in entities]

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='library/search.html')
    def default(self, query = None, type = None):
        artists = []
        albums = []
        tracks = []
        track_ids = []

        hierarchy = None

        album_track_ids = set()

        recent_searches = []

        if query is not None:
            albums = None
            tracks = None

            # only search for artists
            if type == 'artist':
                artists = search.query_artist(query, exact=True)
                albums = []
                tracks = []
            else:
                artists = search.query_artist(query)

            if albums is None:
                albums = search.query_album(query)

            if tracks is None:
                tracks = search.query_track(query)

            for artist in artists:
                remotes.update_artist(artist)

            for album in albums:
                remotes.update_album(album)

            for track in tracks:
                track_ids.append(track.id)
                remotes.update_track(track)

            entities = artists + albums + tracks

            if len(entities) == 1:
                for artist in artists:
                    raise HTTPRedirect('/%s' % artist.slug)
                for album in albums:
                    raise HTTPRedirect('/%s/%s' % (album.artists[0].slug, album.slug))
                for track in tracks:
                    raise HTTPRedirect('/library/track/%s' % track.slug)

            if cache.has(Search.CACHE_RECENT_KEY):
                recent_searches = cache.get(Search.CACHE_RECENT_KEY)
            else:
                cache.set(Search.CACHE_RECENT_KEY, recent_searches)

            if type is None and len(entities) > 0:
                if len(recent_searches) == 0 or query != recent_searches[0][0]:
                    recent_searches.insert(0, (query, datetime.datetime.now(), cherrypy.request.user.login))

                    if len(recent_searches) > Search.MAX_RECENT:
                        recent_searches.pop()

            entities = sorted(entities, key=lambda entity: entity.__SEARCH_SCORE, reverse=True)

            hierarchy = Library._produce_track_hierarchy(entities)

            for key, result_artist in hierarchy['artists'].items():
                for key, result_album in result_artist['albums'].items():
                    for track_id in library_dao.get_track_ids_by_album_id(result_album['entity'].id):
                        album_track_ids.add(track_id)

        return {
            'query': query,
            'hierarchy': hierarchy,
            'tracks': tracks,
            'albums': albums,
            'artists': artists,
            'track_ids': track_ids,
            'album_track_ids': list(album_track_ids),
            'recent_searches': recent_searches
        }


class Upload:
    @cherrypy.expose
    @cherrypy.tools.jinja(filename='library/upload.html')
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.authorize(roles=['admin'])
    def default(self):
        return {}

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='library/upload_add.html')
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.authorize(roles=['admin'])
    def add(self, archive_password = None, audio_file = None, start = "false", session = None):

        CACHE_KEY = "UPLOAD_TRACKS_%d_%s" % (cherrypy.request.user.id, session)

        all_tracks = None

        if start == "true":
            all_tracks = []
            cache.set(CACHE_KEY, all_tracks)
        else:
            if not cache.has(CACHE_KEY):
                raise cherrypy.HTTPError(status=409)
            else:
                all_tracks = cache.get(CACHE_KEY)

        if audio_file is not None and len(audio_file) == 0:
            audio_file = None

        if archive_password is not None and len(archive_password) == 0:
            archive_password = None

        content_disposition = cherrypy.request.headers.get('content-disposition')

        filename = content_disposition[content_disposition.index('filename=') + 9:]

        if filename.startswith('"') and filename.endswith('"'):
            filename = filename[1:-1]

        filename = unquote(filename)

        ext = os.path.splitext(filename)[1].lower()[1:]
        basename = os.path.splitext(filename)[0]

        tempdir = tempfile.mkdtemp()

        path = os.path.join(tempdir, filename)

        paths = []

        rarfile.PATH_SEP = '/'

        messages = []

        with open(path, 'wb') as fileobj:
            fileobj.write(cherrypy.request.rfile.read())

        artist_name_fallback = None

        # this file is a regular file that belongs to an audio_file
        if audio_file is not None:
            track = None
            tries = 0

            # try and sleep until we get the track.. this will almost always
            # be needed because of the async upload.
            while track is None and tries < 10:
                track = library_dao.get_track_by_filename(audio_file.encode('utf8'))
                tries += 1

                if track is None:
                    time.sleep(3)

            if track is None:
                messages.append("Skipping %s, couldn't find its corresponding track %s." %
                                (filename, audio_file))
            else:
                track_structure = TrackStructureParser(track)
                track_path = track_structure.get_path(absolute=True)
                relative_track_path = track_structure.get_path(absolute=False).decode('utf8', 'replace')

                new_path = os.path.join(track_path, filename.encode('utf8'))

                if os.path.exists(new_path):
                    messages.append("Skipping %s, already exists in %s." % (filename, relative_track_path))
                else:
                    shutil.move(path.encode('utf8'), new_path)
                    messages.append("Uploaded %s to %s." % (filename, relative_track_path))

        elif ext == "zip":
            # set artist name fallback to zip's name so if it's missing artist tags
            # it's easily distinguishable and editable so it can be fixed after upload.
            artist_name_fallback = basename

            try:
                zip = ZipFile(path)

                if archive_password is not None:
                    zip.setpassword(archive_password.encode())

                zip.extractall(tempdir)

                for name in zip.namelist():
                    # ignore hidden files, e.g. OSX archive weird and such
                    if name.startswith("."):
                        continue

                    paths.append(os.path.join(tempdir, name).encode('utf8'))

            except Exception as error:
                messages.append("%s: %s" % (os.path.basename(path), error))

        elif ext == "rar":
            # look at corresponding ext == zip comment...
            artist_name_fallback = basename

            try:
                rar = RarFile(path)

                if archive_password is None and rar.needs_password():
                    messages.append("%s needs password but none provided." % os.path.basename(path))
                else:
                    if archive_password is not None:
                        rar.setpassword(archive_password)

                    rar.extractall(tempdir)

                    for name in rar.namelist():
                        if name.startswith("."):
                            continue

                        paths.append(os.path.join(tempdir, name).encode('utf8'))

            except Exception as error:
                messages.append("%s: %s" % (os.path.basename(path), error))

        # this is a plain audio file
        else:
            for comp in basename.split('-'):
                comp = comp.strip()

                if not re.search(r'^[0-9]+$', comp):
                    artist_name_fallback = comp
                    break

            paths.append(path.encode('utf8'))

        for path in paths:
            # update modified time to now, we don't want the time from the zip
            # archive or whatever
            os.utime(path, None)

        if len(paths) > 0:
            tracks, add_files_messages = library_dao.add_files(paths, move = True, remove_dirs = False,
                                                               artist_name_fallback = artist_name_fallback)
            messages += add_files_messages
        else:
            tracks = []

        shutil.rmtree(tempdir)

        for track in tracks:
            track.upload_user = cherrypy.request.user

            all_tracks.append(track.id)

            if track.album is not None:
                remotes.update_album(track.album)

            if track.artist is not None:
                remotes.update_artist(track.artist)

            remotes.update_track(track)

        hierarchy = Library._produce_track_hierarchy(library_dao.get_tracks_by_ids(all_tracks))

        return {'hierarchy': hierarchy, 'messages': messages}


class You:

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='users/you_lastfm.html')
    @cherrypy.tools.authenticated(needs_auth=True)
    def lastfm(self):

        auth_url = authenticated_user = new_auth = None
        need_config = False

        cache_key = 'you_lastfm_session_key_%d' % cherrypy.request.user.id

        if cherrypy.request.user.lastfm_session_key is None:
            session_key = cache.get(cache_key)

            if session_key is not None:
                auth_url = session_key.get_auth_url()
                key = session_key.get_session_key()

                if key is not None:
                    cache.set(cache_key, None)
                    cherrypy.request.user.lastfm_session_key = key
                    cherrypy.request.user.lastfm_user = lastfm.get_authenticated_user_name()
                    auth_url = None
                    new_auth = True
                    raise HTTPRedirect('/users/you/lastfm')
            else:
                try:
                    session_key = SessionKey()
                    auth_url = session_key.get_auth_url()
                    cache.set(cache_key, session_key)
                except LastfmError:
                    need_config = True

        return {
            'need_config': need_config,
            'auth_url': auth_url,
            'new_auth': new_auth
        }

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='users/you_settings.html')
    @cherrypy.tools.authenticated(needs_auth=True)
    def settings(self):
        return {"user": cherrypy.request.user}

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
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


class UsersUsers:
    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='users/users.html')
    def default(self):

        users = (get_database().query(User).order_by(User.login).all())

        for user in users:
            remotes.update_user(user)

        return {'users': users}

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.authorize(roles=['admin'])
    def add_submit(self, login = None, mail = None, roles = None, password1 = None, password2 = None):

        Users._validate_user_params(login, mail, roles, password1, password2)

        if roles is None:
            roles = []

        if isinstance(roles, str):
            roles = [roles]

        salt = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(64))
        password = hash_password(password1, salt)

        user = User(login, password, mail, salt)

        get_database().add(user)

        for role in get_database().query(Role).filter(Role.id.in_(roles)):
            role.users.append(user)

        get_database().commit()

        messages.success('User was added.')

        raise HTTPRedirect('/users/users')

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.authorize(roles=['admin'])
    @cherrypy.tools.jinja(filename='users/users_add.html')
    def add(self):
        roles = (get_database().query(Role).order_by(Role.name).all())

        return {
            'roles': roles
        }


class Users:
    you = You()
    users = UsersUsers()

    @staticmethod
    def _validate_user_params(login = None, mail = None, roles = None, password1 = None, password2 = None):
        if login is None or len(login) < 3:
            messages.warning('Login must be at least 3 chars.')
            raise cherrypy.HTTPError(status=409)

        if mail is None or len(mail) < 3:
            messages.warning('Mail must be at least 3 chars.')
            raise cherrypy.HTTPError(status=409)
            return

        if password1 is not None and password2 is not None:
            if password1 != password2:
                messages.warning('The passwords do not match.')
                raise cherrypy.HTTPError(status=409)

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='users/roles.html')
    def roles(self):
        roles = (get_database().query(Role).order_by(Role.name).all())

        return {'roles': roles}

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    def user(self, login, action = None):
        if action == "edit":
            raise cherrypy.InternalRedirect('/users/user_edit/%s' % login)
        else:
            raise cherrypy.InternalRedirect('/users/user_view/%s' % login)

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='users/user_view.html')
    def user_view(self, login):
        try:
            user = (get_database().query(User)
                    .filter_by(login=login)
                    .order_by(User.login).one())
        except NoResultFound:
            raise cherrypy.NotFound()

        remotes.update_user(user)
        remotes_user = remotes.get_user(user)

        return {
            'user': user,
            'remotes_user': remotes_user
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.authorize(roles=['admin'])
    @cherrypy.tools.jinja(filename='users/user_edit.html')
    def user_edit(self, login):
        try:
            user = (get_database().query(User)
                    .filter_by(login=login)
                    .order_by(User.login).one())
        except NoResultFound:
            raise cherrypy.NotFound()

        roles = (get_database().query(Role).order_by(Role.name).all())

        return {
            'user': user,
            'roles': roles
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.authorize(roles=['admin'])
    def user_edit_submit(self, user_id, login = None, mail = None, roles = None,
                         password1 = None, password2 = None):
        try:
            user = (get_database().query(User)
                    .filter_by(id=user_id).one())
        except NoResultFound:
            raise cherrypy.NotFound()

        Users._validate_user_params(login, mail, roles, password1, password2)

        if roles is None:
            roles = []

        if isinstance(roles, str):
            roles = [roles]

        password = hash_password(password1, user.salt)

        user.login = login
        user.mail = mail
        user.password = password

        user.roles[:] = []

        for role in get_database().query(Role).filter(Role.id.in_(roles)):
            role.users.append(user)

        get_database().commit()

        messages.success('User was edited.')

        raise HTTPRedirect('/users/users')


class Queue:

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='queue/player.html')
    def player(self):
        user = cherrypy.request.user
        queues, queue_info = queue_dao.get_queues(user.id)
        queue_current_track = queue_dao.get_current_track(user.id)

        return {
            'queues': queues,
            'queue_info': queue_info,
            'queue_current_track': queue_current_track
        }

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    @cherrypy.tools.authenticated(needs_auth=True)
    def update(self):
        queues = cherrypy.request.json['queues']

        updates = []

        for index, queue_id in enumerate(queues):
            updates.append((queue_id, {'index': index}))

        queue_dao.update_queues(updates)

        return {}

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='queue/cover.html')
    def cover(self):
        user = cherrypy.request.user
        queue_current_track = queue_dao.get_current_track(user.id)

        return {
            'queue_current_track': queue_current_track
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='queue/list.html')
    def list(self):
        user = cherrypy.request.user
        queues, queue_info = queue_dao.get_queues(user.id)
        queue_current_track = queue_dao.get_current_track(user.id)

        return {
            'queues': queues,
            'queue_info': queue_info,
            'queue_current_track': queue_current_track
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    def add_album(self, id):
        queue_dao.add_album_tracks(id)

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    def add(self, ids):
        queue_dao.add_tracks(ids.split(','))

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    def shuffle(self):
        queue_dao.shuffle()

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    def remove(self, ids):
        queue_dao.remove(ids.split(','))

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    def clear(self, what = None):
        if what is not None and what == 'played':
            queue_dao.clear_played()
        else:
            queue_dao.clear()

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    def stop(self):
        queue_dao.reset_current()


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


class Library:
    search = Search()
    upload = Upload()
    edit = Edit()

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='library/track.html')
    def track(self, slug):
        track = library_dao.get_track_by_slug(slug)

        if track is None:
            raise cherrypy.NotFound()

        remotes.update_track(track)

        remotes_album = remotes_artist = None

        if track.album is not None:
            remotes.update_album(track.album)
            remotes_album = remotes.get_album(track.album)

        if track.artist is not None:
            remotes.update_artist(track.artist)
            remotes_artist = remotes.get_artist(track.artist)

            if remotes_artist is not None and remotes_artist['lastfm'] is not None:
                for tag_name in remotes_artist['lastfm']['tags']:
                    remotes.update_tag(tag_name)

        remotes_track = remotes.get_track(track)

        return {
            'track': track,
            'remotes_artist': remotes_artist,
            'remotes_album': remotes_album,
            'remotes_track': remotes_track,
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='library/album.html')
    def album(self, artist_slug, album_slug):
        try:
            album = (get_database().query(Album)
                     # _dir_tracks() uses paths
                     .options(joinedload(Album.tracks, Track.paths))
                     .filter_by(slug=album_slug).one())
        except NoResultFound:
            raise cherrypy.NotFound()

        remotes.update_album(album)

        remotes_artists = []

        for artist in album.artists:
            remotes.update_artist(artist)
            remotes_artist = remotes.get_artist(artist)

            if remotes_artist is not None:
                remotes_artists.append(remotes_artist)

                if remotes_artist['lastfm'] is not None:
                    for tag_name in remotes_artist['lastfm']['tags']:
                        remotes.update_tag(tag_name)

        for track in album.tracks:
            remotes.update_track(track)

        remotes_album = remotes.get_album(album)

        dir_tracks = self._dir_tracks(album.tracks)

        return {
            'album': album,
            'dir_tracks': dir_tracks,
            'remotes_artists': remotes_artists,
            'remotes_album': remotes_album,
        }

    def _dir_tracks(self, tracks):
        dir_tracks = {}

        artist_covers = set()
        album_covers = set()

        for track in tracks:
            if track.artist is not None:
                artist_covers.add(track.artist.cover_path)

            if track.album is not None:
                album_covers.add(track.album.cover_path)

            dir = track.paths[0].dir

            if dir not in dir_tracks:
                dir_tracks[dir] = {
                    'tracks': [],
                    'pretty_dir': track.paths[0].pretty_dir,
                    'files': [],
                    'paths': []
                }

            dir_tracks[dir]['paths'].append(track.paths[0].path)
            dir_tracks[dir]['tracks'].append(track)

        for dir, item in dir_tracks.items():
            for file in os.listdir(dir):
                file = os.path.join(dir, file)

                if file not in item['paths']:
                    isdir = os.path.isdir(file)

                    if not isdir and LibraryService.is_supported(file):
                        track = library_dao.get_track_by_path(file)
                    else:
                        track = None

                    pretty_file = file[(len(dir) + 1):].decode("utf8", "replace")

                    if isdir:
                        pretty_file = "%s/" % pretty_file

                    if not isdir:
                        stat = os.stat(file)
                        modified = datetime.datetime.fromtimestamp(stat.st_mtime)
                        size = stat.st_size
                    else:
                        size = modified = None

                    library_path = library_dao.get_library_path()

                    relative_file = file[len(library_path):]

                    dir_tracks[dir]['files'].append({
                        "file": file,
                        "relative_file": relative_file.decode('utf8', 'replace'),
                        "modified": modified,
                        "size": size,
                        "track": track,
                        "isdir": isdir,
                        "pretty_file": pretty_file,
                        "is_album_cover": file in album_covers,
                        "is_artist_cover": file in artist_covers
                    })

            dir_tracks[dir]['files'] = sorted(dir_tracks[dir]['files'],
                                              key = lambda item: "%d%s" % (not item["isdir"], item["file"]))

        dir_tracks = sorted(dir_tracks.items(), key = lambda d: d[0])

        return dir_tracks

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='library/tracks.html')
    def tracks(self, sort = None, filter = None, page = None):
        if sort is None:
            sort = "added"

        if filter is None:
            filter = "none"

        if page is None:
            page = 1

        page = int(page)

        page_size = 70

        offset = page_size * (page - 1)

        query = get_database().query(Track).filter(Track.scanned).group_by(Track.id)

        if sort == "added":
            query = query.order_by(Track.added.desc())
        elif sort == "random":
            query = query.order_by(func.rand())
            page = None

        if filter == "woartist":
            query = query.filter("artist_id is null")
        elif filter == "woalbum":
            query = query.filter("album_id is null")
        elif filter == "invalid":
            query = query.filter("invalid is not null")
        elif filter == "duplicates":
            query = (query.join(TrackPath, Track.id == TrackPath.track_id)
                          .having(func.count(distinct(TrackPath.id)) > 1))

        pages = math.ceil(query.count() / page_size)

        tracks = query.limit(page_size).offset(offset).all()

        return {'tracks': tracks, 'page': page, 'pages': pages, 'sort': sort, 'filter': filter}

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='library/artists.html')
    def artists(self, sort = None, filter = None, filter_value = None, page = None):
        if sort is None:
            sort = "added"

        if filter is None:
            filter = "none"

        if filter_value is None:
            filter_value = ""

        if page is None:
            page = 1

        page = int(page)

        page_size = 24

        offset = page_size * (page - 1)

        query = (get_database()
                 .query(Artist)
                 .options(joinedload(Artist.albums))
                 .join(Track, Artist.id == Track.artist_id)
                 .filter(Track.scanned)
                 .group_by(Artist.id))

        if sort == "added":
            query = query.order_by(func.max(Track.added).desc())
        elif sort == "random":
            query = query.order_by(func.rand())
            page = None

        if filter == "yours":
            remotes_user = remotes.get_user(cherrypy.request.user)

            artist_ids = []

            if remotes_user is not None and remotes_user['lastfm'] is not None:
                for artist in remotes_user['lastfm']['top_artists_overall']:
                    artist_results = search.query_artist(artist['name'], exact = True)

                    if len(artist_results) > 0:
                        artist_ids.append(artist_results[0].id)

            query = query.filter(Artist.id.in_(artist_ids))
        elif filter == "invalid":
            query = query.filter("invalid is not null")
        elif filter == "tag":
            artist_ids = []

            if filter_value != "":
                remotes.update_tag(filter_value)
                remotes_tag = remotes.get_tag(filter_value)

                if remotes_tag is not None and remotes_tag['lastfm'] is not None:
                    for artist in remotes_tag['lastfm']['artists']:
                        artist_results = search.query_artist(artist['name'], exact = True)

                        if len(artist_results) > 0:
                            artist_ids.append(artist_results[0].id)

            query = query.filter(Artist.id.in_(artist_ids))

        pages = math.ceil(query.count() / page_size)

        artists = query.limit(page_size).offset(offset).all()

        for artist in artists:
            remotes.update_artist(artist)

        return {
            'artists': artists,
            'page': page,
            'sort': sort,
            'filter': filter,
            'filter_value': filter_value,
            'pages': pages
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='library/albums.html')
    def albums(self, view = None, sort = None, filter = None, filter_value = None, page = None):

        if view is None:
            view = "covers"

        if sort is None:
            sort = "added"

        if filter is None:
            filter = "none"

        if filter_value is None:
            filter_value = ""

        if page is None:
            page = 1

        page = int(page)

        page_size = 24

        offset = page_size * (page - 1)

        query = (get_database()
                 .query(Album)
                 .join(Track, Album.id == Track.album_id)
                 .filter(Track.scanned)
                 .group_by(Album.id))

        albums = []

        if filter == "yours":
            remotes_user = remotes.get_user(cherrypy.request.user)

            album_ids = []

            if remotes_user is not None and remotes_user['lastfm'] is not None:
                for album in remotes_user['lastfm']['top_albums_overall']:
                    album_results = search.query_album(album['name'], exact = True)

                    if len(album_results) > 0:
                        album_ids.append(album_results[0].id)

            query = query.filter(Album.id.in_(album_ids))
        elif filter == "6or30":
            query = query.having(or_(func.count(Track.id) > 6, func.sum(Track.duration) > 30 * 60))
        elif filter == "va":
            query = (query.join(Artist, Artist.id == Track.artist_id)
                          .having(func.count(distinct(Artist.id)) > 1))
        elif filter == "invalid":
            query = query.filter("invalid is not null")
        elif filter == "tag":
            album_ids = []

            if filter_value != "":
                remotes.update_tag(filter_value)
                remotes_tag = remotes.get_tag(filter_value)

                if remotes_tag is not None and remotes_tag['lastfm'] is not None:
                    for album in remotes_tag['lastfm']['albums']:
                        album_results = search.query_album(album['name'], exact = True)

                        if len(album_results) > 0:
                            album_ids.append(album_results[0].id)

            query = query.filter(Album.id.in_(album_ids))

        # count before adding order_by() for performance reasons..
        pages = math.ceil(query.count() / page_size)

        if sort == "added":
            query = query.order_by(Album.added.desc())
        elif sort == "date":
            query = query.order_by(Album.date.desc())
        elif sort == "random":
            query = query.order_by(func.rand())
            page = None

        albums = query.limit(page_size).offset(offset).all()

        for album in albums:
            remotes.update_album(album)

            for artist in album.artists:
                remotes.update_artist(artist)

        return {
            'albums': albums,
            'page': page,
            'sort': sort,
            'filter': filter,
            'filter_value': filter_value,
            'pages': pages,
            "view": view
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='library/artist.html')
    def artist(self, slug):
        artist = library_dao.get_artist_by_slug(slug)

        if artist is None:
            raise cherrypy.NotFound()

        album_group_order = {
            'default': 0,
            'ep': 1,
            'split': 2,
            'va': 3
        }

        album_groups = {}

        remotes.update_artist(artist)

        for album in artist.albums:
            if album.is_split:
                if 'split' not in album_groups:
                    album_groups['split'] = {
                        'title': 'Splits',
                        'albums': []
                    }

                album_groups['split']['albums'].append(album)
            elif album.is_va:
                if 'va' not in album_groups:
                    album_groups['va'] = {
                        'title': 'Various Artists',
                        'albums': []
                    }

                album_groups['va']['albums'].append(album)
            elif album.is_ep:
                if 'ep' not in album_groups:
                    album_groups['ep'] = {
                        'title': 'Singles & EPs',
                        'albums': []
                    }

                album_groups['ep']['albums'].append(album)
            else:
                if 'default' not in album_groups:
                    album_groups['default'] = {
                        'title': 'Albums',
                        'albums': []
                    }

                album_groups['default']['albums'].append(album)

            remotes.update_album(album)

        album_groups = OrderedDict(sorted(album_groups.items(),
                                   key=lambda album_group: album_group_order[album_group[0]]))

        remotes_artist = remotes.get_artist(artist)

        if remotes_artist is not None and remotes_artist['lastfm'] is not None:
            for tag_name in remotes_artist['lastfm']['tags']:
                remotes.update_tag(tag_name)

        same_artists = set()

        for artist_result in search.query_artist(artist.name, exact_metaphone=True):
            if artist != artist_result:
                same_artists.add(artist_result)

        dir_tracks = self._dir_tracks(artist.no_album_tracks)

        return {
            'dir_tracks': dir_tracks,
            'artist': artist,
            'album_groups': album_groups,
            'remotes_artist': remotes_artist,
            'same_artists': same_artists
        }

    @staticmethod
    def _produce_track_hierarchy(entities):
        hierarchy = {
            'artists': OrderedDict({}),
            'albums': OrderedDict({}),
            'tracks': OrderedDict({})
        }

        for entity in entities:
            if isinstance(entity, Artist):
                hierarchy['artists'][entity.id] = {
                    'entity': entity,
                    'albums': OrderedDict({}),
                    'tracks': OrderedDict({})
                }
            elif isinstance(entity, Album):
                if len(entity.artists) == 0:
                    hierarchy['albums'][entity.id] = {
                        'entity': entity,
                        'tracks': OrderedDict({})
                    }
                else:
                    for artist in entity.artists:
                        if artist.id not in hierarchy['artists']:
                            hierarchy['artists'][artist.id] = {
                                'entity': artist,
                                'albums': OrderedDict({}),
                                'tracks': OrderedDict({})
                            }

                        hierarchy['artists'][artist.id]['albums'][entity.id] = {
                            'entity': entity,
                            'tracks': OrderedDict({})
                        }
            elif isinstance(entity, Track):
                if entity.artist is not None and entity.artist.id not in hierarchy['artists']:
                    hierarchy['artists'][entity.artist.id] = {
                        'entity': entity.artist,
                        'albums': OrderedDict({}),
                        'tracks': OrderedDict({})
                    }

                if entity.artist is not None and entity.album is not None:
                    if entity.album.id not in hierarchy['artists'][entity.artist.id]['albums']:
                        hierarchy['artists'][entity.artist.id]['albums'][entity.album.id] = {
                            'entity': entity.album,
                            'tracks': OrderedDict({})
                        }

                    hierarchy['artists'][entity.artist.id]['albums'][entity.album.id]['tracks'][entity.id] = {
                        'entity': entity
                    }
                elif entity.artist is not None:
                    hierarchy['artists'][entity.artist.id]['tracks'][entity.id] = {
                        'entity': entity
                    }
                elif entity.album is not None:
                    if entity.album.id not in hierarchy['albums']:
                        hierarchy['albums'][entity.album.id] = {
                            'entity': entity.album,
                            'tracks': OrderedDict({})
                        }

                    hierarchy['albums'][entity.album.id]['tracks'][entity.id] = {
                        'entity': entity
                    }
                else:
                    hierarchy['tracks'][entity.id] = {
                        'entity': entity
                    }

        return hierarchy


class Admin:
    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.authorize(roles=['admin'])
    def default(self):
        raise HTTPRedirect('/admin/dashboard')

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.authorize(roles=['admin'])
    @cherrypy.tools.jinja(filename='admin/dashboard.html')
    def dashboard(self):
        library_path = cherrypy.request.app.config.get('opmuse').get('library.path')

        stat = os.statvfs(os.path.realpath(library_path))

        disk = {
            'path': library_path,
            'free': stat.f_frsize * stat.f_bavail,
            'total': stat.f_frsize * stat.f_blocks
        }

        formats = (get_database().query(Track.format, func.sum(Track.duration),
                                 func.sum(Track.size), func.count(Track.format))
                                 .group_by(Track.format).all())

        stats = {
            'tracks': library_dao.get_track_count(),
            'invalid': library_dao.get_invalid_track_count(),
            'albums': library_dao.get_album_count(),
            'artists': library_dao.get_artist_count(),
            'track_paths': library_dao.get_track_path_count(),
            'duration': library_dao.get_track_duration(),
            'size': library_dao.get_track_size(),
            'scanning': cherrypy.request.library.scanning,
            'files_found': cherrypy.request.library.files_found
        }

        return {
            'cache_size': cache.storage.size(),
            'disk': disk,
            'stats': stats,
            'formats': formats
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.authorize(roles=['admin'])
    @cherrypy.tools.jinja(filename='admin/bgtasks.html')
    def bgtasks(self):
        return {}

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.authorize(roles=['admin'])
    @cherrypy.tools.jinja(filename='admin/cache.html')
    def cache(self):
        values = []

        total_bytes = 0

        for key, item in cache.storage.values():
            bytes = total_size(item['value'])
            total_bytes += bytes
            values.append((key, bytes, type(item['value']), item['updated']))

        return {
            'values': values,
            'size': cache.storage.size(),
            'total_bytes': total_bytes
        }


class Dashboard:
    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='dashboard/index.html')
    def default(self):
        users = []

        for user in (get_database()
                     .query(User)
                     .order_by(User.login)
                     .filter(User.id != cherrypy.request.user.id)
                     .limit(8).all()):

            remotes.update_user(user)

            remotes_user = remotes.get_user(user)

            users.append({
                'remotes_user': remotes_user,
                'user': user,
                'current_track': queue_dao.get_current_track(user.id)
            })

        remotes.update_user(cherrypy.request.user)

        remotes_user = remotes.get_user(cherrypy.request.user)

        current_user = {
            'user': cherrypy.request.user,
            'current_track': queue_dao.get_current_track(cherrypy.request.user.id),
            'remotes_user': remotes_user,
        }

        all_users = [current_user] + users

        top_artists = Dashboard.get_top_artists(all_users)
        recent_tracks = Dashboard.get_recent_tracks(all_users)
        new_albums = Dashboard.get_new_albums(16, 0)

        now = datetime.datetime.now()

        day_format = "%Y-%m-%d"

        today = now.strftime(day_format)
        yesterday = (now - timedelta(days=1)).strftime(day_format)
        week = now.isocalendar()[0:1]

        for recent_track in recent_tracks:
            track = recent_track['track']

            if track is None:
                continue

            user = recent_track['user']

            if 'played_times' not in user:
                user['played_times'] = {
                    'today': 0,
                    'yesterday': 0,
                    'week': 0
                }

            track_datetime = datetime.datetime.fromtimestamp(int(recent_track['timestamp']))

            if track_datetime.strftime(day_format) == yesterday:
                user['played_times']['yesterday'] += track.duration

            if track_datetime.strftime(day_format) == today:
                user['played_times']['today'] += track.duration

            if track_datetime.isocalendar()[0:1] == week:
                user['played_times']['week'] += track.duration

        return {
            'current_user': current_user,
            'users': users,
            'top_artists': top_artists,
            'recent_tracks': recent_tracks,
            'new_albums': new_albums
        }

    @staticmethod
    def get_new_albums(limit, offset):
        return (get_database()
                .query(Album)
                .options(joinedload(Album.tracks))
                .options(undefer(Album.artist_count))
                .join(Track, Album.id == Track.album_id)
                .group_by(Album.id)
                .order_by(func.max(Track.added).desc())
                .limit(limit)
                .offset(offset)
                .all())

    @staticmethod
    def get_top_artists(all_users):
        top_artists = OrderedDict({})

        index = 0

        while True:
            stop = True

            for user in all_users:
                if user['remotes_user'] is None or user['remotes_user']['lastfm'] is None:
                    continue

                top = user['remotes_user']['lastfm']['top_artists_month']

                if top is not None and index < len(top):
                    stop = False

                    artist = top[index]

                    results = search.query_artist(artist['name'], exact=True)

                    if len(results) > 0:
                        top_artists[results[0]] = None

                    if len(top_artists) >= 24:
                        stop = True
                        break
            if stop:
                break

            index += 1

        top_artists = list(top_artists.keys())

        return top_artists

    @staticmethod
    def get_recent_tracks(all_users):
        all_recent_tracks = []

        for user in all_users:
            if user['remotes_user'] is None or user['remotes_user']['lastfm'] is None:
                continue

            recent_tracks = []

            for recent_track in user['remotes_user']['lastfm']['recent_tracks']:
                recent_tracks.append((user, recent_track))

            all_recent_tracks += recent_tracks

        all_recent_tracks = sorted(all_recent_tracks,
                                   key=lambda recent_track: recent_track[1]['timestamp'], reverse=True)

        recent_tracks = []

        for user, recent_track in all_recent_tracks:
            results = search.query_artist(recent_track['artist'], exact=True)

            track = artist = None

            if len(results) > 0:
                artist = results[0]

                results = search.query_track(recent_track['name'], exact=True)

                if len(results) > 0:
                    for result in results:
                        if result.artist.id == artist.id:
                            track = result

            recent_tracks.append({
                'artist': artist,
                'track': track,
                'artist_name': recent_track['artist'],
                'name': recent_track['name'],
                'timestamp': recent_track['timestamp'],
                'user': user
            })

            if len(recent_tracks) > 24:
                break

        return recent_tracks


class Stream:

    STREAM_PLAYING = {}

    def __init__(self):
        cherrypy.engine.subscribe('transcoding.end', self.transcoding_end)
        cherrypy.engine.subscribe('transcoding.start', self.transcoding_start)

    def transcoding_start(self, transcoder, track):
        Stream.STREAM_PLAYING[cherrypy.request.user.id] = cherrypy.request.headers['User-Agent']

    def transcoding_end(self, track, transcoder):
        Stream.STREAM_PLAYING[cherrypy.request.user.id] = None

    @cherrypy.expose
    @cherrypy.tools.transcodingsubprocess()
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.config(**{'response.stream': True})
    def default(self, **kwargs):

        user = cherrypy.request.user

        remotes.update_user(user)

        if 'dead' in kwargs and kwargs['dead'] == 'true':
            raise cherrypy.HTTPError(status=503)

        user_agent = cherrypy.request.headers['User-Agent']

        # allow only one streaming client at once, or weird things might occur
        if (user.id in Stream.STREAM_PLAYING and Stream.STREAM_PLAYING[user.id] is not None and
            Stream.STREAM_PLAYING[user.id] != user_agent):
            raise cherrypy.HTTPError(status=503)

        queue = queue_dao.get_next(user.id)

        if queue is None:
            raise cherrypy.HTTPError(status=409)

        transcoder, format = transcoding.determine_transcoder(
            queue.track,
            user_agent,
            [accept.value for accept in cherrypy.request.headers.elements('Accept')]
        )

        cherrypy.log(
            '%s is streaming "%s" in %s (original was %s) with "%s"' %
            (user.login, queue.track, format, queue.track.format, user_agent)
        )

        cherrypy.response.headers['Content-Type'] = format

        def track_generator():
            yield queue.track, queue.current_seconds

        return transcoding.transcode(track_generator(), transcoder)


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
    remove = Remove()
    users = Users()
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
