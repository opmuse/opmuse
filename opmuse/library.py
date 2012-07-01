import cherrypy, re, os, hsaudiotag.auto

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
        title = tag.title

        if len(artist) == 0:
            artist = None

        if len(album) == 0:
            album = None

        if len(title) == 0:
            title = None

        return artist, album, title

class PathParser(TagParser):
    """
    Tries to find tags for file by looking at path components (e.g. containing folder
    might be album name, parent folder might be artist name ...)

    This also uses previously parsed tag as a sort of validator if the artist and album
    names are sane.
    """
    def parse(self, filename):
        artist = None
        album = None
        title = None

        artist_comp, album_comp, title_comp = self._get_path_components(filename)

        if artist_comp in self._reader._by_artists:
            artist = artist_comp

        if artist_comp in self._reader._by_artists and album_comp in self._reader._by_artists[artist_comp]:
            album = album_comp

        if artist_comp in self._reader._by_artists and album_comp in self._reader._by_artists[artist_comp]:
            title = title_comp

        return artist, album, title

    def _get_path_components(self, filename):
        title = os.path.splitext(os.path.basename(filename))[0]
        title = title.split("-")[-1]
        path_comp = os.path.split(os.path.dirname(filename))
        album = path_comp[1]
        path_comp = os.path.split(path_comp[0])
        artist = path_comp[1]

        return artist, album, title

class TagReader:

    _parsed = False

    _parsers = []
    _by_artists = {}
    _by_filename = {}
    _files = []

    def __init__(self):
        self._parsers.append(AutoTagParser(self))
        self._parsers.append(PathParser(self))

    def add(self, filename):
        self._files.append(filename)

    def parse(self):
        for parser in self._parsers:
            if not isinstance(parser, TagParser):
                raise Exception("Parser does not implement TagParser")

            for filename in self._files:
                artist = album = title = None

                if filename in self._by_filename:
                    artist, album, title = self._by_filename[filename]

                if artist is not None and album is not None and title is not None:
                    continue

                new_artist, new_album, new_title = parser.parse(filename)

                if artist is None:
                    artist = new_artist

                if album is None:
                    album = new_album

                if title is None:
                    title = new_title

                if artist is not None and len(artist) > 0:
                    if artist not in self._by_artists:
                        self._by_artists[artist] = {}

                    if album is not None and len(album) > 0:
                        if album not in self._by_artists[artist]:
                            self._by_artists[artist][album] = []

                        if title is not None and len(title) > 0:
                            self._by_artists[artist][album].append((filename, title))

                self._by_filename[filename] = (artist, album, title)

        self._parsed = True

    def get(self, filename):
        if not self._parsed:
            raise Exception("Logic error, parse() must be run before get()")

        artist = None
        album = None
        title = None

        if filename in self._by_filename:
            artist, album, title = self._by_filename[filename]

        return artist, album, title

class Library:

    _tracks = []
    _slugs = {}
    _tracks_by_filename = {}

    _reader = TagReader()

    SUPPORTED = [".mp3", ".ogg"]

    def __init__(self, path):
        files = []

        path = os.path.abspath(path)

        for path, dirnames, filenames in os.walk(path):
            for filename in filenames:
                if os.path.splitext(filename)[1].lower() in self.SUPPORTED:
                    filename = os.path.join(path, filename)
                    files.append(filename)

        [self._reader.add(filename) for filename in files]

        self._reader.parse()

        for filename in files:
            slug = self._parse_slug(filename)
            track = Track(*((slug, filename) + self._reader.get(filename)))
            self._tracks_by_filename[filename] = track
            self._tracks.append(track)

    def _parse_slug(self, filename):
        artist, album, title = self._reader.get(filename)

        if artist is not None and album is not None and title is not None:
            slug = "%s_%s_%s" % (artist, album, title)
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
        if slug in self._slugs:
            filename = self._slugs[slug]
            if filename in self._tracks_by_filename:
                return self._tracks_by_filename[filename]

    def get_tracks(self):
        return self._tracks

class Track:

    def __init__(self, slug, filename, artist, album, title):
        self.slug = slug
        self.filename = filename
        self.artist = artist
        self.album = album
        self.title = title

        ext = os.path.splitext(filename)[1].lower()

        if ext == ".mp3":
            self.format = 'audio/mp3'
        elif ext == ".ogg":
            self.format = 'audio/ogg'
        else:
            self.format = 'audio/unknown'

    def incomplete(self):
        return (
            self.artist is None or len(self.artist) == 0 or
            self.album is None or len(self.album) == 0 or
            self.title is None or len(self.title) == 0)

class LibraryPlugin(cherrypy.process.plugins.SimplePlugin):

    def start(self):
        self.library = Library(cherrypy.config['opmuse']['library.path'])


