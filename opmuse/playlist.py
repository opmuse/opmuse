import cherrypy


# TODO Implement the ORM to make playlists persistable
# TODO Consider putting the locking and releasing of the session in a decorator
class Model:
    def getTracks(self):
        tracks = cherrypy.session.get('playlist', [])

        for track in tracks:
            cherrypy.request.database.add(track)

        return tracks

    def clear(self):
        cherrypy.session.acquire_lock()
        cherrypy.session['playlist'] = []
        cherrypy.session.release_lock()

    def addTrack(self, slug):
        library = cherrypy.engine.library.library
        track = library.get_track_by_slug(slug)

        cherrypy.session.acquire_lock()
        playlist = cherrypy.session.get('playlist', [])
        playlist.append(track)

        cherrypy.session['playlist'] = playlist
        cherrypy.session.release_lock()

    def removeTrack(self, number):
        cherrypy.session.acquire_lock()
        playlist = cherrypy.session.get('playlist', [])
        playlist.pop(int(number))

        cherrypy.session['playlist'] = playlist
        cherrypy.session.release_lock()

    def addAlbum(self, slug):
        library = cherrypy.engine.library.library
        album = library.get_album_by_slug(slug)

        cherrypy.session.acquire_lock()
        playlist = cherrypy.session.get('playlist', [])

        for track in album.tracks:
            playlist.append(track)

        cherrypy.session['playlist'] = playlist
        cherrypy.session.release_lock()
