import cherrypy, re, os, hsaudiotag.auto, hashlib
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import IntegrityError
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import sessionmaker
from opmuse.database import Base

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

    artist = relationship("Artist", backref=backref('albums', order_by=id))

    def __init__(self, name, slug):
        self.name = name
        self.slug = slug

class TrackPath(Base):
    __tablename__ = 'track_paths'

    id = Column(Integer, primary_key=True)
    path = Column(String(512))
    track_id = Column(Integer, ForeignKey('tracks.id'))

    tracks = relationship("Track", backref=backref('paths', order_by=id))

    def __init__(self, path):
        self.path = path

class Track(Base):
    __tablename__ = 'tracks'

    id = Column(Integer, primary_key=True)
    slug = Column(String(255), index=True)
    name = Column(String(255))
    format = Column(String(128))
    album_id = Column(Integer, ForeignKey('albums.id'))
    hash = Column(String(40), index=True, unique=True)

    album = relationship("Album", backref=backref('tracks', order_by=id))

    def __init__(self, hash, slug, name, format):
        self.hash = hash
        self.slug = slug
        self.name = name
        self.format = format

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
            return None, None, None

        artist = tag.artist
        album = tag.album
        track = tag.title

        if len(artist) == 0:
            artist = None

        if len(album) == 0:
            album = None

        if len(track) == 0:
            track = None

        tag = None
        return artist, album, track

    def get_tag(self, filename):
        raise NotImplementedError()

class OggParser(HsaudiotagParser):

    def get_tag(self, filename):
        return hsaudiotag.ogg.Vorbis(filename)

    def supported_extensions(self):
        return ['ogg']

class Id3Parser(HsaudiotagParser):

    def get_tag(self, filename):
        return hsaudiotag.mpeg.Mpeg(filename).tag

    def supported_extensions(self):
        return ['mp3']

class PathParser(TagParser):
    """
    Tries to find tags for file by looking at path components (e.g. containing folder
    might be album name, parent folder might be artist name ...)
    """

    def parse(self, filename):
        return self._get_path_components(filename)

    def supported_extensions(self):
        return None

    def _get_path_components(self, filename):
        track = os.path.splitext(os.path.basename(filename))[0]
        track = track.split("-")[-1]
        path_comp = os.path.split(os.path.dirname(filename))
        album = path_comp[1]
        path_comp = os.path.split(path_comp[0])
        artist = path_comp[1]

        return artist, album, track

