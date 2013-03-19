import cherrypy
from opmuse.cache import cache
from opmuse.wikipedia import wikipedia
from opmuse.lastfm import lastfm
from opmuse.discogs import discogs


class Remotes:
    ARTIST_KEY_FORMAT = "remotes_artist_%d"
    ALBUM_KEY_FORMAT = "remotes_album_%d"
    TRACK_KEY_FORMAT = "remotes_track_%d"
    USER_KEY_FORMAT = "remotes_user_%d"

    ARTIST_AGE = 3600 * 24 * 7
    ALBUM_AGE = 3600 * 24 * 7
    TRACK_AGE = 3600 * 24 * 7
    USER_AGE = 3600

    def update_user(self, user):
        database = cherrypy.request.database

        key = Remotes.USER_KEY_FORMAT % user.id

        if cache.needs_update(key, age = Remotes.USER_AGE, database = database):
            cache.keep(key, database = database)
            cherrypy.engine.bgtask.put(self._fetch_user, 10, user.id, user.lastfm_user,
                                       user.lastfm_session_key)

    def _fetch_user(self, id, lastfm_user, lastfm_session_key, _database):
        key = Remotes.USER_KEY_FORMAT % id

        user = {}

        if lastfm_user is not None and lastfm_session_key is not None:
            user['lastfm'] = lastfm.get_user(lastfm_user, lastfm_session_key)
        else:
            user['lastfm'] = None

        cache.set(key, user, database = _database)

    def get_user(self, user):
        database = cherrypy.request.database

        key = Remotes.USER_KEY_FORMAT % user.id

        return cache.get(key, database = database)

    def update_track(self, track):
        database = cherrypy.request.database

        key = Remotes.TRACK_KEY_FORMAT % track.id

        if cache.needs_update(key, age = Remotes.TRACK_AGE, database = database):
            cache.keep(key, database = database)
            album_name = track.album.name if track.album is not None else None
            artist_name = track.artist.name if track.artist is not None else None
            cherrypy.engine.bgtask.put(self._fetch_track, 10, track.id, track.name, album_name, artist_name)

    def _fetch_track(self, id, name, album_name, artist_name, _database):
        key = Remotes.TRACK_KEY_FORMAT % id

        track = {
            'wikipedia': wikipedia.get_track(artist_name, album_name, name)
        }

        cache.set(key, track, database = _database)

    def get_track(self, track):
        database = cherrypy.request.database

        key = Remotes.TRACK_KEY_FORMAT % track.id

        return cache.get(key, database = database)

    def update_album(self, album):
        database = cherrypy.request.database

        key = Remotes.ALBUM_KEY_FORMAT % album.id

        if cache.needs_update(key, age = Remotes.ALBUM_AGE, database = database):
            cache.keep(key, database = database)

            # TODO just take first artist when querying for album...
            if len(album.artists) > 0:
                artist_name = album.artists[0].name
            else:
                artist_name = None

            cherrypy.engine.bgtask.put(self._fetch_album, 11, album.id, album.name,
                                       artist_name)

    def _fetch_album(self, id, name, artist_name, _database):
        key = Remotes.ALBUM_KEY_FORMAT % id

        album = {
            'wikipedia': wikipedia.get_album(artist_name, name),
            'lastfm': lastfm.get_album(artist_name, name)
        }

        cache.set(key, album, database = _database)

    def get_album(self, album):
        database = cherrypy.request.database

        key = Remotes.ALBUM_KEY_FORMAT % album.id

        return cache.get(key, database = database)

    def update_artist(self, artist):
        database = cherrypy.request.database

        key = Remotes.ARTIST_KEY_FORMAT % artist.id

        if cache.needs_update(key, age = Remotes.ARTIST_AGE, database = database):
            cache.keep(key, database = database)
            cherrypy.engine.bgtask.put(self._fetch_artist, 12, artist.id, artist.name)

    def _fetch_artist(self, id, name, _database):
        key = Remotes.ARTIST_KEY_FORMAT % id

        artist = {
            'wikipedia': wikipedia.get_artist(name),
            'lastfm': lastfm.get_artist(name, _database),
            'discogs': discogs.get_artist(name)
        }

        cache.set(key, artist, database = _database)

    def get_artist(self, artist):
        database = cherrypy.request.database

        key = Remotes.ARTIST_KEY_FORMAT % artist.id

        return cache.get(key, database = database)


remotes = Remotes()
