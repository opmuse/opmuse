import cherrypy, re, os, hsaudiotag.auto
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import sessionmaker
from opmuse.database import Base

class Artist(Base):
    __tablename__ = 'artists'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    def __init__(self, name):
        self.name = name

class Album(Base):
    __tablename__ = 'albums'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    artist_id = Column(Integer, ForeignKey('artists.id'))

    artist = relationship("Artist", backref=backref('albums', order_by=id))

    def __init__(self, name):
        self.name = name

class Track(Base):
    __tablename__ = 'tracks'

    id = Column(Integer, primary_key=True)
    slug = Column(String)
    filename = Column(String)
    name = Column(String)
    format = Column(String)
    album_id = Column(Integer, ForeignKey('albums.id'))

    album = relationship("Album", backref=backref('tracks', order_by=id))

    def __init__(self, slug, filename, name):
        self.slug = slug
        self.filename = filename
        self.name = name

        ext = os.path.splitext(filename)[1].lower()

        if ext == ".mp3":
            self.format = 'audio/mp3'
        elif ext == ".ogg":
            self.format = 'audio/ogg'
        else:
            self.format = 'audio/unknown'

class TagParser:
    def __init__(self, reader):
        self._reader = reader

    def parse(self, filename):
        raise NotImplementedError()

class AutoTagParser(TagParser):
    def parse(self, filename):
        tag = hsaudiotag.auto.File(filename)

        artist = tag.artist
        album = tag.album
        track = tag.title

        if len(artist) == 0:
            artist = None

        if len(album) == 0:
            album = None

        if len(track) == 0:
            track = None

        return artist, album, track

class PathParser(TagParser):
    """
    Tries to find tags for file by looking at path components (e.g. containing folder
    might be album name, parent folder might be artist name ...)

    This also uses previously parsed tag as a sort of validator if the artist and album
    names are sane.
    """
    _validate = True

    def validate(self, validate = True):
        self._validate = validate
        return self

    def parse(self, filename):
        artist = None
        album = None
        track = None

        if self._validate:
            artist_comp, album_comp, track_comp = self._get_path_components(filename)

            if artist_comp in self._reader._by_artists:
                artist = artist_comp

            if artist_comp in self._reader._by_artists and album_comp in self._reader._by_artists[artist_comp]:
                album = album_comp

            if artist_comp in self._reader._by_artists and album_comp in self._reader._by_artists[artist_comp]:
                track = track_comp
        else:
            artist, album, track = self._get_path_components(filename)

        return artist, album, track

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
    _files = []

    def __init__(self):
        self._parsers.append(AutoTagParser(self))
        self._parsers.append(PathParser(self).validate(False))

    def add(self, filename):
        self._files.append(filename)

    def parse(self):
        for parser in self._parsers:
            if not isinstance(parser, TagParser):
                raise Exception("Parser does not implement TagParser")

            for filename in self._files:
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

    _slugs = {}

    _reader = TagReader()

    SUPPORTED = [".mp3", ".ogg"]

    def __init__(self, path, database):
        files = []

        self._database = database

        path = os.path.abspath(path)

        for path, dirnames, filenames in os.walk(path):
            for filename in filenames:
                if os.path.splitext(filename)[1].lower() in self.SUPPORTED:
                    filename = os.path.join(path, filename)
                    files.append(filename)

        for filename in files:
            self._reader.add(filename)

        self._reader.parse()

        for filename in files:
            try:
                self._database.query(Track).filter_by(filename=filename).one()
                continue
            except NoResultFound:
                pass

            artist_name, album_name, track_name = self._reader.get(filename)

            if artist_name is None or album_name is None or track_name is None:
                continue

            slug = self._parse_slug(filename)

            artist = None
            album = None

            try:
                artist = self._database.query(Artist).filter_by(name=artist_name).one()
            except NoResultFound:
                artist = Artist(artist_name)
                self._database.add(artist)

            try:
                album = self._database.query(Album).filter_by(name=album_name).one()
            except NoResultFound:
                album = Album(album_name)
                self._database.add(album)

            artist.albums.append(album)

            track = Track(slug, filename, track_name)
            self._database.add(track)

            album.tracks.append(track)

            self._database.commit()
            #self._session.close()
            #self._session = None

    def _parse_slug(self, filename):
        artist, album, track = self._reader.get(filename)

        if artist is not None and album is not None and track is not None:
            slug = "%s_%s_%s" % (artist, album, track)
        else:
            slug = os.path.splitext(os.path.basename(filename))[0]

        slug = re.sub(r'[\'" ()/]', '_', slug.lower())

        index = 0

        while True:
            if slug not in self._slugs:
                self._slugs[slug] = filename
                return slug
            index += 1
            slug = "%s_%s" % (slug, index)

    def get_track_by_slug(self, slug):
        try:
            return cherrypy.request.database.query(Track).filter_by(slug=slug).one()
        except NoResultFound:
            pass

    def get_tracks(self):
        return self._tracks

    def get_artists(self):
        return cherrypy.request.database.query(Artist).all()

class LibraryPlugin(cherrypy.process.plugins.SimplePlugin):

    def start(self):
        session = sessionmaker(autoflush=True, autocommit=False)
        cherrypy.engine.publish('bind', session)
        self.library = Library(cherrypy.config['opmuse']['library.path'], session())

    # TODO use decorator?
    start.priority = 20

