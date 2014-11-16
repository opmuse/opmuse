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

import cherrypy
import re
import os
import base64
import io
import datetime
import math
import shutil
import time
import random
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from cherrypy.process.plugins import SimplePlugin
from cherrypy.lib.lockfile import LockFile, LockError
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy import (Column, Integer, BigInteger, String, ForeignKey, VARBINARY, BINARY, BLOB,
                        DateTime, Boolean, func, TypeDecorator, Index, distinct, select)
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import relationship, deferred, validates, column_property
from sqlalchemy.orm.session import Session
from sqlalchemy.ext.hybrid import hybrid_property
from multiprocessing import cpu_count
from threading import Thread
from unidecode import unidecode
from opmuse.database import Base, get_session, get_database_type, get_database, database_data
from opmuse.search import search
from opmuse.utils import memoize
from opmuse.security import User
import mutagen.mp3
import mutagen.oggvorbis
import mutagen.easymp4
import mutagen.asf
import mutagen.flac
import mutagen.easyid3
import mutagen.apev2
import mutagen.musepack


__all__ = ['FileMetadata', 'library_dao', 'ApeParser', 'TrackStructureParser', 'Artist', 'OggParser',
           'StringBinaryType', 'LibraryDao', 'mutagen', 'IntegrityError', 'MpcParser', 'StructureParser',
           'LibraryProcess', 'reader', 'TagParser', 'Library', 'Id3Parser', 'WmaParser', 'Album', 'LibraryTool',
           'TagReader', 'FsParser', 'Mp4Parser', 'MutagenParser', 'MetadataStructureParser', 'TrackPath',
           'FlacParser', 'Track', 'LibraryPlugin']


def log(msg, traceback=False):
    _log(msg, traceback, logging.INFO)


def warn(msg, traceback=False):
    _log(msg, traceback, logging.WARNING)


def debug(msg, traceback=False):
    _log(msg, traceback, logging.DEBUG)


def _log(msg, traceback, severity):
    cherrypy.log.error(msg, context='library', severity=severity, traceback=traceback)


class StringNotNullType(TypeDecorator):
    """
    Stores None values as empty strings. This is used with unique indexes
    so None values are treated as actual unique values.
    """
    impl = String

    class comparator_factory(String.Comparator):
        def __ne__(self, other):
            if other is None:
                other = ''

            return String.Comparator.__ne__(self, other)

        def __eq__(self, other):
            if other is None:
                other = ''

            return String.Comparator.__eq__(self, other)

    def process_bind_param(self, value, dialect):
        if value is None:
            return ''
        else:
            return value

    def process_result_value(self, value, dialect):
        if value == '':
            return None
        else:
            return value


class StringBinaryType(TypeDecorator):
    """
    Stores value as a binary string in a VARBINARY column but automatically
    converts it to utf8-encoded string.

    This is because VARCHAR in MySQL ignores trailing spaces for comparison
    but we want that.
    """
    impl = VARBINARY

    def process_bind_param(self, value, dialect):
        if value is not None:
            return value.encode('utf8')

    def process_result_value(self, value, dialect):
        if value is not None:
            return value.decode('utf8')


class UserAndAlbum(Base):
    __tablename__ = 'users_and_albums'
    __table_args__ = ((Index('ix_users_and_albums_album_id_user_id', "album_id", "user_id", unique=True), ) +
                      Base.__table_args__)

    id = Column(Integer, primary_key=True, autoincrement=True)
    album_id = Column(Integer, ForeignKey('albums.id', name='fk_users_and_albums_user_id'))
    user_id = Column(Integer, ForeignKey('users.id', name='fk_users_and_albums_album_id'))
    seen = Column(DateTime, index=True)

    album = relationship("Album")
    user = relationship("User")

    def __init__(self, album_id, user_id):
        self.album_id = album_id
        self.user_id = user_id


class ListenedTrack(Base):
    __tablename__ = 'listened_tracks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), index=True)
    artist_name = Column(String(255), index=True)
    album_name = Column(String(255), index=True)
    timestamp = Column(Integer, index=True)

    user_id = Column(Integer, ForeignKey('users.id', name='fk_listened_tracks_user_id'))

    user = relationship("User")

    def __init__(self, user_id, name, artist_name, album_name, timestamp):
        self.user_id = user_id
        self.name = name
        self.artist_name = artist_name
        self.album_name = album_name
        self.timestamp = timestamp


class Track(Base):
    __tablename__ = 'tracks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(255), index=True, unique=True)
    name = Column(StringBinaryType(255), index=True)
    duration = Column(Integer)
    number = Column(String(8))
    format = Column(String(128))
    album_id = Column(Integer, ForeignKey('albums.id', name='fk_tracks_album_id'))
    artist_id = Column(Integer, ForeignKey('artists.id', name='fk_tracks_artist_id'))
    hash = Column(BINARY(24), index=True, unique=True)
    updated = Column(DateTime, index=True)
    created = Column(DateTime, index=True)
    bitrate = Column(Integer)
    sample_rate = Column(Integer)
    mode = Column(String(16))
    genre = Column(String(128))
    size = Column(BigInteger)
    invalid = Column(String(32), index=True)
    invalid_msg = Column(String(255))
    disc = Column(String(64))
    scanned = Column(Boolean, default=False, index=True)
    created_user_id = Column(Integer, ForeignKey('users.id', name='fk_tracks_created_user_id'))

    album = relationship("Album", lazy='joined', innerjoin=False)
    artist = relationship("Artist", lazy='joined', innerjoin=False)
    created_user = relationship("User", lazy='joined', innerjoin=False)
    paths = relationship("TrackPath", cascade='delete', order_by="TrackPath.path")

    def __init__(self, hash):
        self.hash = hash

    @hybrid_property
    def pretty_format(self):
        return Library.pretty_format(self.format)

    @hybrid_property
    def has_dups(self):
        return len(self.paths) > 1

    @hybrid_property
    def low_quality(self):
        if self.bitrate is not None:
            if self.format == "audio/mp3":
                # lame v4
                return self.bitrate < 165000
            if self.format == "audio/ogg":
                # vorbis aq 3
                return self.bitrate < 110000

        return False

    @hybrid_property
    def exists(self):
        for path in self.paths:
            if path.exists:
                return True

        return False

    def __str__(self):
        if self.artist is None and self.album is None:
            return "%s" % self.name
        elif self.artist is None:
            return "%s - %s" % (self.album.name, self.name)
        elif self.album is None:
            return "%s - %s" % (self.artist.name, self.name)
        else:
            return "%s - %s - %s" % (self.artist.name, self.album.name, self.name)


class Artist(Base):
    __tablename__ = 'artists'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(StringBinaryType(255), index=True, unique=True, nullable=False)
    slug = Column(String(255), index=True, unique=True)
    cover = deferred(Column(BLOB().with_variant(mysql.LONGBLOB(), 'mysql')))
    cover_large = deferred(Column(BLOB().with_variant(mysql.LONGBLOB(), 'mysql')))
    cover_path = Column(BLOB)
    cover_hash = Column(BINARY(24))

    # aggregated value updated from _updated
    updated = Column(DateTime, index=True)
    # aggregated value updated from _created
    created = Column(DateTime, index=True)

    albums = relationship("Album", secondary='tracks',
                          order_by="Album.date.desc(), Album.name")
    tracks = relationship("Track", order_by="Track.name")
    no_album_tracks = relationship("Track", primaryjoin="and_(Artist.id==Track.artist_id, Track.album_id==None)")

    _updated = column_property(select([func.max(Track.updated)])
                               .where(Track.artist_id == id).correlate_except(Track), deferred=True)

    _created = column_property(select([func.max(Track.created)])
                               .where(Track.artist_id == id).correlate_except(Track), deferred=True)

    def __init__(self, name):
        self.name = name

    @hybrid_property
    def va_count(self):
        return sum(album.is_va for album in self.albums)

    @hybrid_property
    def album_count(self):
        return sum(not album.is_va for album in self.albums)

    @hybrid_property
    def invalid(self):
        if len(self.tracks) == 0:
            return None

        invalids = set([])

        for track in self.tracks:
            if track.invalid is not None:
                invalids.add(track.invalid)

        if len(invalids) == 0:
            return None
        else:
            return list(invalids)