class TagReader:

    _parsed = False

    _parsers = []
    _by_artists = {}
    _by_filename = {}
    files = set()

    def __init__(self):
        self._parsers.extend([
            Id3Parser(self),
            OggParser(self),
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

                artist = album = track = None

                if filename in self._by_filename:
                    artist, album, track = self._by_filename[filename]

                if artist is not None and album is not None and track is not None:
                    continue

                new_artist, new_album, new_track = parser.parse(filename)

                if artist is None:
                    artist = new_artist

                if album is None:
                    album = new_album

                if track is None:
                    track = new_track

                if artist is not None and len(artist) > 0:
                    if artist not in self._by_artists:
                        self._by_artists[artist] = {}

                    if album is not None and len(album) > 0:
                        if album not in self._by_artists[artist]:
                            self._by_artists[artist][album] = []

                        if track is not None and len(track) > 0:
                            self._by_artists[artist][album].append((filename, track))

                self._by_filename[filename] = (artist, album, track)

        self._parsed = True

    def get(self, filename):
        if not self._parsed:
            raise Exception("Logic error, parse() must be run before get()")

        artist = None
        album = None
        track = None

        if filename in self._by_filename:
            artist, album, track = self._by_filename[filename]

        return artist, album, track

class Library:

    _reader = TagReader()

    SUPPORTED = ["mp3", "ogg"]

    def __init__(self, path, database):

        self._database = database

        path = os.path.abspath(path)

        cherrypy.log("Searching library path.")

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
                index += 1
                if index % 1000 == 0:
                    cherrypy.log("%d files found" % index)

                if os.path.splitext(filename)[1].lower()[1:] in self.SUPPORTED:
                    filename = os.path.join(path, filename)

                    # we just ignore files with non-utf8 chars
                    if filename != filename.encode('utf8', 'replace').decode():
                        continue

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
                    # file doesn't exist
                    except NoResultFound:
                        self._reader.add(filename)

        self._database.commit()

        cherrypy.log("Starting tag parsing.")

        self._reader.parse()

        for filename in self._reader.files:
            artist_name, album_name, track_name = self._reader.get(filename)

            if artist_name is None or album_name is None or track_name is None:
                continue

            artist_slug = self._produce_artist_slug(artist_name)
            album_slug = self._produce_album_slug(artist_name, album_name)
            track_slug = self._produce_track_slug(artist_name, album_name, track_name)

            artist = None
            album = None

            try:
                artist = self._database.query(Artist).filter_by(name=artist_name).one()
            except NoResultFound:
                artist = Artist(artist_name, artist_slug)
                self._database.add(artist)

            try:
                album = self._database.query(Album).filter_by(name=album_name).one()
            except NoResultFound:
                album = Album(album_name, album_slug)
                self._database.add(album)

            artist.albums.append(album)

            hash = hash_by_filename[filename]

            ext = os.path.splitext(filename)[1].lower()

            if ext == ".mp3":
                format = 'audio/mp3'
            elif ext == ".ogg":
                format = 'audio/ogg'
            else:
                format = 'audio/unknown'

            track = Track(hash, track_slug, track_name, format)
            self._database.add(track)

            for filename in filename_by_hash[hash]:
                track.paths.append(TrackPath(filename))

            album.tracks.append(track)

            try:
                self._database.commit()
            except IntegrityError:
                print(track)


        # remove tracks without any paths (e.g. removed since previous search)
        #
        # because if the file moved it will be found by the hash and just have
        # the new path readded as opposed to when it was completely removed
        # from the library path
        for track in self._database.query(Track).all():
            if len(track.paths) == 0:
                self._database.delete(track)

        self._database.commit()

    def _produce_artist_slug(self, artist):
        index = 0
        slug = self.slugify(artist)
        while True:
            try:
                self._database.query(Artist).filter_by(slug=slug).one()
            except NoResultFound:
                return slug
            index += 1
            slug = "%s_%s" % (slug, index)

    def _produce_album_slug(self, artist, album):
        index = 0
        slug = self.slugify("%s_%s" % (artist, album))
        while True:
            try:
                self._database.query(Album).filter_by(slug=slug).one()
            except NoResultFound:
                return slug
            index += 1
            slug = "%s_%s" % (slug, index)

    def _produce_track_slug(self, artist, album, track):
        index = 0
        slug = self.slugify("%s_%s_%s" % (artist, album, track))
        while True:
            try:
                self._database.query(Track).filter_by(slug=slug).one()
            except NoResultFound:
                return slug
            index += 1
            slug = "%s_%s" % (slug, index)

    def slugify(self, string):
        return re.sub(r'[\'" :()/]', '_', string.lower())

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

    def get_tracks(self):
        return self._tracks

    def get_artists(self):
        return cherrypy.request.database.query(Artist).all()

    def get_hash(self, filename):
        with open(filename, "rb") as f:
            m = hashlib.sha1()
            b = f.read(128)
            while b:
                m.update(b)
                b = f.read(128)
        return m.hexdigest()

class LibraryPlugin(cherrypy.process.plugins.SimplePlugin):

    def start(self):
        session = sessionmaker(autoflush=True, autocommit=False)
        cherrypy.engine.publish('bind', session)
        self.library = Library(cherrypy.config['opmuse']['library.path'], session())

    # TODO use decorator?
    start.priority = 20

