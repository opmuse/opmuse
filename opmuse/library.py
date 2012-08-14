import cherrypy, re, os, hsaudiotag.auto, base64, mmh3, io
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import Column, Integer, String, ForeignKey, BINARY, BLOB
from sqlalchemy.orm import relationship, backref
from multiprocessing import Process
from opmuse.database import Base, get_session

class Artist(Base):
    __tablename__ = 'artists'

    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    slug = Column(String(255), index=True)

    def __init__(self, name, slug):
        self.name = name
        self.slug = slug

class Album(Base):
    __tablename__ = 'albums'

    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    slug = Column(String(255), index=True)
    artist_id = Column(Integer, ForeignKey('artists.id'))

    artist = relationship("Artist", backref=backref('albums', order_by=name))

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
    slug = Column(String(255), index=True)
    name = Column(String(255))
    duration = Column(Integer)
    number = Column(Integer)
    format = Column(String(128))
    album_id = Column(Integer, ForeignKey('albums.id'))
    hash = Column(BINARY(24), index=True, unique=True)

    album = relationship("Album", backref=backref('tracks', order_by=number))

    def __init__(self, hash, slug, name, duration, number, format):
        self.hash = hash
        self.slug = slug
        self.name = name
        self.duration = duration
        self.number = number
        self.format = format

class FileMetadata:

    def __init__(self, *args):
        self.artist_name = args[0]
        self.album_name = args[1]
        self.track_name = args[2]
        self.track_duration = args[3]
        self.track_number = args[4]

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
            return FileMetadata(None, None, None, None, None)

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

        return FileMetadata(artist, album, track, duration, number)

    def get_tag(self, filename):
        raise NotImplementedError()

class WmaParser(HsaudiotagParser):

    def get_tag(self, filename):
        try:
            # parser doesn't work with byte filenames
            filename = filename.decode()
        except UnicodeDecodeError:
            return None
        return hsaudiotag.wma.WMADecoder(filename)

    def supported_extensions(self):
        return [b'wma']

class FlacParser(HsaudiotagParser):

    def get_tag(self, filename):
        try:
            # parser doesn't work with byte filenames
            filename = filename.decode()
        except UnicodeDecodeError:
            return None
        return hsaudiotag.flac.FLAC(filename)

    def supported_extensions(self):
        return [b'flac']

class Mp4Parser(HsaudiotagParser):

    def get_tag(self, filename):
        try:
            # parser doesn't work with byte filenames
            filename = filename.decode()
        except UnicodeDecodeError:
            return None
        return hsaudiotag.mp4.File(filename)

    def supported_extensions(self):
        return [b'm4p', b'mp4', b'm4a']

class OggParser(HsaudiotagParser):

    def get_tag(self, filename):
        try:
            # parser doesn't work with byte filenames
            filename = filename.decode()
        except UnicodeDecodeError:
            return None
        return hsaudiotag.ogg.Vorbis(filename)

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
        try:
            # parser doesn't work with byte filenames
            filename = filename.decode()
        except UnicodeDecodeError:
            return None

        mpeg = hsaudiotag.mpeg.Mpeg(filename)

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
        try:
            # parser doesn't work with byte filenames
            filename = filename.decode()
        except UnicodeDecodeError:
            return FileMetadata(None, None, None, None, None)

        track_name = os.path.splitext(os.path.basename(filename))[0]
        track = track_name.split("-")[-1]
        path_comp = os.path.split(os.path.dirname(filename))
        album = path_comp[1]
        path_comp = os.path.split(path_comp[0])
        artist = path_comp[1]

        number = None

        match = re.search('([0-9]+)', track_name)
        if match is not None:
            number = int(match.group(0))
            # i don't know of any albums with more than 100 tracks, so we're
            # going to assume it's not a track number if the number is greater
            # than that
            if number > 100:
                number = None

        return FileMetadata(artist, album, track, None, number)

    def supported_extensions(self):
        return None

