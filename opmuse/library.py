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
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from cherrypy.process.plugins import SimplePlugin
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
import mutagenx.mp3
import mutagenx.oggvorbis
import mutagenx.easymp4
import mutagenx.asf
import mutagenx.flac
import mutagenx.easyid3
import mutagenx.apev2
import mutagenx.musepack
import mutagenx as mutagen


__all__ = ['FileMetadata', 'library_dao', 'ApeParser', 'TrackStructureParser', 'Artist', 'OggParser',
           'StringBinaryType', 'LibraryDao', 'mutagen', 'IntegrityError', 'MpcParser', 'StructureParser',
           'LibraryProcess', 'reader', 'TagParser', 'Library', 'Id3Parser', 'WmaParser', 'Album', 'LibraryTool',
           'TagReader', 'PathParser', 'Mp4Parser', 'MutagenParser', 'MetadataStructureParser', 'TrackPath',
           'FlacParser', 'Track', 'LibraryPlugin']


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


def log(msg, traceback=False):
    cherrypy.log(msg, context='library', traceback=traceback)


class UserAndAlbum(Base):
    __tablename__ = 'users_and_albums'
    __table_args__ = ((Index('ix_users_and_albums_album_id_user_id', "album_id", "user_id", unique=True), ) +
                      Base.__table_args__)

    id = Column(Integer, primary_key=True, autoincrement=True)
    album_id = Column(Integer, ForeignKey('albums.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
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

    user_id = Column(Integer, ForeignKey('users.id'))

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
    album_id = Column(Integer, ForeignKey('albums.id'))
    artist_id = Column(Integer, ForeignKey('artists.id'))
    hash = Column(BINARY(24), index=True, unique=True)
    added = Column(DateTime, index=True)
    bitrate = Column(Integer)
    sample_rate = Column(Integer)
    mode = Column(String(16))
    genre = Column(String(128))
    size = Column(BigInteger)
    invalid = Column(String(32), index=True)
    invalid_msg = Column(String(255))
    disc = Column(String(64))
    scanned = Column(Boolean, default=False, index=True)
    upload_user_id = Column(Integer, ForeignKey('users.id'))

    album = relationship("Album", lazy='joined', innerjoin=False)
    artist = relationship("Artist", lazy='joined', innerjoin=False)
    upload_user = relationship("User", lazy='joined', innerjoin=False)
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
    name = Column(StringBinaryType(255), index=True, unique=True)
    slug = Column(String(255), index=True, unique=True)
    cover = deferred(Column(BLOB().with_variant(mysql.LONGBLOB(), 'mysql')))
    cover_large = deferred(Column(BLOB().with_variant(mysql.LONGBLOB(), 'mysql')))
    cover_path = Column(BLOB)
    cover_hash = Column(BINARY(24))

    # aggregated value updated from _added
    added = Column(DateTime, index=True)

    albums = relationship("Album", secondary='tracks',
                          order_by="Album.date.desc(), Album.name")
    tracks = relationship("Track", order_by="Track.name")
    no_album_tracks = relationship("Track", primaryjoin="and_(Artist.id==Track.artist_id, Track.album_id==None)")

    _added = column_property(select([func.max(Track.added)])
                             .where(Track.artist_id == id).correlate_except(Track), deferred=True)

    def __init__(self, name, slug):
        self.name = name
        self.slug = slug

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

    # aggregated value updated from _added
    added = Column(DateTime, index=True)

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

    # used for updating added
    _added = column_property(select([func.max(Track.added)])
                             .where(Track.album_id == id).correlate_except(Track), deferred=True)

    def __init__(self, name, date, slug, cover, cover_path, cover_hash):
        self.name = name
        self.date = date
        self.slug = slug
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
    def upload_user(self):
        if len(self.tracks) == 0:
            return None

        return self.tracks[0].upload_user

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
    track_id = Column(Integer, ForeignKey('tracks.id'))

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
        self.added = args[5]
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

    def parse(self, filename, metadata, path = None):
        raise NotImplementedError()


class MutagenParser(TagParser):
    def parse(self, filename, metadata, path = None):
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


class PathParser(TagParser):
    """
    Tries to find tags for file by looking at path components (e.g. containing folder
    might be album name, parent folder might be artist name ...)
    """

    def parse(self, filename, metadata, path = None):
        if path is None:
            raise ValueError('PathParser requires path to be specified.')

        bfilename = filename
        try:
            filename = filename.decode('utf8')
        except UnicodeDecodeError:
            try:
                filename = filename.decode('latin1')
            except UnicodeDecodeError:
                return FileMetadata(*(None, ) * 17)

        track_name = os.path.splitext(os.path.basename(filename))[0]
        track_name = track_name.replace("_", " ")

        path_comp = os.path.split(os.path.dirname(filename)[len(path) + (0 if path[-1] == os.sep else 1):])

        artist = album = None

        if len(path_comp[0]) > 0 and len(path_comp[1]) > 0:
            album = path_comp[1]
            path_comp = os.path.split(path_comp[0])
            artist = path_comp[1]
        elif len(path_comp[0]) == 0 and len(path_comp[1]) > 0:
            artist = path_comp[1]

        stat = os.stat(bfilename)
        added = datetime.datetime.fromtimestamp(stat.st_mtime)
        size = stat.st_size

        number = None

        track_dir = os.path.dirname(bfilename)

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

        orig_track_name = track_name

        match = re.search('([0-9]+)', track_name)

        if match is not None:
            number = match.group(0)
            start = match.start(0)
            end = match.end(0)

            track_name = "%s%s" % (track_name[0:start], track_name[end:])

            # i don't know of any albums with more than 100 tracks, so we're
            # going to assume it's not a track number if the number is greater
            # than that
            if int(number) > 100:
                number = None

        track_name = track_name.strip('\n -').split("-")[-1].strip()

        if len(track_name) == 0:
            track_name = orig_track_name

        disc_match = re.search(b'(cd|disc|disk)[^0-9]*([0-9]{1,2})', track_dir, flags = re.IGNORECASE)

        if disc_match:
            disc = disc_match.group(2).decode('utf8')
        else:
            disc = None

        if metadata is None or metadata.artist_name is None or metadata.track_name is None:
            invalid = ['missing_tags']
        else:
            invalid = []

        if metadata is not None:
            structure_parser = MetadataStructureParser(metadata, bfilename)

            if not structure_parser.is_valid():
                structure_parser = MetadataStructureParser(metadata, bfilename, {'artist': 'Various Artists'})

                if not structure_parser.is_valid():
                    invalid = ['dir']

        return FileMetadata(artist, album, track_name, None, number, added, None, None,
                            invalid, None, album_cover_path, artist_cover_path, disc, size,
                            None, None, None)

    @staticmethod
    def match_in_dir(match_files, files):
        match = None

        for match_file in match_files:
            for file in files:
                if re.match(match_file, os.path.basename(file), flags = re.IGNORECASE):
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
        self._parsers.append(PathParser())

    def parse_mutagen(self, filename):
        return self.parse(filename, self._mutagen_parsers)

    def parse(self, filename, parsers = None, path = None):
        metadata = None

        if parsers is None:
            parsers = self._parsers

        for parser in parsers:
            if not parser.is_supported(filename):
                continue

            new_metadata = parser.parse(filename, metadata, path)

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

    def __init__(self, filename, data_override = {}, data_fallback = {}):
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

    def get_path(self, absolute = False):

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

    def __init__(self, track, filename = None, data_override = {}, data_fallback = {}):
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

    def __init__(self, metadata, filename = None, data_override = {}, data_fallback = {}):
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

    def __init__(self, path):
        self.scanning = False
        self.running = None
        self.files_found = None
        self._path = path
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

        self._database_type = get_database_type()
        self._database = get_session()

        # always treat paths as bytes to avoid encoding issues we don't
        # care about
        path = self._path.encode() if isinstance(self._path, str) else self._path

        path = os.path.abspath(path)

        log("Starting library update.")

        # remove paths that doesn't exist anymore
        for track in self._database.query(Track).all():
            for track_path in track.paths:
                # remove path if it has "moved" outside of library path or it
                # doesn't exist anymore
                if track_path.path.find(path) != 0 or not os.path.exists(track_path.path):
                    self._database.delete(track_path)
                    self._database.commit()

        index = 0

        queue = []

        for path, dirnames, filenames in os.walk(path):
            for filename in filenames:
                if Library.is_supported(filename):

                    index += 1

                    filename = os.path.join(path, filename)

                    queue.append(filename)

        self.files_found = index

        log("%d files found" % index)

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
                p = Thread(target=LibraryProcess, args = (self._path, to_process, None, no, None, self),
                           name="LibraryProcess_%d" % no)
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

            for album in self._database.query(Album).all():
                # remove albums without tracks
                if len(album.tracks) == 0:
                    library_dao.delete_album(album, self._database)

            for artist in self._database.query(Artist).all():
                # remove artists without tracks
                if len(artist.tracks) == 0:
                    library_dao.delete_artist(artist, self._database)

        self._database.commit()
        self._database.remove()

        if self.running:
            msg = "Done updating library, in {0} seconds."
        else:
            msg = "Stopped updating library"

        log(msg.format(round(time.time() - start_time)))

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


class LibraryProcess:
    def __init__(self, path, queue, database = None, no = -1, tracks = None, library = None):

        self._path = path
        self.no = no

        log('Process %d about to process %d files.' %
            (self.no, len(queue)))

        if database is None:
            self._database = get_session()
        else:
            self._database = database

        count = 1
        processed = 0
        start = time.time()

        stopped = False

        if tracks is None:
            tracks = []

        for filename in queue:
            if library is not None and library.running is False:
                stopped = True
                break

            track = self.process(filename)

            tracks.append(track)

            if count == 1000:
                log('Process %d processed %d files in %d seconds.' %
                    (self.no, count, time.time() - start))
                start = time.time()
                count = 0

            count += 1
            processed += 1

        artists = set()
        albums = set()

        for track in tracks:
            if track.artist is not None:
                artists.add(track.artist)

            if track.album is not None:
                albums.add(track.album)

        tries = 10

        for artist in artists:
            # try 10 times when we get a deadlock and then give up
            for i in range(0, tries):
                try:
                    # update aggregated artist.added value based on artist._added
                    artist.added = artist._added

                    self._database.commit()
                    break
                except ProgrammingError:
                    if i == tries - 1:
                        log("Failed updating artist aggregated values.", traceback=True)
                        break

                    self._database.rollback()
                    time.sleep(.1)

        for album in albums:
            # try 10 times when we get a deadlock and then give up
            for i in range(0, tries):
                try:
                    # update aggregated album.added value based on album._added
                    album.added = album._added

                    self._database.commit()
                    break
                except ProgrammingError:
                    if i == tries - 1:
                        log("Failed updating album aggregated values.", traceback=True)
                        break

                    self._database.rollback()
                    time.sleep(.1)

        if database is None:
            self._database.remove()

        queue_len = len(queue)

        if stopped:
            msg = 'Process {0} was stopped, {1} of {2} ({3}%) files processed.'
        else:
            msg = 'Process {0} is done processing all {2} files.'

        log(msg.format(self.no, processed, queue_len, round((processed / queue_len) * 100)))

    def process(self, filename):
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

        metadata = reader.parse(filename, None, self._path)

        artist = None
        album = None

        if metadata.artist_name is not None:
            try:
                artist = self._database.query(Artist).filter_by(
                    name=metadata.artist_name
                ).one()
            except NoResultFound:
                artist_slug = self.get_artist_slug(metadata)
                artist = Artist(metadata.artist_name, artist_slug)

                self._database.add(artist)

                try:
                    self._database.commit()
                    search.add_artist(artist)
                except IntegrityError:
                    # we get an IntegrityError if the unique constraint kicks in
                    # in which case the artist already exists so fetch it instead.
                    self._database.rollback()
                    artist = self._database.query(Artist).filter_by(
                        name=metadata.artist_name
                    ).one()

        if metadata.album_name is not None:
            try:
                album_slug = self.get_album_slug(metadata)
                album = Album(metadata.album_name, metadata.date, album_slug, None, metadata.cover_path, None)
                self._database.add(album)
                self._database.commit()
                search.add_album(album)
            except IntegrityError:
                self._database.rollback()
                album = self._database.query(Album).filter_by(
                    name=metadata.album_name, date=metadata.date
                ).one()

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

        added = metadata.added

        track_slug = self.get_track_slug(metadata)

        track.slug = track_slug
        track.name = metadata.track_name
        track.duration = metadata.track_duration
        track.number = LibraryProcess.fix_track_number(metadata.track_number)
        track.format = format
        track.added = added
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

        # try slug change 10 times then give up
        tries = 10

        for i in range(0, tries):
            try:
                self._database.commit()
                break
            except IntegrityError:
                self._database.rollback()

                if i == tries - 1:
                    log("Failed adding track.", traceback=True)
                    break

                track.slug = self.get_track_slug(metadata)

        track_path = TrackPath(filename)
        track_path.track_id = track.id

        self._database.add(track_path)

        track.scanned = True

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

    def get_track_slug(self, metadata):
        index = 0
        track_slug = None

        while True:
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

            try:
                self._database.query(Track).filter_by(slug=track_slug).one()
            except NoResultFound:
                break

            index += 1

        return track_slug

    def get_album_slug(self, metadata):
        index = 0
        album_slug = None

        while True:
            index, album_slug = LibraryProcess.slugify(metadata.album_name, index)

            try:
                self._database.query(Album).filter_by(slug=album_slug).one()
            except NoResultFound:
                break

            index += 1

        return album_slug

    def get_artist_slug(self, metadata):
        index = 0
        artist_slug = None

        while True:
            index, artist_slug = LibraryProcess.slugify(metadata.artist_name, index)
            try:
                self._database.query(Artist).filter_by(slug=artist_slug).one()
            except NoResultFound:
                break
            index += 1

        return artist_slug

    @staticmethod
    def slugify(string, index = 0):
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

    def get_listened_track_by_artist_name_and_album_name(self, user_id, artist_name, album_name):
        try:
            return (get_database().query(ListenedTrack)
                    .filter(ListenedTrack.user_id == user_id, ListenedTrack.artist_name == artist_name,
                            ListenedTrack.album_name == album_name)
                    .order_by(ListenedTrack.timestamp.desc()).limit(1).one())
        except NoResultFound:
            return None

    def get_listened_track_max_timestamp(self, user_id):
        return (get_database().query(func.max(ListenedTrack.timestamp))
                .filter(ListenedTrack.user_id == user_id).scalar())

    def add_listened_track(self, user_id, name, artist_name, album_name, timestamp):
        listened_track = ListenedTrack(user_id, name, artist_name, album_name, timestamp)

        get_database().add(listened_track)
        get_database().commit()

    def delete_track(self, track, database = None):
        if database is None:
            database = get_database()

        album = track.album
        artist = track.artist

        database.delete(track)
        database.commit()

        database.expire(album)
        database.expire(artist)

        search.delete_track(track)

        if album is not None and len(album.tracks) == 0:
            self.delete_album(album, database)

        if artist is not None and len(artist.albums) == 0:
            self.delete_artist(artist, database)

    def delete_album(self, album, database = None):
        if database is None:
            database = get_database()

        database.delete(album)
        database.commit()

        search.delete_album(album)

    def delete_artist(self, artist, database = None):
        if database is None:
            database = get_database()

        database.delete(artist)
        database.commit()

        search.delete_artist(artist)

    def get_track_ids_by_album_id(self, album_id):
        results = get_database().execute(select([Track.id]).where(Track.album_id == album_id))

        return [result[0] for result in results]

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

    def get_track_by_path(self, path):
        try:
            return (get_database().query(Track)
                    .join(TrackPath, Track.id == TrackPath.track_id)
                    .filter(TrackPath.path == path, Track.scanned)
                    .group_by(Track.id).one())

        except NoResultFound:
            return

    def update_tracks_tags(self, tracks, move = False):
        filenames = []
        messages = []

        for track in tracks:
            id = track['id']
            artist_name = track['artist']
            album_name = track['album']
            track_name = track['track']
            date = track['date']
            number = track['number']
            disc = track['disc']

            try:
                track = get_database().query(Track).filter_by(id=id).one()
            except NoResultFound:
                continue

            for path in track.paths:
                try:
                    tag = reader.get_mutagen_tag(path.path)
                except Exception as e:
                    messages.append("Failed to get tag for %s (%s)." % (path.path.decode('utf8', 'replace'), e))
                    break

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
        return (get_database().query(func.sum(Track.duration))
                .filter(Track.scanned).scalar())

    def get_track_size(self):
        return (get_database().query(func.sum(Track.size))
                .filter(Track.scanned).scalar())

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

    def add_files(self, filenames, move = False, remove_dirs = True,
                  artist_name_override = None, artist_name_fallback = None):
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

                dirname = structure_parser.get_path(absolute = True)
                old_dirname = os.path.dirname(filename)

                if dirname is None:
                    messages.append(
                        'Couldn\'t find appropriate path for %s.' % os.path.basename(filename).decode('utf8', 'replace')
                    )
                    continue

                if os.path.exists(dirname):
                    if not os.path.isdir(dirname):
                        dirname = dirname[len(library_path) - 1:]
                        messages.append(
                            'The path "%s" exists and is not a directory.' % dirname.decode('utf8', 'replace')
                        )
                        continue
                else:
                    try:
                        os.makedirs(dirname)
                    except OSError as e:
                        if e.errno == 17:  # "File exists"
                            # if another thread in a paralell upload scenario already
                            # created it, we just ignore this error
                            pass
                        else:
                            raise e

                path = os.path.join(dirname, os.path.basename(filename))

                if path != filename:
                    if os.path.exists(path):
                        path = path[len(library_path) - 1:]
                        messages.append('The file "%s" already exists.' % path.decode('utf8', 'replace'))
                        continue

                    cherrypy.engine.library_watchdog.add_ignores([filename, path])

                    shutil.move(filename, path)

                    old_dirs.add(old_dirname)
                    moved_dirs.add((old_dirname, dirname))

                    paths.append(path)
                else:
                    paths.append(filename)
            else:
                paths.append(filename)

        tracks = []

        LibraryProcess(self.get_library_path(), paths, get_database(), 0, tracks)

        # move non-track files with folder if there's no tracks left in folder
        # i.e. album covers and such
        for from_dir, to_dir in moved_dirs:
            tracks_left = get_database().query(TrackPath).filter(TrackPath.dir == from_dir).count()

            if tracks_left == 0:
                for from_file in os.listdir(from_dir):
                    from_path = os.path.join(from_dir, from_file)
                    to_path = os.path.join(to_dir, from_file)

                    if from_path == to_dir:
                        continue

                    if os.path.exists(to_path):
                        messages.append('The file "%s" already exists.' % to_path.decode('utf8', 'replace'))
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

            if len(os.listdir(dir)) == 0:
                os.rmdir(dir)
                new_dirs.add(os.path.dirname(dir))

        if len(new_dirs) > 0:
            self.remove_empty_dirs(new_dirs)

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

    def remove_paths(self, paths, remove = True):
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

        if not self.ignore(event.dest_path) and Library.is_supported(event.dest_path):
            self.added.add(event.dest_path)

    def on_created(self, event):
        FileSystemEventHandler.on_created(self, event)

        if event.is_directory or self.ignore(event.src_path) or not Library.is_supported(event.src_path):
            return

        self.added.add(event.src_path)

    def on_deleted(self, event):
        FileSystemEventHandler.on_deleted(self, event)

        if event.is_directory or self.ignore(event.src_path) or not Library.is_supported(event.src_path):
            return

        self.removed.add(event.src_path)

    def on_modified(self, event):
        FileSystemEventHandler.on_modified(self, event)

        if event.is_directory or self.ignore(event.src_path) or not Library.is_supported(event.src_path):
            return

        self.added.add(event.src_path)

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
                database_data.database = get_session()

                removed = self.event_handler.pop_removed()

                if len(removed) > 0:
                    log("Watchdog removing %d files." % len(removed))
                    library_dao.remove_paths(removed, remove = False)

                added = self.event_handler.pop_added()

                if len(added) > 0:
                    log("Watchdog adding %d files." % len(added))
                    tracks, add_files_messages = library_dao.add_files(added, move = False, remove_dirs = False)

                try:
                    database_data.database.commit()
                except:
                    database_data.database.rollback()
                    raise
                finally:
                    database_data.database.remove()
                    database_data.database = None

                time.sleep(5)
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

        def run(self, library_path):
            self.library = Library(library_path)
            self.library.start()

        self.thread = Thread(
            name="Library",
            target=run,
            args=(self, os.path.abspath(config['library.path']))
        )

        self.thread.start()

    start.priority = 110

    def bind_library(self):
        return self.library

    def stop(self):
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
