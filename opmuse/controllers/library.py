# Copyright 2012-2015 Mattias Fliesberg
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
import time
import datetime
import math
import rarfile
import shutil
import tempfile
import cherrypy
import re
from collections import OrderedDict
from urllib.parse import unquote
from zipfile import ZipFile
from rarfile import RarFile
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm import joinedload
from sqlalchemy import func, distinct, and_
from sqlalchemy.sql import text
from opmuse.database import get_database
from opmuse.library import (library_dao, TrackPath, TrackStructureParser, Album,
                            Track, Artist, UserAndAlbum, Library as LibraryService)
from opmuse.utils import HTTPRedirect
from opmuse.search import search
from opmuse.cache import cache
from opmuse.remotes import remotes
from opmuse.security import security_dao


class LibraryEdit:
    @cherrypy.expose
    @cherrypy.tools.jinja(filename='library/edit.html')
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    def default(self, ids=''):
        ids = ids.split(',')

        tracks = library_dao.get_tracks_by_ids(ids)

        return {'tracks': tracks}

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='library/edit_result.html')
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    def submit(self, ids, artists, albums, tracks, dates, numbers, discs, yes=False, no=False):

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

        tracks = LibraryEdit._sort_tracks(tracks)

        hierarchy = Library._produce_track_hierarchy(tracks)

        return {'hierarchy': hierarchy, 'messages': messages}

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='library/edit_result.html')
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    def move(self, ids, where=None):

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
            filenames, move=True, remove_dirs=True, artist_name_override=artist_name
        )

        tracks = LibraryEdit._sort_tracks(tracks)

        hierarchy = Library._produce_track_hierarchy(tracks)

        return {'hierarchy': hierarchy, 'messages': messages}

    @staticmethod
    def _sort_tracks(tracks):
        return sorted(tracks, key=lambda track: (
                      track.artist.name if track.artist is not None else '',
                      track.album.name if track.album is not None else '',
                      track.number if track.number is not None else '0',
                      track.name))


class LibraryRemove:
    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='library/remove_modal.html')
    def modal(self, ids, title=None):
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