class Album(Base):
    __tablename__ = 'albums'
    __table_args__ = (Index('name_date', "name", "date", unique=True), ) + Base.__table_args__

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(StringBinaryType(255), nullable=False)
    slug = Column(String(255), index=True, unique=True)
    date = Column(StringNotNullType(32), index=True, nullable=False)
    cover = deferred(Column(BLOB().with_variant(mysql.LONGBLOB(), 'mysql')))
    cover_large = deferred(Column(BLOB().with_variant(mysql.LONGBLOB(), 'mysql')))
    cover_path = Column(BLOB)
    cover_hash = Column(BINARY(24))

    # aggregated value updated from _updated
    updated = Column(DateTime, index=True)
    # aggregated value updated from _created
    created = Column(DateTime, index=True)

    artists = relationship("Artist", secondary='tracks')
    tracks = relationship("Track", order_by="Track.disc, Track.number, Track.name")
    user_and_albums = relationship("UserAndAlbum", cascade='delete, delete-orphan')

    artist_count = column_property(select([func.count(distinct(Artist.id))])
                                   .select_from(Artist.__table__.join(Track.__table__))
                                   .where(Track.album_id == id), deferred=True)

    # TODO func.max() makes no sense for Track.format... maybe we should put
    #      format in a table so we can fetch the most used format in said album
    #      here instead.
    format = column_property(select([func.max(Track.format)])
                             .where(Track.album_id == id).correlate_except(Track), deferred=True)

    disc_count = column_property(select([func.count(distinct(Track.disc))])
                                 .where(Track.album_id == id)
                                 .correlate_except(Track), deferred=True)

    track_count = column_property(select([func.count(Track.id)])
                                  .where(Track.album_id == id).correlate_except(Track), deferred=True)

    duration = column_property(select([func.sum(Track.duration)])
                               .where(Track.album_id == id).correlate_except(Track), deferred=True)

    # used for updating updated
    _updated = column_property(select([func.max(Track.updated)])
                               .where(Track.album_id == id).correlate_except(Track), deferred=True)

    # used for updating created
    _created = column_property(select([func.max(Track.created)])
                               .where(Track.album_id == id).correlate_except(Track), deferred=True)

    def __init__(self, name, date, cover, cover_path, cover_hash):
        self.name = name
        self.date = date
        self.cover = cover
        self.cover_path = cover_path
        self.cover_hash = cover_hash

    @hybrid_property
    def pretty_format(self):
        return Library.pretty_format(self.format)

    @hybrid_property
    def is_split(self):
        return self.artist_count > 1 and self.artist_count <= 3

    @hybrid_property
    def is_ep(self):
        for match in ('EP', 'ep', 'E.P.', 'e.p.'):
            if re.search(r'\b%s$' % re.escape(match), self.name):
                return True

        return not (self.track_count > 6 or self.duration is not None and self.duration >= 60 * 20)

    @hybrid_property
    def is_va(self):
        return self.artist_count > 1

    @hybrid_property
    def low_quality(self):
        if len(self.tracks) == 0:
            return False

        return sum(int(track.low_quality) for track in self.tracks) > 0

    @hybrid_property
    def invalid(self):
        if len(self.tracks) == 0:
            return None

        invalids = set([])

        for track in self.tracks:
            if track.invalid is not None:
                invalids.add(track.invalid)

        if len(invalids) == 0:
            return None
        else:
            return list(invalids)

    @hybrid_property
    def created_user(self):
        if len(self.tracks) == 0:
            return None

        return self.tracks[0].created_user

    @hybrid_property
    def seen(self):
        if cherrypy.request.user is None:
            raise ValueError("Album.seen can only be used from a request")

        try:
            user_and_album = self._seen()
        except NoResultFound:
            return None

        return user_and_album.seen

    @seen.setter
    def seen(self, value):
        if cherrypy.request.user is None:
            raise ValueError("Album.seen can only be used from a request")

        session = Session.object_session(self)

        try:
            user_and_album = self._seen()
        except NoResultFound:
            user_and_album = UserAndAlbum(self.id, cherrypy.request.user.id)
            session.add(user_and_album)

        if value is True:
            value = datetime.datetime.utcnow()

        user_and_album.seen = value

    def _seen(self):
        session = Session.object_session(self)

        return (session.query(UserAndAlbum)
                .filter(UserAndAlbum.album_id == self.id, UserAndAlbum.user_id == cherrypy.request.user.id)
                .one())


class TrackPath(Base):
    __tablename__ = 'track_paths'

    id = Column(Integer, primary_key=True, autoincrement=True)
    path = Column(BLOB)
    filename = Column(BLOB)
    modified = Column(DateTime, index=True)
    dir = Column(BLOB)
    track_id = Column(Integer, ForeignKey('tracks.id', name='fk_track_paths_track_id'))

    track = relationship("Track")

    def __init__(self, path):
        self.path = path

    @validates('path')
    def _set_path(self, key, value):
        self.dir = os.path.dirname(value)
        self.filename = os.path.basename(value)
        self.modified = datetime.datetime.utcnow()
        return value

    @hybrid_property
    def pretty_path(self):
        path = self.path.decode('utf8', 'replace')

        if cherrypy.request.app is not None:
            library_path = os.path.abspath(cherrypy.request.app.config['opmuse']['library.path'])
            return path[len(library_path) + 1:]
        else:
            return path

    @hybrid_property
    def pretty_dir(self):
        pretty_path = self.pretty_path
        return "%s/" % os.path.dirname(pretty_path)

    @hybrid_property
    def exists(self):
        return os.path.exists(self.path)

    @hybrid_property
    def path_modified(self):
        if not os.path.exists(self.path):
            return None

        stat = os.stat(self.path)

        return datetime.datetime.fromtimestamp(stat.st_mtime)


class FileMetadata:

    def __init__(self, *args):
        self.artist_name = args[0]
        self.album_name = args[1]
        self.track_name = args[2]
        self.track_duration = args[3]
        self.track_number = args[4]
        self.updated = args[5]
        self.date = args[6]
        self.bitrate = args[7]
        self.invalid = args[8]
        self.invalid_msg = args[9]
        self.cover_path = args[10]
        self.artist_cover_path = args[11]
        self.disc = args[12]
        self.size = args[13]
        self.sample_rate = args[14]
        self.mode = args[15]
        self.genre = args[16]

        self.metadatas = args

        self.pos = 0

    def __iter__(self):
        return self

    def next(self):
        if self.pos > len(self.metadatas) - 1:
            raise StopIteration
        else:
            self.pos += 1
            return self.metadatas[self.pos - 1]

    def merge(self, metadata):

        metadatas = []

        while True:
            try:
                this = self.next()
                that = metadata.next()
            except StopIteration:
                break

            # merge strategy for lists are different from scalars
            # e.g. lists are extended and scalars set if previous value was None
            if isinstance(this, list) and isinstance(that, list):
                metadatas.append(this + that)
                continue

            if this is None:
                metadatas.append(that)
            else:
                metadatas.append(this)

        return FileMetadata(*metadatas)

    def __str__(self):
        return str(self.metadatas)


class TagParser:
    def is_supported(self, filename):
        extensions = self.supported_extensions()

        if extensions is None:
            return True

        ext = os.path.splitext(filename)[1].lower()[1:]

        return ext in extensions

    def supported_extensions(self):
        """
            Should return a list of supported file extensions this parser
            supports or None if it supports everything.
        """
        raise NotImplementedError()

    def parse(self, filename, metadata):
        raise NotImplementedError()


