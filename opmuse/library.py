import cherrypy, re, os, base64, mmh3, io, datetime, math, shutil, time
from cherrypy.process.plugins import SimplePlugin
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import (Column, Integer, String, ForeignKey, BINARY, BLOB,
                       DateTime, Boolean)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.hybrid import hybrid_property
from multiprocessing import cpu_count
from threading import Thread
from opmuse.database import Base, get_session, get_type
import mutagen.mp3
import mutagen.oggvorbis
import mutagen.m4a
import mutagen.asf
import mutagen.flac
import mutagen.easyid3
import mutagen.apev2
import mutagen.musepack

class Album(Base):
    __tablename__ = 'albums'
    __searchable__ = ['name']

    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    slug = Column(String(255), index=True, unique=True)
    date = Column(String(32))

    artists = relationship("Artist", secondary='tracks')

    def __init__(self, name, date, slug):
        self.name = name
        self.date = date
        self.slug = slug

    @hybrid_property
    def valid(self):
        return len(self.tracks) == sum(track.valid for track in self.tracks)


class Artist(Base):
    __tablename__ = 'artists'
    __searchable__ = ['name']

    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    slug = Column(String(255), index=True, unique=True)

    albums = relationship("Album", secondary='tracks',
        order_by=(Album.date.desc(), Album.name))

    def __init__(self, name, slug):
        self.name = name
        self.slug = slug


class TrackPath(Base):
    __tablename__ = 'track_paths'

    id = Column(Integer, primary_key=True)
    path = Column(BLOB)
    track_id = Column(Integer, ForeignKey('tracks.id'))

    tracks = relationship("Track", backref=backref('paths', cascade="all,delete", order_by=id))

    def __init__(self, path):
        self.path = path

class Track(Base):
    __tablename__ = 'tracks'
    __searchable__ = ['name']

    id = Column(Integer, primary_key=True)
    slug = Column(String(255), index=True, unique=True)
    name = Column(String(255))
    duration = Column(Integer)
    number = Column(String(8))
    format = Column(String(128))
    album_id = Column(Integer, ForeignKey('albums.id'))
    artist_id = Column(Integer, ForeignKey('artists.id'))
    hash = Column(BINARY(24), index=True, unique=True)
    added = Column(DateTime, index=True)
    bitrate = Column(Integer)
    valid = Column(Boolean, index=True)

    album = relationship("Album", lazy='joined', innerjoin=True,
        backref=backref('tracks', order_by=(number, name)))

    artist = relationship("Artist", lazy='joined', innerjoin=True,
        backref=backref('tracks', order_by=name))

    def __init__(self, hash):
        self.hash = hash

    def __str__(self):
        return "%s - %s - %s" % (self.artist.name, self.album.name, self.name)

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
        self.valid = args[8]

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

    def parse(self, filename):
        raise NotImplementedError()

class MutagenParser(TagParser):
    def parse(self, filename):
        try:
            tag = self.get_tag(filename)
        except (IOError, ValueError) as error:
            cherrypy.log("Got '%s' when parsing '%s'" % (error, filename.decode('utf8', 'replace')))
            return FileMetadata(*(None, ) * 9)

        artist = tag['artist'][0] if 'artist' in tag else None
        album = tag['album'][0] if 'album' in tag else None
        track = tag['title'][0] if 'title' in tag else None
        duration = tag.info.length
        number = tag['tracknumber'][0] if 'tracknumber' in tag else None
        date = tag['date'][0] if 'date' in tag else None
        bitrate = tag.info.bitrate if hasattr(tag.info, 'bitrate') else None

        # won't fit in SQL INT, and i'm guessing something's up :|
        if bitrate is not None and bitrate > 2147483647:
            bitrate = None

        if number is not None and len(number) > 8:
            number = None

        valid = artist is not None and album is not None and track is not None

        return FileMetadata(artist, album, track, duration, number, None, date,
                            bitrate, valid)

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
        return mutagen.m4a.M4A(filename)

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

    def parse(self, filename):
        bfilename = filename
        try:
            filename = filename.decode('utf8')
        except UnicodeDecodeError:
            try:
                filename = filename.decode('latin1')
            except UnicodeDecodeError:
                return FileMetadata(*(None, ) * 9)

        track_name = os.path.splitext(os.path.basename(filename))[0]
        track_name = track_name.replace("_", " ")
        path_comp = os.path.split(os.path.dirname(filename))
        album = path_comp[1]
        path_comp = os.path.split(path_comp[0])
        artist = path_comp[1]

        stat = os.stat(bfilename)
        added = datetime.datetime.fromtimestamp(stat.st_mtime)

        number = None

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

        return FileMetadata(artist, album, track_name, None, number, added,
                            None, None, False)

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

    def parse(self, filename):
        metadata = None

        for parser in self._parsers:

            parser_name = parser.__class__.__name__

            if not parser.is_supported(filename):
                continue

            new_metadata = parser.parse(filename)

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