class LibraryUpload:
    CACHE_KEY = "UPLOAD_TRACKS_%d_%s"

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='library/upload.html')
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    def default(self):
        return {}

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    def start(self, session=None):
        cache_key = LibraryUpload.CACHE_KEY % (cherrypy.request.user.id, session)

        all_tracks = []

        cache.set(cache_key, all_tracks)

        return b''

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='library/upload_add.html')
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    def add(self, archive_password=None, audio_file=None, session=None, artist_name_fallback=None):
        cache_key = LibraryUpload.CACHE_KEY % (cherrypy.request.user.id, session)

        all_tracks = None

        if not cache.has(cache_key):
            raise cherrypy.HTTPError(status=409)
        else:
            all_tracks = cache.get(cache_key)

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

        cache_path = os.path.join(cherrypy.config['opmuse'].get('cache.path'), 'upload')

        if not os.path.exists(cache_path):
            os.mkdir(cache_path)

        tempdir = tempfile.mkdtemp(dir=cache_path)

        path = os.path.join(tempdir, filename)

        paths = []

        rarfile.PATH_SEP = '/'

        messages = []

        with open(path, 'wb') as fileobj:
            fileobj.write(cherrypy.request.rfile.read())

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
                messages.append(('warning', ("<strong>%s</strong>: Skipping <strong>%s</strong>, timeout trying to " +
                                "find its track.") % (audio_file, filename)))
            else:
                track_structure = TrackStructureParser(track)
                track_path = track_structure.get_path(absolute=True)
                relative_track_path = track_structure.get_path(absolute=False).decode('utf8', 'replace')

                new_path = os.path.join(track_path, filename.encode('utf8'))

                if os.path.exists(new_path):
                    messages.append(('warning', ("<strong>%s</strong>: Skipping <strong>%s</strong>, already exists " +
                                    "in <strong>%s</strong>.") % (audio_file, filename, relative_track_path)))
                else:
                    shutil.move(path.encode('utf8'), new_path)
                    messages.append(('info', ("<strong>%s</strong>: Uploaded <strong>%s</strong> to " +
                                    "<strong>%s</strong>.") % (audio_file, filename, relative_track_path)))

        elif ext == "zip":
            # set artist name fallback to zip's name so if it's missing artist tags
            # it's easily distinguishable and editable so it can be fixed after upload.
            artist_name_fallback = basename

            try:
                zip = ZipFile(path)

                if archive_password is not None:
                    zip.setpassword(archive_password.encode())

                zip.extractall(tempdir)

                os.remove(path)

                for name in zip.namelist():
                    namepath = os.path.join(tempdir, name)

                    # ignore hidden files, e.g. OSX archive weirdness and such
                    if name.startswith(".") or os.path.split(name)[0] == "__MACOSX":
                        shutil.rmtree(namepath)
                        continue

                    paths.append(namepath.encode('utf8'))

            except Exception as error:
                messages.append(('danger', "<strong>%s</strong>: %s" % (os.path.basename(path), error)))

        elif ext == "rar":
            # look at corresponding ext == zip comment...
            artist_name_fallback = basename

            try:
                rar = RarFile(path)

                if archive_password is None and rar.needs_password():
                    messages.append(('danger', "<strong>%s</strong>: Needs password but none provided." %
                                    os.path.basename(path)))
                else:
                    if archive_password is not None:
                        rar.setpassword(archive_password)

                    rar.extractall(tempdir)

                    os.remove(path)

                    for name in rar.namelist():
                        namepath = os.path.join(tempdir, name)

                        if name.startswith("."):
                            shutil.rmtree(namepath)
                            continue

                        paths.append(namepath.encode('utf8'))

            except Exception as error:
                messages.append(('danger', "<strong>%s</strong>: %s" % (os.path.basename(path), error)))

        # this is a plain audio file
        else:
            paths.append(path.encode('utf8'))

        for path in paths:
            # update modified time to now, we don't want the time from the zip
            # archive or whatever
            os.utime(path, None)

        if len(paths) > 0:
            tracks, add_files_messages = library_dao.add_files(paths, move=True, remove_dirs=False,
                                                               artist_name_fallback=artist_name_fallback,
                                                               user=cherrypy.request.user)
            messages += add_files_messages
        else:
            tracks = []

        shutil.rmtree(tempdir)

        for track in tracks:
            all_tracks.append(track.id)

            if track.album is not None:
                remotes.update_album(track.album)

            if track.artist is not None:
                remotes.update_artist(track.artist)

            remotes.update_track(track)

        hierarchy = Library._produce_track_hierarchy(library_dao.get_tracks_by_ids(all_tracks))

        return {'hierarchy': hierarchy, 'messages': messages}