class MutagenParser(TagParser):
    def parse(self, filename, metadata):
        try:
            tag = self.get_tag(filename)
        except (IOError, ValueError) as error:
            log("Got '%s' when parsing '%s'" % (error, filename.decode('utf8', 'replace')))
            return FileMetadata(*(((None, ) * 8) + (['broken_tags'], "Mutagen: %s" % error) + ((None, ) * 7)))

        artist = str(tag['artist'][0]) if 'artist' in tag else None
        album = str(tag['album'][0]) if 'album' in tag else None
        track = str(tag['title'][0]) if 'title' in tag else None
        duration = tag.info.length
        number = str(tag['tracknumber'][0]) if 'tracknumber' in tag else None
        date = str(tag['date'][0]) if 'date' in tag else None
        bitrate = tag.info.bitrate if hasattr(tag.info, 'bitrate') else None
        sample_rate = tag.info.sample_rate if hasattr(tag.info, 'sample_rate') else None
        disc = str(tag['discnumber'][0]) if 'discnumber' in tag else None

        if date == '':
            date = None

        mode = None

        if hasattr(tag.info, 'mode'):
            if tag.info.mode in (mutagen.mp3.STEREO, mutagen.mp3.JOINTSTEREO, mutagen.mp3.DUALCHANNEL):
                mode = 'stereo'
            elif tag.info.mode == mutagen.mp3.MONO:
                mode = 'mono'
        elif hasattr(tag.info, 'channels'):
            if tag.info.channels == 2:
                mode = 'stereo'
            elif tag.info.channels == 1:
                mode = 'mono'

        genre = str(','.join(tag['genre'])) if 'genre' in tag and len(tag['genre']) > 0 else None

        if genre is not None:
            genre = genre.strip()

            if len(genre) == 0:
                genre = None

        if artist is not None and len(artist) == 0:
            artist = None

        if album is not None and len(album) == 0:
            album = None

        if track is not None and len(track) == 0:
            track = None

        # won't fit in SQL INT, and i'm guessing something's up :|
        if bitrate is not None and bitrate > 2147483647:
            bitrate = None

        if number is not None and len(number) > 8:
            number = None

        if artist is None or track is None:
            invalid = ['incomplete_tags']
        else:
            invalid = ['valid']

        return FileMetadata(artist, album, track, duration, number, None, date,
                            bitrate, invalid, None, None, None, disc, None,
                            sample_rate, mode, genre)

    def get_tag(self, filename):
        raise NotImplementedError()


class MpcParser(MutagenParser):

    def get_tag(self, filename):
        return mutagen.musepack.Musepack(filename)

    def supported_extensions(self):
        return [b'mpc']


class ApeParser(MutagenParser):

    def get_tag(self, filename):
        return mutagen.apev2.APEv2File(filename)

    def supported_extensions(self):
        return [b'ape']


class WmaParser(MutagenParser):

    def get_tag(self, filename):
        return mutagen.asf.ASF(filename)

    def supported_extensions(self):
        return [b'wma']


class FlacParser(MutagenParser):

    def get_tag(self, filename):
        return mutagen.flac.FLAC(filename)

    def supported_extensions(self):
        return [b'flac']


class Mp4Parser(MutagenParser):

    def get_tag(self, filename):
        return mutagen.easymp4.EasyMP4(filename)

    def supported_extensions(self):
        return [b'm4p', b'mp4', b'm4a']


class OggParser(MutagenParser):

    def get_tag(self, filename):
        return mutagen.oggvorbis.OggVorbis(filename)

    def supported_extensions(self):
        return [b'ogg']


class Id3Parser(MutagenParser):

    def get_tag(self, filename):
        return mutagen.mp3.MP3(filename, ID3=mutagen.easyid3.EasyID3)

    def supported_extensions(self):
        return [b'mp3', b'mp2']


class FsParser(TagParser):
    """
    Get file-specific data like size and mtime and also covers.

    Note that the only time the cover matching actually works is when we do our
    bootup-scan. Because upon uploading files and editing files (which causes a
    move) the covers will get moved/uploaded to the relevant folder *after* all
    tracks have been moved or in the case of upload we will have a bit of
    asynchronicity at work.
    """

    def parse(self, filename, metadata):
        stat = os.stat(filename)
        updated = datetime.datetime.fromtimestamp(stat.st_mtime)
        size = stat.st_size

        track_dir = os.path.dirname(filename)

        track_dir_files = []

        for file in os.listdir(track_dir):
            # ignore media files
            if Library.is_supported(file):
                continue

            track_dir_files.append(os.path.join(track_dir, file))

        album_cover_match = []

        if metadata is not None and metadata.album_name is not None:
            album_slug = LibraryProcess.slugify(metadata.album_name)[1]
            album_cover_match.append(
                ('.*%s.*\.(jpg|png|gif)$' % re.escape(album_slug)).encode("utf8")
            )

        album_cover_match += [
            b'.*(cover|front|folder).*\.(jpg|png|gif)$',
            b'.*\.(jpg|png|gif)$'
        ]

        album_cover_path = self.match_in_dir(album_cover_match, track_dir_files)

        artist_cover_path = None

        if metadata is not None and metadata.artist_name is not None:
            artist_slug = LibraryProcess.slugify(metadata.artist_name)[1]

            artist_cover_match = [
                ('.*%s.*\.(jpg|png|gif)$' % re.escape(artist_slug)).encode("utf8")
            ]

            artist_cover_path = self.match_in_dir(artist_cover_match, track_dir_files)

        return FileMetadata(None, None, None, None, None, updated, None, None,
                            None, None, album_cover_path, artist_cover_path,
                            None, size, None, None, None)

    @staticmethod
    def match_in_dir(match_files, files):
        match = None

        for match_file in match_files:
            for file in files:
                if re.match(match_file, os.path.basename(file), flags=re.IGNORECASE):
                    match = file
                    break

            if match is not None:
                break

        return match

    def supported_extensions(self):
        return None


class TagReader:
    def __init__(self):
        self._by_filename = {}

        self._mutagen_parsers = [
            Id3Parser(),
            OggParser(),
            Mp4Parser(),
            FlacParser(),
            WmaParser(),
            ApeParser(),
            MpcParser(),
        ]
        self._parsers = []

        self._parsers.extend(self._mutagen_parsers)
        self._parsers.append(FsParser())

    def parse_mutagen(self, filename):
        return self.parse(filename, self._mutagen_parsers)

    def parse(self, filename, parsers=None):
        metadata = None

        if parsers is None:
            parsers = self._parsers

        for parser in parsers:
            if not parser.is_supported(filename):
                continue

            new_metadata = parser.parse(filename, metadata)

            if not isinstance(new_metadata, FileMetadata):
                raise Exception("TagParser.parse must return a FileMetadata instance.")

            if metadata is not None:
                metadata = metadata.merge(new_metadata)
            else:
                metadata = new_metadata

        return metadata

    def get_mutagen_tag(self, filename):
        for parser in self._mutagen_parsers:
            if not parser.is_supported(filename):
                continue

            return parser.get_tag(filename)

        raise ValueError('Unsupported filetype.')


reader = TagReader()


class StructureParser:

    def __init__(self, filename, data_override={}, data_fallback={}):
        config = cherrypy.tree.apps[''].config['opmuse']
        self._fs_structure = config['library.fs.structure']
        self._path = os.path.abspath(config['library.path']).encode('utf8')
        self._filename = None if filename is None else os.path.abspath(filename)
        self._data_override = data_override
        self._data_fallback = data_fallback

    def is_valid(self):
        if self._filename is None:
            raise ValueError('filename was not provided, can\'t use is_valid().')

        correct_path = self.get_path()
        actual_path = os.path.dirname(self._filename)[len(self._path):]

        return correct_path == actual_path

    def get_path(self, absolute=False):

        data = self.get_data()

        path_parts = self.split(self._fs_structure, ':')

        for name, value in data.items():
            if name in self._data_fallback and self._data_fallback[name] is not None:
                fallback_value = self._data_fallback[name]
            else:
                fallback_value = None

            if value is None and name == 'artist':
                if fallback_value is not None:
                    value = fallback_value
                else:
                    value = 'Unknown Artist'
            elif value is None and fallback_value is not None:
                value = fallback_value
            elif value is None:
                value = ''

            if name in self._data_override and self._data_override[name] is not None:
                value = self._data_override[name]

            value = value.replace('/', '_')

            def sub_callback(match):
                if value == '':
                    return ''

                new_value = value

                if match.group(2) is not None:
                    fixes = match.group(2).split('!')

                    if len(fixes) > 1:
                        prefix, suffix = fixes
                    else:
                        prefix, suffix = fixes[0], ''

                    if prefix:
                        new_value = "%s%s" % (prefix, new_value)

                    if suffix:
                        new_value = "%s%s" % (new_value, suffix)

                return new_value

            for index, part in enumerate(path_parts):
                path_parts[index] = re.sub(r':%s(!([^:/]+))?' % name, sub_callback, part)

        path = ''

        for part in path_parts:
            path += part

        path = re.sub(r'[/]+', '/', path)

        if path[len(path) - 1] == '/':
            path = path[0:(len(path) - 1)]

        if len(path) == 0:
            return None

        if not absolute and path[0] != '/':
            path = '/%s' % path
        elif absolute:
            path = path[1:]

        path = path.encode('utf8')

        if absolute:
            return os.path.join(self._path, path)
        else:
            return path

    def get_data(self):
        raise NotImplementedError()

    @staticmethod
    def split(split, sep):
        splits = re.split('([^%s]*)' % sep, split)

        new_splits = []

        length = len(splits)

        if length % 2 != 0:
            length -= 1

        for index in range(0, length, 2):
            new_splits.append('%s%s' % (splits[index], splits[index + 1]))

        return new_splits