reader = TagReader()

class Library:

    # TODO figure out from TagParsers?
    SUPPORTED = [b"mp3", b"ogg", b"flac", b"wma", b"m4p", b"mp4", b"m4a",
                 b"ape", b"mpc", b"wav", b"mp2"]

    def __init__(self, path):
        self.scanning = False
        self._path = path

    def start(self):

        self.scanning = True

        self._database_type = get_type()
        self._database = get_session()

        # always treat paths as bytes to avoid encoding issues we don't
        # care about
        path = self._path.encode() if isinstance(self._path, str) else self._path

        path = os.path.abspath(path)

        cherrypy.log("Starting library update.")

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
                if os.path.splitext(filename)[1].lower()[1:] in self.SUPPORTED:

                    index += 1

                    filename = os.path.join(path, filename)

                    queue.append(filename)

        cherrypy.log("%d files found" % index)

        threads = []

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
                p = Thread(target=LibraryProcess, args = (to_process, None, no))
                p.start()

                threads.append(p)

                to_process = []
                no += 1

        cherrypy.log("Spawned %d library thread(s)." % thread_num)

        for thread in threads:
            thread.join()

        # remove tracks without any paths (e.g. removed since previous search)
        #
        # because if the file moved it will be found by the hash and just have
        # the new path readded as opposed to when it was completely removed
        # from the library path
        for track in self._database.query(Track).all():
            if len(track.paths) == 0:
                self._database.delete(track)
                self._database.commit()

        # remove albums without tracks
        for album in self._database.query(Album).all():
            if len(album.tracks) == 0:
                self._database.delete(album)
                self._database.commit()

        # remove artists without albums
        for artist in self._database.query(Artist).all():
            if len(artist.albums) == 0:
                self._database.delete(artist)
                self._database.commit()

        self._database.remove()

        self.scanning = False

        cherrypy.log("Done updating library.")

