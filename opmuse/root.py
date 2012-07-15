import os, cherrypy
from opmuse.transcoder import Transcoder

class Playlist:
    @cherrypy.expose
    @cherrypy.tools.jinja(filename='playlist.html')
    def list(self):
        playlist = cherrypy.session.get('playlist', [])

        for track in playlist:
            cherrypy.request.database.add(track)

        return {'playlist': playlist}

    @cherrypy.expose
    def add(self, slug):
        library = cherrypy.engine.library.library
        track = library.get_track_by_slug(slug)

        cherrypy.session.acquire_lock()
        playlist = cherrypy.session.get('playlist', [])
        playlist.append(track)

        cherrypy.session['playlist'] = playlist
        cherrypy.session.release_lock()

    @cherrypy.expose
    def clear(self):
        cherrypy.session.acquire_lock()
        cherrypy.session['playlist'] = []
        cherrypy.session.release_lock()


class Styles(object):
    @cherrypy.expose
    def default(self, file):
        cherrypy.response.headers['Content-Type'] = 'text/css'

        path = os.path.join(os.path.abspath("."), "public", "styles")

        csspath = os.path.join(path, file)

        if os.path.exists(csspath):
            return cherrypy.lib.static.serve_file(csspath)

        ext = os.path.splitext(file)
        lesspath = os.path.join(path, "%s%s" % (ext[0], ".less"))

        if os.path.exists(lesspath):
            from lesscpy.lessc import parser
            p = parser.LessParser()
            p.parse(
                filename=lesspath,
                debuglevel=0
            )

            items = {
                'nl': '\n',
                'tab': '\t',
                'ws': ' ',
                'eb': '\n'
            }

            return ''.join([u.fmt(items) for u in p.result if u]).strip()

class Root(object):
    styles = Styles()
    playlist = Playlist()

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='index.html')
    def index(self):
        return { }

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='album.html')
    def album(self, slug):
        library = cherrypy.engine.library.library
        return {'album': library.get_album_by_slug(slug)}

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='artist.html')
    def artist(self, slug):
        library = cherrypy.engine.library.library
        return {'artist': library.get_artist_by_slug(slug)}

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='library.html')
    def library(self):
        library = cherrypy.engine.library.library
        return {'artists': library.get_artists()}

    @cherrypy.expose
    @cherrypy.config(**{'response.stream': True})
    # TODO reimplement Accept header support
    def stream(self, **kwargs):

        playlist = cherrypy.session.get('playlist', [])

        if len(playlist) == 0:
            raise cherrypy.HTTPError(409)

        cherrypy.response.headers['Content-Type'] = 'audio/ogg'

        for track in playlist:
            cherrypy.request.database.add(track)

        return Transcoder().transcode([track.paths[0].path for track in playlist])


