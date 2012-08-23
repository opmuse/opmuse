import cherrypy, re, os, hsaudiotag.auto, base64, mmh3, io, datetime, math
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import Column, Integer, String, ForeignKey, BINARY, BLOB, DateTime
from sqlalchemy.orm import relationship, backref
from multiprocessing import Process, cpu_count
from opmuse.database import Base, get_session

class Artist(Base):
    __tablename__ = 'artists'
    __searchable__ = ['name']

    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    slug = Column(String(255), index=True, unique=True)

    albums = relationship("Album", secondary='tracks')

    def __init__(self, name, slug):
        self.name = name
        self.slug = slug

class Album(Base):
    __tablename__ = 'albums'
    __searchable__ = ['name']

    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    slug = Column(String(255), index=True, unique=True)

    artists = relationship("Artist", secondary='tracks')

    def __init__(self, name, slug):
        self.name = name
        self.slug = slug

class TrackPath(Base):
    __tablename__ = 'track_paths'

    id = Column(Integer, primary_key=True)
    path = Column(BLOB)
    track_id = Column(Integer, ForeignKey('tracks.id'))

    tracks = relationship("Track", backref=backref('paths', order_by=id))

    def __init__(self, path):
        self.path = path

class Track(Base):
    __tablename__ = 'tracks'
    __searchable__ = ['name']

    id = Column(Integer, primary_key=True)
    slug = Column(String(255), index=True, unique=True)
    name = Column(String(255))
    duration = Column(Integer)
    number = Column(Integer)
    format = Column(String(128))
    album_id = Column(Integer, ForeignKey('albums.id'))
    artist_id = Column(Integer, ForeignKey('artists.id'))
    hash = Column(BINARY(24), index=True, unique=True)
    added = Column(DateTime, index=True)

    album = relationship("Album", backref=backref('tracks', order_by=number))
    artist = relationship("Artist", backref=backref('tracks', order_by=name))

    def __init__(self, hash):
        self.hash = hash

class FileMetadata:

    def __init__(self, *args):
        self.artist_name = args[0]
        self.album_name = args[1]
        self.track_name = args[2]
        self.track_duration = args[3]
        self.track_number = args[4]
        self.added = args[5]

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

    def has_required(self):
        return (self.artist_name is not None and
                self.album_name is not None and
                self.track_name is not None)

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

class TagParser:
    def __init__(self, reader):
        self._reader = reader

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

class HsaudiotagParser(TagParser):
    def parse(self, filename):
        tag = self.get_tag(filename)

        if tag is None:
            return FileMetadata(None, None, None, None, None, None)

        artist = tag.artist
        album = tag.album
        track = tag.title
        duration = tag.duration if hasattr(tag, 'duration') else None
        number = tag.track if tag.track > 0 else None

        if len(artist) == 0:
            artist = None

        if len(album) == 0:
            album = None

        if len(track) == 0:
            track = None

        tag = None

        return FileMetadata(artist, album, track, duration, number, None)

    def get_tag(self, filename):
        raise NotImplementedError()

class WmaParser(HsaudiotagParser):

    def get_tag(self, filename):
        return hsaudiotag.wma.WMADecoder(open(filename, 'rb'))

    def supported_extensions(self):
        return [b'wma']

class FlacParser(HsaudiotagParser):

    def get_tag(self, filename):
        return hsaudiotag.flac.FLAC(open(filename, 'rb'))

    def supported_extensions(self):
        return [b'flac']

class Mp4Parser(HsaudiotagParser):

    def get_tag(self, filename):
        return hsaudiotag.mp4.File(open(filename, 'rb'))

    def supported_extensions(self):
        return [b'm4p', b'mp4', b'm4a']

class OggParser(HsaudiotagParser):

    def get_tag(self, filename):
        return hsaudiotag.ogg.Vorbis(open(filename, 'rb'))

    def supported_extensions(self):
        return [b'ogg']

class Id3Tag:
    """
    Wrapper for Mpeg object, because hsaudiotag api is inconsistent it seems
    and some stuff is on the Mpeg object and some on the tag object...
    """

    def __init__(self, mpeg):
        self.artist = mpeg.tag.artist
        self.album = mpeg.tag.album
        self.title = mpeg.tag.title
        self.duration = mpeg.duration
        self.track = mpeg.tag.track

class Id3Parser(HsaudiotagParser):

    def get_tag(self, filename):
        mpeg = hsaudiotag.mpeg.Mpeg(open(filename, 'rb'))

        if mpeg.tag is None:
            return None
        else:
            return Id3Tag(mpeg)

    def supported_extensions(self):
        return [b'mp3']

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
                return FileMetadata(None, None, None, None, None, None)

        track_name = os.path.splitext(os.path.basename(filename))[0]
        track = track_name.split("-")[-1]
        path_comp = os.path.split(os.path.dirname(filename))
        album = path_comp[1]
        path_comp = os.path.split(path_comp[0])
        artist = path_comp[1]

        stat = os.stat(bfilename)
        added = datetime.datetime.fromtimestamp(stat.st_mtime)

        number = None

        match = re.search('([0-9]+)', track_name)
        if match is not None:
            number = int(match.group(0))
            # i don't know of any albums with more than 100 tracks, so we're
            # going to assume it's not a track number if the number is greater
            # than that
            if number > 100:
                number = None

        return FileMetadata(artist, album, track, None, number, added)

    def supported_extensions(self):
        return None

