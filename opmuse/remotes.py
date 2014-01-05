# Copyright 2012-2013 Mattias Fliesberg
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
from opmuse.cache import cache
from opmuse.wikipedia import wikipedia
from opmuse.lastfm import lastfm
from opmuse.google import google
from opmuse.ws import ws
from opmuse.discogs import discogs
from opmuse.database import get_database
from opmuse.library import Artist


class Remotes:
    ARTIST_KEY_FORMAT = "remotes_artist_%d"
    ALBUM_KEY_FORMAT = "remotes_album_%d"
    TRACK_KEY_FORMAT = "remotes_track_%d"
    USER_KEY_FORMAT = "remotes_user_%d"
    TAG_KEY_FORMAT = "remotes_tag_%s"

    ARTIST_AGE = 3600 * 24 * 7
    TAG_AGE = 3600 * 24 * 7
    ALBUM_AGE = 3600 * 24 * 7
    TRACK_AGE = 3600 * 24 * 7
    USER_AGE = 3600

    def update_user(self, user):
        key = Remotes.USER_KEY_FORMAT % user.id

        if cache.needs_update(key, age = Remotes.USER_AGE):
            cache.keep(key)
            cherrypy.engine.bgtask.put(self._fetch_user, 10, user.id, user.lastfm_user,
                                       user.lastfm_session_key)

    def _fetch_user(self, id, lastfm_user, lastfm_session_key):
        key = Remotes.USER_KEY_FORMAT % id

        if lastfm_user is None or lastfm_session_key is None:
            return

        user_lastfm = lastfm.get_user(lastfm_user, lastfm_session_key)

        if user_lastfm is None:
            return

        cache.set(key, {
            'lastfm': user_lastfm
        })

        ws.emit_all('remotes.user.fetched', id)

    _fetch_user.bgtask_name = "Fetch lastfm info for user {1}"

    def get_user(self, user):
        key = Remotes.USER_KEY_FORMAT % user.id

        return cache.get(key)

    def update_track(self, track):
        key = Remotes.TRACK_KEY_FORMAT % track.id

        if cache.needs_update(key, age = Remotes.TRACK_AGE):
            cache.keep(key)
            album_name = track.album.name if track.album is not None else None
            artist_name = track.artist.name if track.artist is not None else None
            cherrypy.engine.bgtask.put(self._fetch_track, 10, track.id, track.name, album_name, artist_name)

    def _fetch_track(self, id, name, album_name, artist_name):
        key = Remotes.TRACK_KEY_FORMAT % id

        track = {
            'wikipedia': wikipedia.get_track(artist_name, album_name, name)
        }

        cache.set(key, track)

        ws.emit_all('remotes.track.fetched', id)

    _fetch_track.bgtask_name = "Fetch info for track {1} by {3} on {2}"

    def get_track(self, track):
        key = Remotes.TRACK_KEY_FORMAT % track.id

        return cache.get(key)

    def update_album(self, album):
        key = Remotes.ALBUM_KEY_FORMAT % album.id

        if cache.needs_update(key, age = Remotes.ALBUM_AGE):
            cache.keep(key)

            # TODO just take first artist when querying for album...
            if len(album.artists) > 0:
                artist_name = album.artists[0].name
            else:
                artist_name = None

            cherrypy.engine.bgtask.put(self._fetch_album, 11, album.id, album.name,
                                       artist_name)

    def _fetch_album(self, id, name, artist_name):
        key = Remotes.ALBUM_KEY_FORMAT % id

        album = {
            'wikipedia': wikipedia.get_album(artist_name, name),
            'lastfm': lastfm.get_album(artist_name, name)
        }

        cache.set(key, album)

        ws.emit_all('remotes.album.fetched', id)

    _fetch_album.bgtask_name = "Fetch info for album {1} by {2}"

    def get_album(self, album):
        key = Remotes.ALBUM_KEY_FORMAT % album.id

        return cache.get(key)

    def update_artist(self, artist):
        key = Remotes.ARTIST_KEY_FORMAT % artist.id

        if cache.needs_update(key, age = Remotes.ARTIST_AGE):
            cache.keep(key)
            cherrypy.engine.bgtask.put(self._fetch_artist, 12, artist.id, artist.name)

    def _fetch_artist(self, id, name):
        key = Remotes.ARTIST_KEY_FORMAT % id

        artist_entity = get_database().query(Artist).filter(Artist.id == id).one()

        artist = {
            'wikipedia': wikipedia.get_artist(name),
            'lastfm': lastfm.get_artist(name),
            'google': google.get_artist_search(artist_entity),
            'discogs': discogs.get_artist(name)
        }

        cache.set(key, artist)

        ws.emit_all('remotes.artist.fetched', id)

    _fetch_artist.bgtask_name = "Fetch info for artist {1}"

    def get_artist(self, artist):
        key = Remotes.ARTIST_KEY_FORMAT % artist.id

        return cache.get(key)

    def update_tag(self, tag_name):
        key = Remotes.TAG_KEY_FORMAT % tag_name

        if cache.needs_update(key, age = Remotes.TAG_AGE):
            cache.keep(key)
            cherrypy.engine.bgtask.put(self._fetch_tag, 5, tag_name)

    def _fetch_tag(self, tag_name):
        key = Remotes.TAG_KEY_FORMAT % tag_name

        tag = {
            'lastfm': lastfm.get_tag(tag_name, 1000),
        }

        cache.set(key, tag)

        ws.emit_all('remotes.tag.fetched', tag_name)

    _fetch_tag.bgtask_name = "Fetch info for tag {0}"

    def get_tag(self, tag_name):
        key = Remotes.TAG_KEY_FORMAT % tag_name

        return cache.get(key)


remotes = Remotes()