class LibraryProcess:

    def __init__(self, queue, database = None, no = -1, tracks = None):

        self.no = no

        if database is None:
            self._database = get_session()
        else:
            self._database = database

        count = 1
        start = time.time()
        for filename in queue:
            track = self.process(filename)

            if tracks is not None:
                tracks.append(track)

            if count == 1000:
                cherrypy.log('Process %d processed %d files in %d seconds.' %
                    (self.no, count, time.time() - start))
                start = time.time()
                count = 0

            count += 1

        if database is None:
            self._database.remove()

        cherrypy.log('Process %d is done.' % (self.no, ))

    def process(self, filename):

        hash = LibraryProcess.get_hash(filename)

        try:
            track = self._database.query(Track).filter_by(hash=hash).one()
            # file most likely just moved
            if filename not in [path.path for path in track.paths]:
                track.paths.append(TrackPath(filename))
                self._database.commit()
            return track
        # file doesn't exist
        except NoResultFound:
            track = Track(hash)
            self._database.add(track)
            self._database.commit()

        metadata = reader.parse(filename)

        artist_slug = self._produce_artist_slug(
            metadata.artist_name
        )
        album_slug = self._produce_album_slug(
            metadata.album_name
        )
        track_slug = self._produce_track_slug(
            metadata.artist_name, metadata.album_name, metadata.track_name
        )

        artist = None
        album = None

        try:
            artist = self._database.query(Artist).filter_by(
                name=metadata.artist_name
            ).one()
        except NoResultFound:
            artist = Artist(metadata.artist_name, artist_slug)
            self._database.add(artist)
            self._database.commit()

        try:
            album = self._database.query(Album).filter_by(
                name=metadata.album_name
            ).one()
        except NoResultFound:
            album = Album(metadata.album_name, metadata.date, album_slug)
            self._database.add(album)
            self._database.commit()

        # if the first track on the album didn't have date data maybe another
        # one does...
        if album.date is None:
            album.date = metadata.date

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

        track.slug = track_slug
        track.name = metadata.track_name
        track.duration = metadata.track_duration
        track.number = LibraryProcess.fix_track_number(metadata.track_number)
        track.format = format
        track.added = added
        track.bitrate = metadata.bitrate
        track.valid = False if metadata.valid is None else metadata.valid

        track.paths.append(TrackPath(filename))

        album.tracks.append(track)
        artist.tracks.append(track)

        self._database.commit()

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

    def _produce_artist_slug(self, artist):
        index = 0
        while True:
            slug = LibraryProcess.slugify(artist, index)
            try:
                self._database.query(Artist).filter_by(slug=slug).one()
            except NoResultFound:
                return slug
            index += 1

    def _produce_album_slug(self, album):
        index = 0
        while True:
            slug = LibraryProcess.slugify(album, index)
            try:
                self._database.query(Album).filter_by(slug=slug).one()
            except NoResultFound:
                return slug
            index += 1

    def _produce_track_slug(self, artist, album, track):
        index = 0
        while True:
            slug = LibraryProcess.slugify("%s_%s_%s" % (artist, album, track), index)
            try:
                self._database.query(Track).filter_by(slug=slug).one()
            except NoResultFound:
                return slug
            index += 1

    @staticmethod
    def slugify(string, index):
        if index > 0:
            index = str(index)
            string = "%s_%s" % (string[:(255 - len(index))], index)
        else:
            string = string[:255]
        return re.sub(r'[^A-Za-z0-9_]', '_', string.lower())

    @staticmethod
    def get_hash(filename):

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

    def get_library_path(self):
        library_path = os.path.abspath(cherrypy.request.app.config['opmuse']['library.path'])

        if library_path[-1] != "/":
            library_path += "/"
        return library_path

    def update_tracks_tags(self, tracks, move = False):
        filenames = []

        for track in tracks:
            id = track['id']
            artist_name = track['artist']
            album_name = track['album']
            track_name = track['track']
            date = track['date']
            number = track['number']

            track = (cherrypy.request.database.query(Track)
                .filter_by(id=id).one())

            for path in track.paths:
                filenames.append(path.path)

                tag = reader.get_mutagen_tag(path.path)
                tag['artist'] = artist_name
                tag['album'] = album_name
                tag['title'] = track_name

                if number is not None and number != '':
                    tag['tracknumber'] = number

                if date is not None and date != '':
                    tag['date'] = date

                tag.save()

            cherrypy.request.database.delete(track)
            cherrypy.request.database.commit()

        return self.add_files(filenames, move)

    def get_invalid_track_count(self):
        return (cherrypy.request.database.query(Track)
            .filter(Track.valid == False).count())

    def get_album_count(self):
        return cherrypy.request.database.query(Album).count()

    def get_artist_count(self):
        return cherrypy.request.database.query(Artist).count()

    def get_track_count(self):
        return cherrypy.request.database.query(Track).count()

    def get_tracks_by_ids(self, ids):
        return (cherrypy.request.database.query(Track)
            .filter(Track.id.in_(ids)).all())

    def add_files(self, filenames, move = False):

        paths = []

        messages = []

        for filename in filenames:
            if os.path.splitext(filename)[1].lower()[1:] not in Library.SUPPORTED:
                continue

            metadata = reader.parse(filename)

            library_path = self.get_library_path()

            dirname = os.path.join(library_path, metadata.artist_name, metadata.album_name)

            dirname = dirname.encode('utf8')

            if os.path.exists(dirname):
                if not os.path.isdir(dirname):
                    dirname = dirname[len(library_path) - 1:]
                    messages.append('The path "%s" exists and is not a directory.' % dirname.decode('utf8', 'replace'))
                    continue
            else:
                os.makedirs(dirname)

            if move:
                path = os.path.join(dirname, os.path.basename(filename))

                if path != filename:
                    if os.path.exists(path):
                        path = path[len(library_path) - 1:]
                        messages.append('The file "%s" already exists.' % path.decode('utf8', 'replace'))
                        continue

                    shutil.move(filename, path)
            else:
                path = filename

            paths.append(path)

        tracks = []

        LibraryProcess(paths, cherrypy.request.database, 0, tracks)

        return tracks, messages

    def get_album_by_slug(self, slug):
        try:
            return cherrypy.request.database.query(Album).filter_by(slug=slug).one()
        except NoResultFound:
            pass

    def get_artist_by_slug(self, slug):
        try:
            return cherrypy.request.database.query(Artist).filter_by(slug=slug).one()
        except NoResultFound:
            pass

    def get_track_by_slug(self, slug):
        try:
            return cherrypy.request.database.query(Track).filter_by(slug=slug).one()
        except NoResultFound:
            pass

    def get_artists(self):
        return cherrypy.request.database.query(Artist).order_by(Artist.name).all()

    def get_new_tracks(self, age):
        return (cherrypy.request.database.query(Track).filter(Track.added > age)
            .order_by(Track.added.desc()).all())

library_dao = LibraryDao()

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
            target=run,
            args=(self, os.path.abspath(config['library.path']))
        )

        self.thread.start()

    start.priority = 110

    def bind_library(self):
        return self.library

    def stop(self):
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