class TagReader:

    def __init__(self):

        self._parsers = []
        self._by_filename = {}

        self._parsers.extend([
            Id3Parser(self),
            OggParser(self),
            Mp4Parser(self),
            FlacParser(self),
            WmaParser(self),
            PathParser(self)
        ])

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

class Library:

    # TODO figure out from TagParsers?
    SUPPORTED = [b"mp3", b"ogg", b"flac", b"wma", b"m4p", b"mp4", b"m4a"]

    def __init__(self, path):
        self._database = get_session()

        # always treat paths as bytes to avoid encoding issues we don't
        # care about
        path = path.encode() if isinstance(path, str) else path

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

                    if index % 1000 == 0:
                        cherrypy.log("%d files found" % index)

                    filename = os.path.join(path, filename)

                    queue.append(filename)

        processes = []

        proc_num = math.ceil(cpu_count() / 2)

        cherrypy.log("Going to use %d library subprocess(es)." % proc_num)

        queue_len = len(queue)
        chunk_size = math.ceil(queue_len / proc_num)

        to_process = []

        for index, filename in enumerate(queue):

            to_process.append(filename)

            if index > 0 and index % chunk_size == 0 or index == queue_len - 1:
                cherrypy.log("Spawning library subprocess.")
                p = Process(target=LibraryProcess, args = (to_process, ))
                p.start()

                processes.append(p)

                to_process = []

        for process in processes:
            process.join()

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

        cherrypy.log("Done updating library.")

class LibraryProcess:

    def __init__(self, queue):

        self._database = get_session()
        self._reader = TagReader()

        for filename in queue:
            self.process(filename)

        self._database.remove()

    def process(self, filename):

        hash = self.get_hash(filename)

        try:
            track = self._database.query(Track).filter_by(hash=hash).one()
            # file most likely just moved
            if filename not in [path.path for path in track.paths]:
                track.paths.append(TrackPath(filename))
                self._database.commit()
            return
        # file doesn't exist
        except NoResultFound:
            track = Track(hash)
            self._database.add(track)
            self._database.commit()

        metadata = self._reader.parse(filename)

        if not metadata.has_required():
            return

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
            album = Album(metadata.album_name, album_slug)
            self._database.add(album)
            self._database.commit()

        ext = os.path.splitext(filename)[1].lower()

        if ext == b".mp3":
            format = 'audio/mp3'
        elif ext == b".wma":
            format = 'audio/x-ms-wma'
        elif ext == b".m4a" or ext == b".m4p" or ext == b".mp4":
            format = b'audio/mp4a-latm'
        elif ext == b".flac":
            format = 'audio/flac'
        elif ext == b".ogg":
            format = 'audio/ogg'
        else:
            format = 'audio/unknown'

        added = metadata.added

        track.slug = track_slug
        track.name = metadata.track_name
        track.duration = metadata.track_duration
        track.number = metadata.track_number
        track.format = format
        track.added = added

        track.paths.append(TrackPath(filename))

        album.tracks.append(track)
        artist.tracks.append(track)

        self._database.commit()

    def _produce_artist_slug(self, artist):
        index = 0
        while True:
            slug = self.slugify(artist, index)
            try:
                self._database.query(Artist).filter_by(slug=slug).one()
            except NoResultFound:
                return slug
            index += 1

    def _produce_album_slug(self, album):
        index = 0
        while True:
            slug = self.slugify(album, index)
            try:
                self._database.query(Album).filter_by(slug=slug).one()
            except NoResultFound:
                return slug
            index += 1

    def _produce_track_slug(self, artist, album, track):
        index = 0
        while True:
            slug = self.slugify("%s_%s_%s" % (artist, album, track), index)
            try:
                self._database.query(Track).filter_by(slug=slug).one()
            except NoResultFound:
                return slug
            index += 1

    def slugify(self, string, index):
        if index > 0:
            index = str(index)
            string = "%s_%s" % (string[:(255 - len(index))], index)
        else:
            string = string[:255]
        return re.sub(r'[^A-Za-z0-9_]', '_', string.lower())

    def get_hash(self, filename):

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

library = LibraryDao()

class LibraryPlugin(cherrypy.process.plugins.SimplePlugin):

    def start(self):
        def process():
            config = cherrypy.tree.apps[''].config['opmuse']
            Library(config['library.path'])

        cherrypy.log("Spawning library process.")
        p = Process(target=process)
        p.start()

    start.priority = 110