class Library:
    upload = LibraryUpload()
    edit = LibraryEdit()
    remove = LibraryRemove()

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

        remotes_track = remotes.get_track(track)

        if track.artist is not None:
            artist_listened_tuples = self.get_artist_listened_tuples(track.artist.name)

            if track.album is not None:
                album_listened_tuples = self.get_album_listened_tuples(track.artist.name, track.album.name)
            else:
                album_listened_tuples = None
        else:
            artist_listened_tuples = None
            album_listened_tuples = None

        return {
            'track': track,
            'remotes_artist': remotes_artist,
            'remotes_album': remotes_album,
            'remotes_track': remotes_track,
            'album_listened_tuples': album_listened_tuples,
            'artist_listened_tuples': artist_listened_tuples,
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='library/artist_caption.html')
    def artist_caption(self, artist_id):
        artist = library_dao.get_artist(artist_id)

        if artist is None:
            raise cherrypy.NotFound()

        listened_track = library_dao.get_listened_track_by_artist_name(cherrypy.request.user.id, artist.name)

        return {
            'artist': artist,
            'listened_track': listened_track
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='library/album_caption.html')
    def album_caption(self, album_id):
        album = library_dao.get_album(album_id)

        if album is None:
            raise cherrypy.NotFound()

        if len(album.artists) > 0:
            artist_name = album.artists[0].name
        else:
            artist_name = None

        listened_track = library_dao.get_listened_track_by_artist_name_and_album_name(cherrypy.request.user.id,
                                                                                      artist_name, album.name)

        return {
            'album': album,
            'listened_track': listened_track
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

        # always update seen, True means now
        album.seen = True

        remotes.update_album(album)

        remotes_artists = []

        for artist in album.artists:
            remotes.update_artist(artist)
            remotes_artist = remotes.get_artist(artist)

            if remotes_artist is not None:
                remotes_artists.append(remotes_artist)

        disc_nos = {}

        for track in album.tracks:
            remotes.update_track(track)

            disc = '' if track.disc is None else track.disc

            if disc not in disc_nos:
                disc_nos[disc] = []

            if track.number is not None:
                # extract max track no, '01' will become 1, '01/10' will become 10
                disc_nos[disc].append(int(re.search(r'\d+', track.number).group()))
            else:
                disc_nos[disc].append(None)

        album_disc_nos = []

        for disc, numbers in disc_nos.items():
            max_number = max([number for number in numbers if number is not None], default=None)

            if max_number is not None:
                album_disc_nos.append((disc, len(numbers), max_number))

        album_disc_nos = sorted(album_disc_nos, key=lambda album_disc_no: album_disc_no[0])

        remotes_album = remotes.get_album(album)

        dir_tracks = self._dir_tracks(album.tracks)

        if len(album.artists) > 0:
            artist_name = album.artists[0].name
        else:
            artist_name = None

        album_listened_tuples = self.get_album_listened_tuples(artist_name, album.name)
        artist_listened_tuples = self.get_artist_listened_tuples(artist_name)

        return {
            'album_disc_nos': album_disc_nos,
            'album': album,
            'dir_tracks': dir_tracks,
            'remotes_artists': remotes_artists,
            'remotes_album': remotes_album,
            'album_listened_tuples': album_listened_tuples,
            'artist_listened_tuples': artist_listened_tuples,
        }

    # TODO use whoosh instead
    def get_artist_listened_tuples(self, artist_name):
        artist_listened_tuples = []

        listened_tuples = library_dao.get_listened_tuples_by_artist_name_for_users(artist_name)

        youple = None

        for user_id, timestamp in listened_tuples:
            user = security_dao.get_user(user_id)

            listened_tuple = (user, timestamp)

            if user_id == cherrypy.request.user.id:
                youple = listened_tuple
            else:
                artist_listened_tuples.append(listened_tuple)

        if youple is not None:
            artist_listened_tuples.insert(0, youple)

        return artist_listened_tuples

    # TODO use whoosh instead
    def get_album_listened_tuples(self, artist_name, album_name):
        album_listened_tuples = []

        listened_tuples = library_dao.get_listened_tuples_by_artist_name_and_album_name_for_users(
            artist_name, album_name)

        youple = None

        for user_id, timestamp in listened_tuples:
            user = security_dao.get_user(user_id)

            listened_tuple = (user, timestamp)

            if user_id == cherrypy.request.user.id:
                youple = listened_tuple
            else:
                album_listened_tuples.append(listened_tuple)

        if youple is not None:
            album_listened_tuples.insert(0, youple)

        return album_listened_tuples

    def _dir_tracks(self, tracks):
        dir_tracks = {}

        artist_covers = set()
        album_covers = set()

        for track in tracks:
            if track.artist is not None:
                artist_covers.add(track.artist.cover_path)

            if track.album is not None:
                album_covers.add(track.album.cover_path)

            if len(track.paths) == 0:
                continue

            for path in track.paths:
                dir = path.dir

                if dir not in dir_tracks:
                    dir_tracks[dir] = {
                        'paths': [],
                        'tracks': [],
                        'paths_and_tracks': [],
                        'pretty_dir': path.pretty_dir,
                        'files': [],
                    }

                dir_tracks[dir]['paths'].append(path.path)
                dir_tracks[dir]['tracks'].append(track)
                dir_tracks[dir]['paths_and_tracks'].append((path, track))

        for dir, dir_track in dir_tracks.items():
            dir_tracks[dir]['paths_and_tracks'] = sorted(dir_track['paths_and_tracks'], key=lambda pat: pat[0].path)

        for dir, item in dir_tracks.items():
            if not os.path.exists(dir):
                continue

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
                        try:
                            stat = os.stat(file)
                            modified = datetime.datetime.fromtimestamp(stat.st_mtime)
                            size = stat.st_size
                        except FileNotFoundError:
                            continue
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
                                              key=lambda item: "%d%s" % (not item["isdir"], item["file"]))

        dir_tracks = sorted(dir_tracks.items(), key=lambda d: d[0])

        return dir_tracks

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='library/tracks.html')
    def tracks(self, sort=None, filter=None, page=None):
        if sort is None:
            sort = "created"

        if filter is None:
            filter = "none"

        if page is None:
            page = 1

        page = int(page)

        page_size = 70

        offset = page_size * (page - 1)

        query = get_database().query(Track).filter(Track.scanned).group_by(Track.id)

        if sort == "created":
            query = query.order_by(Track.created.desc())
        elif sort == "updated":
            query = query.order_by(Track.updated.desc())
        elif sort == "random":
            query = query.order_by(func.rand())
            page = None

        if filter == "woartist":
            query = query.filter(text("artist_id is null"))
        elif filter == "woalbum":
            query = query.filter(text("album_id is null"))
        elif filter == "invalid":
            query = query.filter(text("invalid is not null"))
        elif filter == "duplicates":
            query = (query.join(TrackPath, Track.id == TrackPath.track_id)
                          .having(func.count(distinct(TrackPath.id)) > 1))

        total = query.count()
        pages = math.ceil(total / page_size)

        tracks = query.limit(page_size).offset(offset).all()

        return {
            'tracks': tracks,
            'page': page,
            'page_size': page_size,
            'total': total,
            'pages': pages,
            'sort': sort,
            'filter': filter
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='library/artists.html')
    def artists(self, sort=None, filter=None, filter_value=None, page=None):
        if sort is None:
            sort = "created"

        if filter is None:
            filter = "none"

        if filter_value is None:
            filter_value = ""

        if page is None:
            page = 1

        page = int(page)

        page_size = 48

        offset = page_size * (page - 1)

        query = (get_database()
                 .query(Artist)
                 .join(Track, Artist.id == Track.artist_id)
                 .filter(Track.scanned)
                 .group_by(Artist.id))

        if sort == "created":
            query = query.order_by(Artist.created.desc())
        elif sort == "updated":
            query = query.order_by(Artist.updated.desc())
        elif sort == "random":
            query = query.order_by(func.rand())
            page = None

        if filter == "yours":
            remotes_user = remotes.get_user(cherrypy.request.user)

            artist_ids = []

            if remotes_user is not None and remotes_user['lastfm'] is not None:
                for artist in remotes_user['lastfm']['top_artists_overall']:
                    artist_results = search.query_artist(artist['name'], exact=True)

                    if len(artist_results) > 0:
                        artist_ids.append(artist_results[0].id)

            query = query.filter(Artist.id.in_(artist_ids))
        elif filter == "invalid":
            query = query.filter(text("invalid is not null"))
        elif filter == "tag":
            artist_ids = []

            if filter_value != "":
                remotes.update_tag(filter_value)
                remotes_tag = remotes.get_tag(filter_value)

                if remotes_tag is not None and remotes_tag['lastfm'] is not None:
                    for artist in remotes_tag['lastfm']['artists']:
                        artist_results = search.query_artist(artist['name'], exact=True)

                        if len(artist_results) > 0:
                            artist_ids.append(artist_results[0].id)

            query = query.filter(Artist.id.in_(artist_ids))

        total = query.count()
        pages = math.ceil(total / page_size)

        artists = query.limit(page_size).offset(offset).all()

        for artist in artists:
            remotes.update_artist(artist)

        return {
            'artists': artists,
            'page': page,
            'page_size': page_size,
            'total': total,
            'sort': sort,
            'filter': filter,
            'filter_value': filter_value,
            'pages': pages
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='library/albums.html')
    def albums(self, view=None, sort=None, filter=None, filter_value=None, page=None):
        if view is None:
            view = "covers"

        if sort is None:
            sort = "created"

        if filter is None:
            filter = "none"

        if filter_value is None:
            filter_value = ""

        if page is None:
            page = 1

        page = int(page)

        page_size = 48

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
                    album_results = search.query_album(album['name'], exact=True)

                    if len(album_results) > 0:
                        album_ids.append(album_results[0].id)

            query = query.filter(Album.id.in_(album_ids))
        elif filter == "1year" or filter == "2year" or filter == "5year":
            now = datetime.datetime.utcnow()

            if filter == "2year":
                years = 2
            elif filter == "5year":
                years = 5
            else:
                years = 1

            query = query.filter(Album.created > now - datetime.timedelta(days=years * 365))
        elif filter == "va":
            query = (query.join(Artist, Artist.id == Track.artist_id)
                          .having(func.count(distinct(Artist.id)) > 1))
        elif filter == "invalid":
            query = query.filter(text("invalid is not null"))
        elif filter == "tag":
            album_ids = []

            if filter_value != "":
                remotes.update_tag(filter_value)
                remotes_tag = remotes.get_tag(filter_value)

                if remotes_tag is not None and remotes_tag['lastfm'] is not None:
                    for album in remotes_tag['lastfm']['albums']:
                        album_results = search.query_album(album['name'], exact=True)

                        if len(album_results) > 0:
                            album_ids.append(album_results[0].id)

            query = query.filter(Album.id.in_(album_ids))

        # count before adding order_by() for performance reasons..
        total = query.count()
        pages = math.ceil(total / page_size)

        if sort == "created":
            query = query.order_by(Album.created.desc())
        elif sort == "updated":
            query = query.order_by(Album.updated.desc())
        elif sort == "seen":
            query = (query.outerjoin(UserAndAlbum, and_(Album.id == UserAndAlbum.album_id,
                                     UserAndAlbum.user_id == cherrypy.request.user.id))
                     .order_by(UserAndAlbum.seen.desc())
                     .order_by(Album.updated.desc()))
        elif sort == "date":
            query = (query
                     .order_by(Album.date.desc())
                     .order_by(Album.updated.desc()))
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
            'page_size': page_size,
            'total': total,
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
            'live': 3,
            'va': 4
        }

        album_groups = {}

        remotes.update_artist(artist)

        for album in artist.albums:
            if re.search(r'\blive\b', album.name.lower()):
                if 'live' not in album_groups:
                    album_groups['live'] = {
                        'title': 'Live',
                        'albums': []
                    }

                album_groups['live']['albums'].append(album)
            elif album.is_split:
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

        same_artists = set()

        for artist_result in search.query_artist(artist.name, exact_metaphone=True):
            if artist != artist_result:
                same_artists.add(artist_result)

        dir_tracks = self._dir_tracks(artist.no_album_tracks)

        remotes_user = remotes.get_user(cherrypy.request.user)

        artist_listened_tuples = self.get_artist_listened_tuples(artist.name)

        return {
            'remotes_user': remotes_user,
            'dir_tracks': dir_tracks,
            'artist': artist,
            'album_groups': album_groups,
            'remotes_artist': remotes_artist,
            'same_artists': same_artists,
            'artist_listened_tuples': artist_listened_tuples
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