class TrackStructureParser(StructureParser):

    def __init__(self, track, filename=None, data_override={}, data_fallback={}):
        StructureParser.__init__(self, filename, data_override, data_fallback)
        self._track = track

    def get_data(self):
        return {
            'artist': self._track.artist.name if self._track.artist is not None else None,
            'album': self._track.album.name if self._track.album is not None else None,
            'disc': self._track.disc,
            'date': self._track.album.date if self._track.album is not None else None,
        }


class MetadataStructureParser(StructureParser):

    def __init__(self, metadata, filename=None, data_override={}, data_fallback={}):
        StructureParser.__init__(self, filename, data_override, data_fallback)
        self._metadata = metadata

    def get_data(self):
        if self._metadata is not None:
            return {
                'artist': self._metadata.artist_name,
                'album': self._metadata.album_name,
                'disc': self._metadata.disc,
                'date': self._metadata.date,
            }
        else:
            return {
                'artist': None,
                'album': None,
                'disc': None,
                'date': None
            }


class Library:

    # TODO figure out from TagParsers?
    SUPPORTED = [b"mp3", b"ogg", b"flac", b"wma", b"m4p", b"mp4", b"m4a",
                 b"ape", b"mpc", b"wav", b"mp2"]

    def __init__(self, path, use_opmuse_txt):
        self.scanning = False
        self.running = None
        self.files_found = None
        self.processed = None
        self.path = path
        self.use_opmuse_txt = use_opmuse_txt
        self.threads = []

    @staticmethod
    def pretty_format(format):
        if format == "audio/flac":
            format = "flac"
        elif format == "audio/mp3":
            format = "mp3"
        elif format == 'audio/x-ms-wma':
            format = "wma"
        elif format == 'audio/mp4a-latm':
            format = "mp4"
        elif format == 'audio/ogg':
            format = "ogg"
        elif format == 'audio/x-ape':
            format = "ape"
        elif format == 'audio/x-musepack':
            format = "mpc"
        elif format == 'audio/wav':
            format = "wav"

        return format

    def start(self):
        start_time = time.time()

        self.scanning = True
        self.running = True
        self.processed = 0

        try:
            self._database_type = get_database_type()
            self._database = get_session()

            # always treat paths as bytes to avoid encoding issues we don't
            # care about
            path = self.path.encode() if isinstance(self.path, str) else self.path

            path = os.path.abspath(path)

            log("Starting library update.")

            old_files = 0

            # remove paths that doesn't exist anymore
            for track in self._database.query(Track).all():
                for track_path in track.paths:
                    # remove path if it has "moved" outside of library path or it
                    # doesn't exist anymore. it might have been moved in which case
                    # it will be found by the LibraryProcess and re-added to the Track
                    if track_path.path.find(path) != 0 or not os.path.exists(track_path.path):
                        self._database.delete(track_path)
                        self._database.commit()
                        old_files += 1

            if old_files > 0:
                log("%d old files removed from database." % old_files)

            files_found = 0

            queue = []

            for path, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    if Library.is_supported(filename):

                        files_found += 1

                        filename = os.path.join(path, filename)

                        queue.append(filename)

            self.files_found = files_found

            log("%d files found." % files_found)

            # sqlite doesn't support threaded writes so just run one thread if
            # that's what we have
            if self._database_type == 'sqlite':
                thread_num = 1
            else:
                thread_num = math.ceil(cpu_count() / 2)
                thread_num = thread_num if thread_num > 2 else 2

            queue_len = len(queue)
            chunk_size = math.ceil(queue_len / thread_num)

            to_process = []

            no = 0

            for index, filename in enumerate(queue):
                to_process.append(filename)

                if index > 0 and index % chunk_size == 0 or index == queue_len - 1:
                    p = Thread(target=LibraryProcess, name="LibraryProcess_%d" % no,
                               args=(self.path, self.use_opmuse_txt, to_process, None, no, None, self))
                    p.start()

                    self.threads.append(p)

                    to_process = []
                    no += 1

            for thread in self.threads:
                thread.join()

            self.threads = []

            if self.running:
                for track in self._database.query(Track).all():
                    # remove tracks without any paths (e.g. removed since previous search)
                    #
                    # because if the file moved it will be found by the hash and just have
                    # the new path readded as opposed to when it was completely removed
                    # from the library path
                    if len(track.paths) == 0:
                        library_dao.delete_track(track, self._database)

            self._database.commit()
            self._database.remove()

            if self.running:
                msg = "Done updating library, in {0} seconds."
            else:
                msg = "Stopped updating library"

            log(msg.format(round(time.time() - start_time)))
        except:
            log('Failed to update library.', traceback=True)
            raise
        finally:
            self.scanning = False
            self.running = False

    def stop(self):
        if self.running:
            log("Stop updating library.")

            self.running = False

            for thread in self.threads:
                thread.join()

    @staticmethod
    def is_supported(filename):
        if filename is None:
            return False

        return os.path.splitext(filename)[1].lower()[1:] in Library.SUPPORTED


