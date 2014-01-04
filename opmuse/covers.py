# Copyright 2012-2013 Mattias Fliesberg
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
import mimetypes
import cherrypy
import base64
import mmh3
import tempfile
import time
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from opmuse.ws import ws
from opmuse.image import image as image_service
from opmuse.library import library_dao
from opmuse.library import Artist, Album
from opmuse.lastfm import lastfm
from opmuse.google import google
from opmuse.database import get_database
from opmuse.remotes import remotes


def log(msg, traceback=False):
    cherrypy.log(msg, context='covers', traceback=traceback)


class Covers:
    DEFAULT_WIDTH = 220
    DEFAULT_HEIGHT = 220
    DEFAULT_GRAVITY = 'center'
    LARGE_WIDTH = 650
    LARGE_HEIGHT = 325
    LARGE_GRAVITY = 'north'

    def refresh(self, type, slug):
        if type not in ['album', 'artist']:
            raise ValueError('Invalid type %s supplied' % type)

        entity = None

        if type == "album":
            entity = library_dao.get_album_by_slug(slug)
        elif type == "artist":
            entity = library_dao.get_artist_by_slug(slug)

        if entity is not None:
            if entity.cover_path is not None and os.path.exists(entity.cover_path):
                os.remove(entity.cover_path)

            entity.cover_path = None
            entity.cover_hash = None
            entity.cover = None
            entity.cover_large = None

        if type == "album":
            ws.emit_all('covers.album.update', entity.id)
        elif type == "artist":
            ws.emit_all('covers.artist.update', entity.id)

    def get_cover(self, type, slug, size = "default"):
        if type not in ['album', 'artist']:
            raise ValueError('Invalid type %s supplied' % type)

        entity = None

        if type == "album":
            entity = library_dao.get_album_by_slug(slug)

            remotes.update_album(entity)

            if entity is None:
                raise ValueError('Entity not found')

            for artist in entity.artists:
                if artist.cover_path is None or not os.path.exists(artist.cover_path):
                    cherrypy.engine.bgtask.put(self.fetch_artist_cover, 9, artist.id)

            if entity.cover_path is None or not os.path.exists(entity.cover_path):
                cherrypy.engine.bgtask.put(self.fetch_album_cover, 9, entity.id)

                for artist in entity.artists:
                    if artist.cover is not None:
                        return self.guess_mime(artist), artist.cover_large if size == "large" else artist.cover

        elif type == "artist":
            entity = library_dao.get_artist_by_slug(slug)

            remotes.update_artist(entity)

            if entity is None:
                raise ValueError('Entity not found')

            if entity.cover_path is None or not os.path.exists(entity.cover_path):
                cherrypy.engine.bgtask.put(self.fetch_artist_cover, 9, entity.id)

        if entity is None:
            raise ValueError('Entity not found')

        if entity.cover_path is not None:
            if entity.cover is None:
                cover_ext = os.path.splitext(entity.cover_path)[1].decode('utf8')
                temp_cover = tempfile.mktemp(cover_ext).encode('utf8')
                temp_cover_large = tempfile.mktemp(cover_ext).encode('utf8')

                cover = image_service.resize(entity.cover_path, temp_cover,
                                             Covers.DEFAULT_WIDTH, Covers.DEFAULT_HEIGHT,
                                             Covers.DEFAULT_GRAVITY)

                large_offset = self._get_image_offset(Covers.LARGE_WIDTH, Covers.LARGE_HEIGHT,
                                                      Covers.LARGE_GRAVITY)

                cover_large = image_service.resize(entity.cover_path, temp_cover_large,
                                                   Covers.LARGE_WIDTH, Covers.LARGE_HEIGHT,
                                                   Covers.LARGE_GRAVITY, large_offset)

                if cover and cover_large:
                    with open(temp_cover, 'rb') as file:
                        entity.cover = file.read()
                        entity.cover_hash = base64.b64encode(mmh3.hash_bytes(entity.cover))

                    with open(temp_cover_large, 'rb') as file:
                        entity.cover_large = file.read()

                    os.remove(temp_cover)
                    os.remove(temp_cover_large)

                    get_database().commit()

            return self.guess_mime(entity), entity.cover_large if size == "large" else entity.cover

        return None, None

    def fetch_album_cover(self, album_id):
        album = get_database().query(Album).filter_by(id=album_id).one()

        remotes_album = None
        tries = 0

        # try and sleep until we get the remotes_album.
        while remotes_album is None and tries < 8:
            remotes_album = remotes.get_album(album)

            tries += 1

            if remotes_album is None:
                # exponential backoff
                time.sleep(tries ** 2)

        lastfm_album = None

        if remotes_album is not None:
            lastfm_album = remotes_album['lastfm']

        if lastfm_album is None or lastfm_album['cover'] is None:
            google_images = google.get_album_images(album)

            if google_images is not None:
                urls = google_images
            else:
                return
        else:
            urls = [lastfm_album['cover']]

        cover = None

        for url in urls:
            cover, resize_cover, resize_cover_large, cover_ext = self.retrieve_and_resize(url)

            if cover is None:
                continue

        if cover is None:
            return

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
        album.cover_large = resize_cover_large
        album.cover_hash = base64.b64encode(mmh3.hash_bytes(album.cover))

        get_database().commit()

        ws.emit_all('covers.album.update', album.id)

    fetch_album_cover.bgtask_name = "Fetch cover for album {0}"

    def fetch_artist_cover(self, artist_id):
        artist = get_database().query(Artist).filter_by(id=artist_id).one()

        remotes_artist = None
        tries = 0

        # try and sleep until we get the remotes_artist.
        while remotes_artist is None and tries < 8:
            remotes_artist = remotes.get_artist(artist)

            tries += 1

            if remotes_artist is None:
                # exponential backoff
                time.sleep(tries ** 2)

        lastfm_artist = None

        if remotes_artist is not None:
            lastfm_artist = remotes_artist['lastfm']

        if lastfm_artist is None or lastfm_artist['cover'] is None:
            google_images = google.get_artist_images(artist)

            if google_images is not None:
                urls = google_images
            else:
                return
        else:
            urls = [lastfm_artist['cover']]

        cover = None

        for url in urls:
            cover, resize_cover, resize_cover_large, cover_ext = self.retrieve_and_resize(url)

            if cover is None:
                continue

        if cover is None:
            return

        track_dirs = set()

        for track in artist.tracks:
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
        artist.cover_large = resize_cover_large
        artist.cover_hash = base64.b64encode(mmh3.hash_bytes(artist.cover))

        get_database().commit()

        ws.emit_all('covers.artist.update', artist.id)

    fetch_artist_cover.bgtask_name = "Fetch cover for artist {0}"

    def retrieve_and_resize(self, image_url):
        image_ext = os.path.splitext(image_url)[1]

        album_dirs = set()

        temp_image = tempfile.mktemp(image_ext).encode('utf8')

        try:
            fp_from = urlopen(image_url)
        except (HTTPError, URLError) as error:
            log('Got "%s" when downloading %s.' % (error, image_url))
            return None, None, None, None

        with open(temp_image, "wb") as fp_to:
            fp_to.write(fp_from.read())

        resize_image = self._resize(temp_image, Covers.DEFAULT_WIDTH, Covers.DEFAULT_HEIGHT, Covers.DEFAULT_GRAVITY)
        resize_image_large = self._resize(temp_image, Covers.LARGE_WIDTH, Covers.LARGE_HEIGHT, Covers.LARGE_GRAVITY)

        if not resize_image or not resize_image_large:
            return None, None, None, None

        image = None

        with open(temp_image, 'rb') as file:
            image = file.read()

        os.remove(temp_image)

        return image, resize_image, resize_image_large, image_ext

    def _get_image_offset(self, width, height, gravity):
        if gravity == "north":
            offset_y = int(height * 0.15)
            return "+0+%d" % offset_y
        else:
            return "+0+0"

    def _resize(self, temp_image, width, height, gravity):
        image_ext = os.path.splitext(temp_image.decode('utf8'))[1]

        offset = self._get_image_offset(width, height, gravity)

        resize_temp_image = tempfile.mktemp(image_ext).encode('utf8')

        if not image_service.resize(temp_image, resize_temp_image, width, height, gravity, offset):
            os.remove(temp_image)

            if os.path.exists(resize_temp_image):
                os.remove(resize_temp_image)

            return False

        resize_image = None

        with open(resize_temp_image, 'rb') as file:
            resize_image = file.read()

        os.remove(resize_temp_image)

        return resize_image

    def guess_mime(self, entity):
        mimetype = mimetypes.guess_type(entity.cover_path.decode('utf8', 'replace'))
        return mimetype[0] if mimetype is not None else 'image/jpeg'


covers = Covers()
