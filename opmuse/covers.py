import os
import mimetypes
import cherrypy
import base64
import mmh3
import tempfile
from opmuse.image import image as image_service
from opmuse.library import library_dao
from opmuse.library import Artist, Album
from opmuse.lastfm import lastfm
from urllib.request import urlretrieve

class Covers:
    SIZE = 220

    def get_cover(self, type, slug):
        if type not in ['album', 'artist']:
            raise ValueError('Invalid type %s supplied' % type)

        entity = None

        if type == "album":
            entity = library_dao.get_album_by_slug(slug)

            if entity is None:
                raise ValueError('Entity not found')

            for artist in entity.artists:
                if artist.cover_path is None or not os.path.exists(artist.cover_path):
                    cherrypy.engine.bgtask.put(self.fetch_artist_cover, artist.id)

            if entity.cover_path is None or not os.path.exists(entity.cover_path):
                cherrypy.engine.bgtask.put(self.fetch_album_cover, entity.id)

                for artist in entity.artists:
                    if artist.cover is not None:
                        return self.guess_mime(artist), artist.cover

        elif type == "artist":
            entity = library_dao.get_artist_by_slug(slug)

            if entity is None:
                raise ValueError('Entity not found')

            if entity.cover_path is None or not os.path.exists(entity.cover_path):
                cherrypy.engine.bgtask.put(self.fetch_artist_cover, entity.id)

        if entity is None:
            raise ValueError('Entity not found')

        if entity.cover_path is not None:
            if entity.cover is None:
                cover_ext = os.path.splitext(entity.cover_path)[1].decode('utf8')
                temp_cover = tempfile.mktemp(cover_ext).encode('utf8')

                if image_service.resize(entity.cover_path, temp_cover, Covers.SIZE):
                    with open(temp_cover, 'rb') as file:
                        entity.cover = file.read()
                        entity.cover_hash = base64.b64encode(mmh3.hash_bytes(entity.cover))

                    os.remove(temp_cover)

                    cherrypy.request.database.commit()

            return self.guess_mime(entity), entity.cover

        return None, None

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

    def fetch_artist_cover(self, artist_id, _database):
        artist = _database.query(Artist).filter_by(id=artist_id).one()

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

    def retrieve_and_resize(self, image_url):
        image_ext = os.path.splitext(image_url)[1]

        album_dirs = set()

        temp_image = tempfile.mktemp(image_ext).encode('utf8')
        resize_temp_image = tempfile.mktemp(image_ext).encode('utf8')
        urlretrieve(image_url, temp_image)

        if not image_service.resize(temp_image, resize_temp_image, Covers.SIZE):
            os.remove(temp_image)
            os.remove(resize_temp_image)
            return

        resize_image = None
        image = None

        with open(resize_temp_image, 'rb') as file:
            resize_image = file.read()

        os.remove(resize_temp_image)

        with open(temp_image, 'rb') as file:
            image = file.read()

        os.remove(temp_image)

        return image, resize_image, image_ext

    def guess_mime(self, entity):
        mimetype = mimetypes.guess_type(entity.cover_path.decode('utf8', 'replace'))
        return mimetype[0] if mimetype is not None else 'image/jpeg'


covers = Covers()