class TagReader:

    _parsed = False

    _parsers = []
    _by_filename = {}
    files = set()

    def __init__(self):
        self._parsers.extend([
            Id3Parser(self),
            OggParser(self),
            Mp4Parser(self),
            FlacParser(self),
            WmaParser(self),
            PathParser(self)
        ])

    def add(self, filename):
        self.files.add(filename)

    def parse(self):
        for parser in self._parsers:
            if not isinstance(parser, TagParser):
                raise Exception("Parser does not implement TagParser")

            parser_name = parser.__class__.__name__

            cherrypy.log("Parsing with %s" % parser_name)

            index = 0
            total = len(self.files)
            for filename in self.files:
                index += 1

                if index % 1000 == 0:
                    cherrypy.log("%d of %d parsed with %s" % (index, total, parser_name))

                if not parser.is_supported(filename):
                    continue

                previous_metadata = None

                if filename in self._by_filename:
                    previous_metadata = self._by_filename[filename]

                new_metadata = parser.parse(filename)

                if not isinstance(new_metadata, FileMetadata):
                    raise Exception("TagParser.parse must return a FileMetadata instance.")

                if previous_metadata is not None:
                    metadata = previous_metadata.merge(new_metadata)
                else:
                    metadata = new_metadata

                self._by_filename[filename] = metadata

        self._parsed = True

    def get(self, filename):
        if not self._parsed:
            raise Exception("Logic error, parse() must be run before get()")

        if filename in self._by_filename:
            return self._by_filename[filename]

class Library:

    _reader = TagReader()

    # TODO figure out from TagParsers?
    SUPPORTED = [b"mp3", b"ogg", b"flac", b"wma", b"m4p", b"mp4", b"m4a"]

    def __init__(self, path, database):

        self._database = database

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

        filename_by_hash = {}
        hash_by_filename = {}

        index = 0
        for path, dirnames, filenames in os.walk(path):
            for filename in filenames:

                if os.path.splitext(filename)[1].lower()[1:] in self.SUPPORTED:

                    index += 1
                    if index % 1000 == 0:
                        cherrypy.log("%d files found" % index)

                    filename = os.path.join(path, filename)

                    # we just ignore files with non-utf8 chars
                    #if filename != filename.encode('utf8', 'replace').decode():
                    #    continue

                    hash = self.get_hash(filename)

                    hash_by_filename[filename] = hash

                    # don't parse two identical files more than once
                    if hash in filename_by_hash:
                        filename_by_hash[hash].append(filename)
                        continue
                    else:
                        filename_by_hash[hash] = [filename]

                    try:
                        track = self._database.query(Track).filter_by(hash=hash).one()
                        # file most likely just moved
                        if filename not in [path.path for path in track.paths]:
                            track.paths.append(TrackPath(filename))
                            self._database.add(track)
                            self._database.commit()
                    # file doesn't exist
                    except NoResultFound:
                        self._reader.add(filename)


        cherrypy.log("Starting tag parsing.")

        self._reader.parse()

        cherrypy.log("Starting database update.")

        files = index = len(self._reader.files)

        for filename in self._reader.files:

            if index % 1000 == 0:
                cherrypy.log("Updated %d of %d files." % (index, files))

            index -= 1

            metadata = self._reader.get(filename)

            if not metadata.has_required():
                continue

            artist_slug = self._produce_artist_slug(
                metadata.artist_name
            )
            album_slug = self._produce_album_slug(
                metadata.artist_name, metadata.album_name
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
                    artist=artist, name=metadata.album_name
                ).one()
            except NoResultFound:
                album = Album(metadata.album_name, album_slug)
                self._database.add(album)
                self._database.commit()

            artist.albums.append(album)

            hash = hash_by_filename[filename]

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

            track = Track(hash, track_slug, metadata.track_name,
                    metadata.track_duration, metadata.track_number, format)
            self._database.add(track)

            for filename in filename_by_hash[hash]:
                track.paths.append(TrackPath(filename))

            album.tracks.append(track)

            self._database.commit()

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

        cherrypy.log("Done updating library.")

    def _produce_artist_slug(self, artist):
        index = 0
        while True:
            slug = self.slugify(artist, index)
            try:
                self._database.query(Artist).filter_by(slug=slug).one()
            except NoResultFound:
                return slug
            index += 1

    def _produce_album_slug(self, artist, album):
        index = 0
        while True:
            slug = self.slugify("%s_%s" % (artist, album), index)
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
            # fetch first 512k and last 512k to get a reasonably secure
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

class LibraryPlugin(cherrypy.process.plugins.SimplePlugin):

    def start(self):
        def process():
            config = cherrypy.tree.apps[''].config['opmuse']
            Library(config['library.path'], get_session())

        cherrypy.log("Spawning library process.")
        p = Process(target=process)
        p.start()

        self.library = LibraryDao()

    # TODO use decorator?
    start.priority = 20