class OpmuseTxt:
    """
    Class for processing opmuse.txt files.

    Because the opmuse.txt files are stored in a track's folder there will most likely
    be one opmuse.txt for several files. This of course depends on your fs structure
    though. Right now there's no real "priority" to which track actually gets to write
    its data to this file, or some other summarization or whatever, whatever file in
    whatever thread to acquire the lock first will be the authority.
    """

    TRIES = 20
    """
    How many times to try to acquire a lock before giving up.
    """

    def __init__(self, filename):
        self.filename = filename
        self.opmuse_txt = os.path.join(os.path.dirname(self.filename), b'opmuse.txt')

    def process(self, database, track):
        """
        Stores and retrieves "additional data" to and from opmuse.txt files.
        """

        for i in range(0, OpmuseTxt.TRIES):
            try:
                lock = LockFile(self.opmuse_txt + b'.lock')

                # if there's a opmuse.txt file use its data for this track
                if os.path.exists(self.opmuse_txt):
                    data = self.unserialize()
                    self.put_track(database, data, track)
                # if there's no opmuse.txt file write this tracks data to it
                else:
                    data = {}
                    self.put_data(database, track, data)
                    self.serialize(data)

                # in the future we might want to store data in opmuse.txt that will
                # change after first creation. then we'll have to add code here ^^

                lock.release()
                lock.remove()
            except LockError:
                if i == OpmuseTxt.TRIES - 1:
                    warn("Failed to acquire lock for %s, giving up.\n" % self.opmuse_txt, traceback=True)
                    break

                time.sleep(.5)

    def put_track(self, database, data, track):
        """
        Gets data from opmuse.txt and sets it on the track entity.
        """

        if 'created' in data:
            try:
                track.created = datetime.datetime.strptime(data['created'][0:19], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                log('Error occured while reading created from %s, ignoring.' % self.opmuse_txt, traceback=True)

        if 'created_user' in data:
            try:
                track.created_user = database.query(User).filter(User.login == data['created_user']).one()
            except NoResultFound:
                log('Error occured while reading created_user from %s, ignoring.' % self.opmuse_txt, traceback=True)

    def put_data(self, database, track, data):
        """
        Takes data from the track entity and sets it in opmuse.txt
        """

        if 'created' not in data:
            data['created'] = track.updated

        if 'created_user' not in data and track.created_user is not None:
            data['created_user'] = track.created_user.login

    def unserialize(self):
        data = {}

        with open(self.opmuse_txt, "r") as f:
            for line in f:
                if line[0] == '#':
                    continue

                key, value = line.split(':', 1)

                data[key.strip()] = value.strip()

        return data

    def serialize(self, data):
        with open(self.opmuse_txt, "w") as f:
            f.write('# opmuse file, used to store additional data. don\'t edit directly.\n')

            for key, value in data.items():
                if isinstance(value, datetime.datetime):
                    value = value.isoformat()

                f.write('%s: %s\n' % (key, value))


class LibraryProcess:
    def __init__(self, path, use_opmuse_txt, queue, database=None, no=-1,
                 tracks=None, library=None, user=None, artist_name_fallback=None):
        self.path = path
        self.no = no
        self.user = user
        self.use_opmuse_txt = use_opmuse_txt

        queue_len = len(queue)

        log('Process %d about to process %d files.' % (self.no, queue_len))

        if database is None:
            self._database = get_session()
        else:
            self._database = database

        count = 1
        processed = 0
        start = time.time()

        stopped = False

        artist_ids = set()
        album_ids = set()

        for filename in queue:
            if library is not None and library.running is False:
                stopped = True

            try:
                track = self.process(filename, artist_name_fallback)
            except:
                log('Failed processing %s' % filename.decode('utf8', 'replace'), traceback=True)
                continue

            if tracks is not None:
                tracks.append(track)

            if track.artist_id is not None:
                artist_ids.add(track.artist_id)

            if track.album_id is not None:
                album_ids.add(track.album_id)

            # update aggregated values every 1000 tracks, to avoid these
            # queries becoming huge and more evenly distributing the load of 'em
            if count == 1000 or processed + 1 == queue_len or stopped:
                tries = 10

                for artist in self._database.query(Artist).filter(Artist.id.in_(artist_ids)).all():
                    # try 10 times when we get a deadlock and then give up
                    for i in range(0, tries):
                        try:
                            # update aggregated artist.updated value based on artist._updated
                            artist.updated = artist._updated
                            artist.created = artist._created

                            self._database.commit()
                            break
                        except ProgrammingError:
                            if i == tries - 1:
                                log("Failed updating artist aggregated values.", traceback=True)
                                break

                            self._database.rollback()
                            time.sleep(.1)

                artist_ids.clear()

                for album in self._database.query(Album).filter(Album.id.in_(album_ids)).all():
                    # try 10 times when we get a deadlock and then give up
                    for i in range(0, tries):
                        try:
                            # update aggregated album.updated value based on album._updated
                            album.updated = album._updated
                            album.created = album._created

                            self._database.commit()
                            break
                        except ProgrammingError:
                            if i == tries - 1:
                                log("Failed updating album aggregated values.", traceback=True)
                                break

                            self._database.rollback()
                            time.sleep(.1)

                album_ids.clear()

                log('Process %d processed %d files in %d seconds.' %
                    (self.no, count, time.time() - start))
                start = time.time()
                count = 0

            count += 1
            processed += 1

            if library is not None:
                library.processed += 1

            if stopped:
                break

        if database is None:
            self._database.remove()

        queue_len = len(queue)

        if stopped:
            msg = 'Process {0} was stopped, {1} of {2} ({3}%) files processed.'
        else:
            msg = 'Process {0} is done processing all {2} files.'

        log(msg.format(self.no, processed, queue_len, round((processed / queue_len) * 100)))

    def process(self, filename, artist_name_fallback=None):
        hash = LibraryProcess.get_hash(filename)

        try:
            track = Track(hash)
            self._database.add(track)
            self._database.commit()
        except IntegrityError:
            self._database.rollback()
            track = self._database.query(Track).filter_by(hash=hash).one()

            if track.scanned:
                # if this file isnt part of the track's paths then add it.
                # it might just have moved and we add it here and the other
                # one will be removed last in the scanning process...
                if filename not in [path.path for path in track.paths]:
                    track_path = TrackPath(filename)
                    track_path.track_id = track.id

                    self._database.add(track_path)
                    self._database.commit()

                return track

        metadata = reader.parse(filename)

        # change track slug until successful
        track_slug_index, track.slug = self.get_track_slug(metadata)

        i = 0

        while True:
            i += 1

            try:
                self._database.commit()
                break
            except IntegrityError:
                self._database.rollback()

                track_slug_index, track.slug = self.get_track_slug(metadata, track_slug_index + i)

        artist = None
        album = None

        if metadata.artist_name is None:
            artist_name = artist_name_fallback
        else:
            artist_name = metadata.artist_name

        if artist_name is not None:
            try:
                artist = Artist(artist_name)

                self._database.add(artist)
                self._database.commit()

                search.add_artist(artist)
            except IntegrityError:
                # we get an IntegrityError if the unique constraint kicks in
                # in which case the artist already exists so fetch it instead.
                self._database.rollback()
                artist = self._database.query(Artist).filter_by(
                    name=artist_name
                ).one()

            # change artist slug until successful
            artist_slug_index, artist.slug = self.get_artist_slug(metadata)

            i = 0

            while True:
                i += 1

                try:
                    self._database.commit()
                    break
                except IntegrityError:
                    self._database.rollback()

                    artist_slug_index, artist.slug = self.get_artist_slug(metadata, artist_slug_index + i)

        if metadata.album_name is not None:
            try:
                album = Album(metadata.album_name, metadata.date, None, metadata.cover_path, None)
                self._database.add(album)
                self._database.commit()
                search.add_album(album)
            except IntegrityError:
                self._database.rollback()
                album = self._database.query(Album).filter_by(
                    name=metadata.album_name, date=metadata.date
                ).one()

            # change album slug until successful
            album_slug_index, album.slug = self.get_album_slug(metadata)

            i = 0

            while True:
                i += 1

                try:
                    self._database.commit()
                    break
                except IntegrityError:
                    self._database.rollback()

                    album_slug_index, album.slug = self.get_album_slug(metadata, album_slug_index + i)

        if album is not None and album.cover_path is None:
            album.cover_path = metadata.cover_path
            self._database.commit()

        if artist is not None and artist.cover_path is None:
            artist.cover_path = metadata.artist_cover_path
            self._database.commit()

        ext = os.path.splitext(filename)[1].lower()

        if ext == b".mp3" or ext == b".mp2":
            format = 'audio/mp3'
        elif ext == b".wma":
            format = 'audio/x-ms-wma'
        elif ext == b".m4a" or ext == b".m4p" or ext == b".mp4":
            format = b'audio/mp4a-latm'
        elif ext == b".flac":
            format = 'audio/flac'
        elif ext == b".ogg":
            format = 'audio/ogg'
        elif ext == b".ape":
            format = 'audio/x-ape'
        elif ext == b".mpc":
            format = 'audio/x-musepack'
        elif ext == b".wav":
            format = 'audio/wav'
        else:
            format = 'audio/unknown'

        track.name = metadata.track_name
        track.duration = metadata.track_duration
        track.number = LibraryProcess.fix_track_number(metadata.track_number)
        track.format = format
        track.updated = metadata.updated
        track.created = metadata.updated
        track.bitrate = metadata.bitrate
        track.sample_rate = metadata.sample_rate
        track.mode = metadata.mode
        track.genre = metadata.genre
        track.size = metadata.size
        track.disc = metadata.disc

        if metadata.invalid == ['valid']:
            track.invalid = None
        else:
            invalid = metadata.invalid

            try:
                invalid.remove('valid')
            except ValueError:
                pass

            track.invalid = invalid[0] if len(invalid) > 0 else ''
            track.invalid_msg = metadata.invalid_msg

        if album is not None:
            track.album_id = album.id

        if artist is not None:
            track.artist_id = artist.id

        track_path = TrackPath(filename)
        track_path.track_id = track.id

        self._database.add(track_path)

        track.created_user = self.user

        track.scanned = True

        if self.use_opmuse_txt:
            opmuse_txt = OpmuseTxt(filename)
            opmuse_txt.process(self._database, track)

        self._database.commit()

        search.add_track(track)

        return track

    @staticmethod
    def fix_track_number(number):
        """
        pads track number with zero so we can sort it nicely with a regular
        alphanumeric sort
        """

        if number is None:
            return None

        if len(number) == 1:
            number = "0%s" % number

        for separator in ['/', '-']:
            if separator in number:
                split = number.split(separator)

                if len(split[0]) == 1:
                    split[0] = "0%s" % split[0]

                number = separator.join(split)
                break

        return number

    def get_track_slug(self, metadata, index=0):
        if metadata.artist_name is None and metadata.album_name is None:
            slug = metadata.track_name
        elif metadata.artist_name is None:
            slug = "%s_%s" % (metadata.album_name, metadata.track_name)
        elif metadata.album_name is None:
            slug = "%s_%s" % (metadata.artist_name, metadata.track_name)
        else:
            slug = "%s_%s_%s" % (metadata.artist_name, metadata.album_name, metadata.track_name)

        index, track_slug = LibraryProcess.slugify(
            slug, index
        )

        return index, track_slug

    def get_album_slug(self, metadata, index=0):
        return LibraryProcess.slugify(metadata.album_name, index)

    def get_artist_slug(self, metadata, index=0):
        return LibraryProcess.slugify(metadata.artist_name, index)

    @staticmethod
    def slugify(string, index=0):
        if string is None:
            string = ""

        if index > 0:
            index_str = str(index)
            string = "%s_%s" % (string[:(255 - len(index_str))], index_str)
        else:
            string = string[:255]

        string = string.lower()

        # Disallow certain slug values that will conflict with urls.
        # Would be nice if this was automatic (search through controllers for all top-level url components).
        if string in ('library', 'users', 'upload', 'logout', 'login', 'search',
                      'queue', 'cover', 'font', 'va', 'unknown', 'download', 'settings'):
            index += 1
            return LibraryProcess.slugify(string, index)

        string = unidecode(string)

        string = string.lower()

        string = re.sub(r'[^A-Za-z0-9_\'"()$-]+', '_', string)

        string = string.strip('_')

        if len(string) == 0:
            string = "_"

        return index, string

    @staticmethod
    def get_hash(filename):
        import mmh3

        byte_size = 1024 * 128

        with open(filename, "rb", 0) as f:
            # fetch first 128k and last 128k to get a reasonably secure
            # unique set of bytes from this file. also because id3 tags
            # might be located at the end or the beginning of a file,
            # we want to be able to detect changes to them

            if os.path.getsize(filename) < byte_size * 2:
                bytes = f.read()
            else:
                begin_bytes = f.read(byte_size)
                f.seek(-byte_size, io.SEEK_END)
                end_bytes = f.read(byte_size)
                bytes = begin_bytes + end_bytes

            return base64.b64encode(mmh3.hash_bytes(bytes))


class LibraryDao:

    def get_listened_tracks_by_timestmap(self, timestamp):
        return (get_database().query(ListenedTrack).order_by(ListenedTrack.timestamp.desc())
                .filter(ListenedTrack.timestamp > timestamp).all())

    def get_listened_tracks(self, limit):
        return get_database().query(ListenedTrack).order_by(ListenedTrack.timestamp.desc()).limit(limit).all()

    def get_listened_track_by_artist_name(self, user_id, artist_name):
        try:
            return (get_database().query(ListenedTrack)
                    .filter(ListenedTrack.user_id == user_id, ListenedTrack.artist_name == artist_name)
                    .order_by(ListenedTrack.timestamp.desc()).limit(1).one())
        except NoResultFound:
            return None

    def get_listened_tuples_by_artist_name_for_users(self, artist_name):
        try:
            return (get_database().query(ListenedTrack.user_id, func.max(ListenedTrack.timestamp))
                    .filter(ListenedTrack.artist_name == artist_name)
                    .group_by(ListenedTrack.user_id)
                    .order_by(ListenedTrack.timestamp.desc()).all())
        except NoResultFound:
            return None

    def get_listened_artist_name_count(self, user_id, start_date=None, end_date=None, limit=None):
        try:
            query = (get_database().query(ListenedTrack.artist_name, func.count(ListenedTrack.id).label('count'))
                     .filter(ListenedTrack.user_id == user_id)
                     .group_by(ListenedTrack.artist_name)
                     .order_by('count DESC'))

            if start_date is not None:
                query = query.filter(ListenedTrack.timestamp > int(start_date.timestamp()))

            if end_date is not None:
                query = query.filter(ListenedTrack.timestamp < int(end_date.timestamp()))

            if limit is not None:
                query = query.limit(limit)

            return query.all()
        except NoResultFound:
            return None

    def get_listened_tuples_by_artist_name_and_album_name_for_users(self, artist_name, album_name):
        try:
            return (get_database().query(ListenedTrack.user_id, func.max(ListenedTrack.timestamp))
                    .filter(ListenedTrack.artist_name == artist_name, ListenedTrack.album_name == album_name)
                    .group_by(ListenedTrack.user_id)
                    .order_by(ListenedTrack.timestamp.desc()).all())
        except NoResultFound:
            return None

    def get_listened_track_by_artist_name_and_album_name(self, user_id, artist_name, album_name):
        try:
            return (get_database().query(ListenedTrack)
                    .filter(ListenedTrack.user_id == user_id, ListenedTrack.artist_name == artist_name,
                            ListenedTrack.album_name == album_name)
                    .order_by(ListenedTrack.timestamp.desc()).limit(1).one())
        except NoResultFound:
            return None

    def get_listened_tracks_count(self, user_id):
        return (get_database().query(func.count(ListenedTrack.id))
                .filter(ListenedTrack.user_id == user_id).scalar())

    def get_listened_track_max_timestamp(self, user_id):
        return (get_database().query(func.max(ListenedTrack.timestamp))
                .filter(ListenedTrack.user_id == user_id).scalar())

    def add_listened_track(self, user_id, name, artist_name, album_name, timestamp):
        listened_track = ListenedTrack(user_id, name, artist_name, album_name, timestamp)

        get_database().add(listened_track)
        get_database().commit()

    def delete_listened_tracks(self, user_id):
        return (get_database().query(ListenedTrack)
                .filter(ListenedTrack.user_id == user_id).delete())

    def delete_track(self, track, database=None):
        if database is None:
            database = get_database()

        album = track.album
        artist = track.artist

        database.delete(track)
        database.commit()

        search.delete_track(track)

        # remove album if there is one and there are no tracks left on it
        if album is not None:
            # we need to expire manually or album.tracks will return the old value
            database.expire(album, ['tracks'])

            if len(album.tracks) == 0:
                self.delete_album(album, database)

        if artist is not None and len(artist.albums) > 0:
            database.expire(artist, ['albums'])

            if len(artist.albums) == 0:
                self.delete_artist(artist, database)

    def delete_album(self, album, database=None):
        if database is None:
            database = get_database()

        database.delete(album)
        database.commit()

        search.delete_album(album)

    def delete_artist(self, artist, database=None):
        if database is None:
            database = get_database()

        database.delete(artist)
        database.commit()

        search.delete_artist(artist)

    @memoize
    def get_track(self, id):
        try:
            return get_database().query(Track).filter_by(id=id).one()
        except NoResultFound:
            pass

    def get_track_ids_by_album_id(self, album_id):
        results = get_database().execute(select([Track.id]).where(Track.album_id == album_id))

        return [result[0] for result in results]

    def get_library_opmuse_txt(self):
        config = cherrypy.request.app.config['opmuse']

        if 'library.opmuse_txt' in config:
            return config['library.opmuse_txt']
        else:
            return True

    def get_library_path(self):
        library_path = os.path.abspath(cherrypy.request.app.config['opmuse']['library.path'])

        if library_path[-1] != "/":
            library_path += "/"

        return library_path

    def get_track_by_filename(self, filename):
        try:
            return (get_database().query(Track)
                    .join(TrackPath, Track.id == TrackPath.track_id)
                    .filter(TrackPath.filename == filename, Track.scanned)
                    .order_by(TrackPath.modified.desc())
                    .group_by(Track.id)
                    .limit(1)
                    .one())

        except NoResultFound:
            return

    def get_albums_by_created_user(self, user_id, limit=10):
        return (get_database().query(Album)
                .join(Track, Album.id == Track.album_id)
                .filter(Track.created_user_id == user_id)
                .group_by(Album.id)
                .order_by(Track.created.desc())
                .limit(limit).all())

    def get_track_by_path(self, path):
        try:
            return (get_database().query(Track)
                    .join(TrackPath, Track.id == TrackPath.track_id)
                    .filter(TrackPath.path == path, Track.scanned)
                    .group_by(Track.id).one())

        except NoResultFound:
            return

    def update_tracks_tags(self, tracks, move=False):
        filenames = []
        messages = []

        for _track in tracks:
            id = _track['id']
            artist_name = _track['artist']
            album_name = _track['album']
            track_name = _track['track']
            date = _track['date']
            number = _track['number']
            disc = _track['disc']

            try:
                track = get_database().query(Track).filter_by(id=id).one()
            except NoResultFound:
                continue

            for path in track.paths:
                try:
                    tag = reader.get_mutagen_tag(path.path)
                except Exception as error:
                    messages.append(('danger', "Failed to get tag for <strong>%s</strong> (%s)." %
                                    (path.path.decode('utf8', 'replace'), error)))
                    break

                cherrypy.engine.library_watchdog.add_ignores(path.path)

                filenames.append(path.path)

                tag['artist'] = artist_name
                tag['album'] = album_name
                tag['title'] = track_name

                if number is not None and number != '':
                    tag['tracknumber'] = number

                if date is not None and date != '':
                    tag['date'] = date

                if disc is not None and disc != '':
                    tag['discnumber'] = disc

                tag.save()
            else:
                self.delete_track(track)

        tracks, add_files_messages = self.add_files(filenames, move)

        return tracks, messages + add_files_messages

    def get_invalid_track_count(self):
        return (get_database().query(func.count(Track.id))
                .filter("invalid is not null", Track.scanned).scalar())

    def get_album_count(self):
        return get_database().query(func.count(Album.id)).scalar()

    def get_artist_count(self):
        return get_database().query(func.count(Artist.id)).scalar()

    def get_track_duration(self):
        duration = (get_database().query(func.sum(Track.duration))
                    .filter(Track.scanned).scalar())

        if duration is None:
            return 0
        else:
            return duration

    def get_track_size(self):
        size = (get_database().query(func.sum(Track.size))
                .filter(Track.scanned).scalar())

        if size is None:
            return 0
        else:
            return size

    def get_track_count(self):
        return (get_database().query(func.count(Track.id))
                .filter(Track.scanned).scalar())

    def get_track_path_count(self):
        return (get_database().query(func.count(TrackPath.id))
                .join(Track, Track.id == TrackPath.track_id)
                .filter(Track.scanned).scalar())

    def get_tracks_by_ids(self, ids):
        return (get_database().query(Track)
                .outerjoin(Album, Album.id == Track.album_id)
                .outerjoin(Artist, Artist.id == Track.artist_id)
                .filter(Track.id.in_(ids))
                .order_by(Artist.name)
                .order_by(Album.name)
                .order_by(Track.disc)
                .order_by(Track.number)
                .order_by(Track.name).all())

    def get_albums(self):
        return get_database().query(Album).all()

    def get_artists(self):
        return get_database().query(Artist).all()

    def get_tracks(self):
        return get_database().query(Track).all()

    def add_files(self, filenames, move=False, remove_dirs=True,
                  artist_name_override=None, artist_name_fallback=None, user=None):
        """
        Processes files and adds them as tracks with artists albums etc.

        user
            The user that added these tracks, will be used for created_user.

        artist_name_override
            This override's the artist name for the fs structure (e.g. what
            path/dir it will reside in)

        artist_name_fallback
            This provides a fallback for the artist name for both the fs
            structure and the track's entity.
        """

        paths = []
        messages = []
        old_dirs = set()
        moved_dirs = set()

        for filename in filenames:
            if os.path.splitext(filename)[1].lower()[1:] not in Library.SUPPORTED:
                continue

            if move:
                library_path = self.get_library_path()

                metadata = reader.parse_mutagen(filename)

                structure_parser = MetadataStructureParser(metadata, filename,
                                                           {'artist': artist_name_override},
                                                           {'artist': artist_name_fallback})

                dirname = structure_parser.get_path(absolute=True)
                old_dirname = os.path.dirname(filename)

                filename_basename = os.path.basename(filename)
                path = os.path.join(dirname, filename_basename)
                filename_basename = filename_basename.decode('utf8', 'replace')

                if dirname is None:
                    messages.append(('danger', '<strong>%s</strong>: Couldn\'t find appropriate path.' %
                                    filename_basename))
                    continue

                if os.path.exists(dirname):
                    if not os.path.isdir(dirname):
                        dirname = dirname[len(library_path) - 1:]
                        messages.append(('danger',
                                        ('<strong>%s</strong>: File\'s directory <strong>%s</strong> exists ' +
                                         'and is not a directory.') %
                                         (filename_basename, dirname.decode('utf8', 'replace'))))
                        continue
                else:
                    try:
                        os.makedirs(dirname)
                    except OSError as e:
                        if e.errno == 17:  # "File exists"
                            # if another thread (like in a parallel upload type scenario)
                            # already created it, we just ignore this error
                            pass
                        else:
                            raise e

                if path != filename:
                    if os.path.exists(path):
                        path_hash = LibraryProcess.get_hash(path)
                        filename_hash = LibraryProcess.get_hash(filename)

                        path = path[len(library_path) - 1:].decode('utf8', 'replace')

                        if path_hash != filename_hash:
                            messages.append(('danger', ('<strong>%s</strong>: A file already exists at ' +
                                                        '<strong>%s</strong> and it\'s not the same file, ' +
                                                        'you might want to investigate.') % (filename_basename, path)))
                        else:
                            messages.append(('warning', ('<strong>%s</strong>: A file already exists at ' +
                                                         '<strong>%s</strong> but it\'s the exact same file, ' +
                                                         'so don\'t worry.') % (filename_basename, path)))

                        continue

                    cherrypy.engine.library_watchdog.add_ignores([filename, path])

                    opmuse_txt = os.path.join(dirname, b'opmuse.txt')
                    old_opmuse_txt = os.path.join(old_dirname, b'opmuse.txt')

                    if os.path.exists(old_opmuse_txt) and not os.path.exists(opmuse_txt):
                        shutil.copy(old_opmuse_txt, opmuse_txt)

                    shutil.move(filename, path)

                    old_dirs.add(old_dirname)
                    moved_dirs.add((old_dirname, dirname))

                    paths.append(path)
                else:
                    paths.append(filename)
            else:
                paths.append(filename)

        tracks = []

        if len(paths) == 0:
            return tracks, messages

        LibraryProcess(self.get_library_path(), self.get_library_opmuse_txt(),
                       paths, get_database(), 0, tracks, user=user,
                       artist_name_fallback=artist_name_fallback)

        # move non-track files with folder if there's no tracks left in folder
        # i.e. album covers and such
        for from_dir, to_dir in moved_dirs:
            tracks_left = get_database().query(TrackPath).filter(TrackPath.dir == from_dir).count()

            if tracks_left == 0:
                for from_file in os.listdir(from_dir):
                    from_path = os.path.join(from_dir, from_file)
                    to_path = os.path.join(to_dir, from_file)

                    # if the "file" to be moved is a dir check if it contains
                    # any tracks and if it does, dont move it.
                    #
                    # this might happen when tracks from one dir moves into two
                    # subdirs of that dir.
                    if os.path.isdir(from_path):
                        tracks_left = get_database().query(TrackPath).filter(TrackPath.dir == from_path).count()

                        if tracks_left > 0:
                            continue

                    if os.path.exists(to_path):
                        messages.append(('info', '<strong>%s</strong>: The file <strong>%s</strong> already exists.' %
                                        (filename_basename, to_path.decode('utf8', 'replace'))))
                    else:
                        shutil.move(from_path, to_path)

        if remove_dirs:
            self.remove_empty_dirs(old_dirs)

        return tracks, messages

    def remove_empty_dirs(self, dirs):
        new_dirs = set()

        for dir in dirs:
            if not os.path.exists(dir):
                continue

            files = os.listdir(dir)

            opmuse_txt = os.path.join(dir, b'opmuse.txt')

            # remove empty dirs or dirs only containing a opmuse.txt, as
            # they are worthless on their own
            if len(files) == 0 or len(files) == 1 and b'opmuse.txt' in files:
                if os.path.exists(opmuse_txt):
                    os.remove(opmuse_txt)

                os.rmdir(dir)
                new_dirs.add(os.path.dirname(dir))
            elif len(files) > 1:
                # remove "leftover" opmuse.txt file
                only_files = []

                for file in files:
                    if not os.path.isdir(os.path.join(dir, file)):
                        only_files.append(file)

                if len(only_files) == 1 and b'opmuse.txt' in only_files:
                    os.remove(opmuse_txt)

        if len(new_dirs) > 0:
            self.remove_empty_dirs(new_dirs)

    @memoize
    def get_album(self, id):
        try:
            return get_database().query(Album).filter_by(id=id).one()
        except NoResultFound:
            pass

    def get_album_by_slug(self, slug):
        try:
            return get_database().query(Album).filter_by(slug=slug).one()
        except NoResultFound:
            pass

    @memoize
    def get_artist(self, id):
        try:
            return get_database().query(Artist).filter_by(id=id).one()
        except NoResultFound:
            pass

    def get_artist_by_slug(self, slug):
        try:
            return get_database().query(Artist).filter_by(slug=slug).one()
        except NoResultFound:
            pass

    def get_track_by_slug(self, slug):
        try:
            return get_database().query(Track).filter_by(slug=slug).one()
        except NoResultFound:
            pass

    def remove_paths(self, paths, remove=True):
        dirs = set()
        tracks = set()

        for path in paths:
            try:
                track_path = get_database().query(TrackPath).filter_by(path=path).one()
            except NoResultFound:
                continue

            dirs.add(os.path.dirname(path))

            if remove:
                cherrypy.engine.library_watchdog.add_ignores(path)
                os.remove(path)

            tracks.add(track_path.track)

            get_database().delete(track_path)

        get_database().commit()

        for track in tracks:
            path_count = get_database().query(TrackPath).filter_by(track_id=track.id).count()

            if path_count == 0:
                self.delete_track(track)

        get_database().commit()

        self.remove_empty_dirs(dirs)

    def remove(self, id):
        track = get_database().query(Track).filter_by(id=id).one()

        dirs = set()

        for path in track.paths:
            dirs.add(os.path.dirname(path.path))
            cherrypy.engine.library_watchdog.add_ignores(path.path)
            os.remove(path.path)

        album = track.album
        artist = track.artist

        self.delete_track(track)

        self.remove_empty_dirs(dirs)

        if album is not None and len(album.tracks) == 0:
            album = None

        if artist is not None and len(artist.albums) == 0:
            artist = None

        return artist, album

    def get_random_artists(self, limit):
        return self._get_random_entity(Artist, limit)

    def get_random_albums(self, limit):
        return self._get_random_entity(Album, limit)

    def _get_random_entity(self, Entity, limit):
        max_id = get_database().query(func.max(Entity.id)).one()[0]

        ids = []

        for i in range(0, limit * 10):
            ids.append(random.randrange(1, max_id))

        entities = (get_database()
                    .query(Entity)
                    .filter(Entity.id.in_(ids))
                    .order_by(func.rand())
                    .limit(limit)
                    .all())

        if len(entities) < limit:
            entities += self.get_random_entity(Entity, limit - len(entities))

        return entities


library_dao = LibraryDao()


class WatchdogEventHandler(FileSystemEventHandler):
    def __init__(self):
        FileSystemEventHandler.__init__(self)

        log("Watchdog watching for changes.")

        self.added = set()
        self.removed = set()

        self.ignores = set()

    def on_moved(self, event):
        FileSystemEventHandler.on_moved(self, event)

        if event.is_directory:
            return

        if not self.ignore(event.src_path) and Library.is_supported(event.src_path):
            self.removed.add(event.src_path)

            debug('Watchdog, removed %s' % event.src_path)

        if not self.ignore(event.dest_path) and Library.is_supported(event.dest_path):
            self.added.add(event.dest_path)

            debug('Watchdog, created %s' % event.dest_path)

    def on_created(self, event):
        FileSystemEventHandler.on_created(self, event)

        if event.is_directory or self.ignore(event.src_path) or not Library.is_supported(event.src_path):
            return

        self.added.add(event.src_path)

        debug('Watchdog, created %s' % event.src_path)

    def on_deleted(self, event):
        FileSystemEventHandler.on_deleted(self, event)

        if event.is_directory or self.ignore(event.src_path) or not Library.is_supported(event.src_path):
            return

        self.removed.add(event.src_path)

        debug('Watchdog, removed %s' % event.src_path)

    def on_modified(self, event):
        FileSystemEventHandler.on_modified(self, event)

        if event.is_directory or self.ignore(event.src_path) or not Library.is_supported(event.src_path):
            return

        self.added.add(event.src_path)

        debug('Watchdog, modified %s' % event.src_path)

    def pop_added(self):
        return self._pop_set(self.added)

    def pop_removed(self):
        return self._pop_set(self.removed)

    def ignore(self, ignore):
        try:
            self.ignores.remove(ignore)
            return True
        except KeyError:
            return False

    def add_ignores(self, ignores):
        if not isinstance(ignores, list):
            ignores = [ignores]

        for ignore in ignores:
            self.ignores.add(ignore)

    @staticmethod
    def _pop_set(collection):
        result = []

        if len(collection) == 0:
            return result

        while True:
            try:
                file = collection.pop()
                result.append(file)
            except KeyError:
                break

        return result


class LibraryWatchdogPlugin(SimplePlugin):

    def __init__(self, bus):
        SimplePlugin.__init__(self, bus)

        self.event_handler = None
        self.running = None

    def start(self):
        self.running = True

        config = cherrypy.tree.apps[''].config['opmuse']

        def run(self, library_path):
            self.event_handler = WatchdogEventHandler()

            observer = Observer()
            observer.schedule(self.event_handler, library_path, recursive=True)
            observer.start()

            while self.running:
                try:
                    database_data.database = get_session()

                    removed = self.event_handler.pop_removed()

                    if len(removed) > 0:
                        log("Watchdog removing %d files." % len(removed))
                        library_dao.remove_paths(removed, remove=False)

                    added = self.event_handler.pop_added()

                    if len(added) > 0:
                        log("Watchdog adding %d files." % len(added))
                        tracks, add_files_messages = library_dao.add_files(added, move=False, remove_dirs=False)

                    try:
                        database_data.database.commit()
                    except:
                        database_data.database.rollback()
                        raise
                    finally:
                        database_data.database.remove()
                        database_data.database = None

                    time.sleep(5)
                except:
                    log("Watchdog failed adding files.", traceback=True)
            else:
                observer.stop()

            observer.join()

        self.thread = Thread(
            name="LibraryWatchdog",
            target=run,
            args=(self, os.path.abspath(config['library.path']))
        )

        self.thread.start()

    start.priority = 115

    def stop(self):
        if self.running:
            self.running = False
            self.thread.join()

        self.thread = None

    def add_ignores(self, ignores):
        self.event_handler.add_ignores(ignores)


class LibraryPlugin(SimplePlugin):

    def __init__(self, bus):
        SimplePlugin.__init__(self, bus)
        self.library = None
        self.bus.subscribe("bind_library", self.bind_library)

    def start(self):
        config = cherrypy.tree.apps[''].config['opmuse']

        if 'library.opmuse_txt' in config:
            use_opmuse_txt = config['library.opmuse_txt']
        else:
            use_opmuse_txt = True

        def run(self, library_path, use_opmuse_txt):
            self.library = Library(library_path, use_opmuse_txt)
            self.library.start()

        self.thread = Thread(
            name="Library",
            target=run,
            args=(self, os.path.abspath(config['library.path']), use_opmuse_txt)
        )

        self.thread.start()

    start.priority = 110

    def bind_library(self):
        return self.library

    def stop(self):
        if self.library is not None:
            self.library.stop()
            self.thread.join()
            self.library = None
            self.thread = None


class LibraryTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.bind_library, priority=10)

    def bind_library(self):
        binds = cherrypy.engine.publish('bind_library')
        cherrypy.request.library = binds[0]
        cherrypy.request.library_dao = library_dao
