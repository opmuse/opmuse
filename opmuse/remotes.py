# Copyright 2012-2014 Mattias Fliesberg
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
from sqlalchemy.orm.exc import NoResultFound
from opmuse.cache import cache
from opmuse.wikipedia import wikipedia
from opmuse.lastfm import lastfm
from opmuse.google import google
from opmuse.ws import ws
from opmuse.musicbrainz import musicbrainz
from opmuse.database import get_database
from opmuse.library import Artist, Album, Track, library_dao


class Remotes:
    ARTIST_KEY_FORMAT = "remotes_artist_%d"
    ALBUM_KEY_FORMAT = "remotes_album_%d"
    TRACK_KEY_FORMAT = "remotes_track_%d"
    USER_KEY_FORMAT = "remotes_user_%d"
    USER_TRACKS_KEY_FORMAT = "remotes_user_tracks_%d"
    TAG_KEY_FORMAT = "remotes_tag_%s"

    ARTIST_AGE = 3600 * 24 * 7
    ALBUM_AGE = 3600 * 24 * 7
    TRACK_AGE = 3600 * 24 * 7
    USER_AGE = 3600 * 2
    USER_TRACKS_AGE = 1800
    TAG_AGE = 3600 * 24 * 7

    def update_user_tracks(self, user):
        key = Remotes.USER_TRACKS_KEY_FORMAT % user.id

        if cache.needs_update(key, age = Remotes.USER_TRACKS_AGE):
            cache.keep(key)
            cherrypy.engine.bgtask.put(self._add_listened_tracks, 10, user.id, user.lastfm_user,
                                       user.lastfm_session_key)

    def _add_listened_tracks(self, user_id, lastfm_user, lastfm_session_key):
        key = Remotes.USER_TRACKS_KEY_FORMAT % user_id

        if lastfm_user is None or lastfm_session_key is None:
            return

        count = library_dao.get_listened_tracks_count(user_id)

        max_timestamp = library_dao.get_listened_track_max_timestamp(user_id)

        index = 0

        for track in lastfm.get_user_tracks(lastfm_user, lastfm_session_key):
            # if we have less than 90% of what lastfm reports that the total
            # should be we assume something went wrong before and we redo
            # the whole thing from the start.
            #
            # this could occur if the user shuts down opmuse before this finishes
            # or if lastfm goes down or rate limits the hell out of us.
            #
            # the reason we only do it when it's less than 90% is because there's
            # a bug in the lastfm api where if the user has submitted non utf8 data
            # or otherwise "corrupt" data the api call will fail with an empty
            # response and we'll miss out on some tracks and there's nothing we
            # can do about that. http://www.last.fm/group/Last.fm+Web+Services/forum/21604/_/626352
            #
            # this could obviously also 'cause some unnecessary re-fetching of all
            # tracks on every run in some cases, but i'm not gonna fix that until
            # someone reports it as an actual issue...
            if index == 0 and count > 0 and count / track['total'] < .90:
                max_timestamp = None
                count = 0
                library_dao.delete_listened_tracks(user_id)

            if max_timestamp is not None and track['timestamp'] is not None and max_timestamp >= track['timestamp']:
                break

            library_dao.add_listened_track(user_id, track['name'], track['artist'], track['album'], track['timestamp'])

            index += 1

        cache.set(key, True)

    _add_listened_tracks.bgtask_name = "Add lastfm listened tracks for user {1}"

    def update_user(self, user):
        key = Remotes.USER_KEY_FORMAT % user.id

        if cache.needs_update(key, age = Remotes.USER_AGE):
            cache.keep(key)
            cherrypy.engine.bgtask.put(self._fetch_user, 10, user.id, user.lastfm_user,
                                       user.lastfm_session_key)

        self.update_user_tracks(user)

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
            cherrypy.engine.bgtask.put(self._fetch_track, 10, track.id)

    def _fetch_track(self, id):
        key = Remotes.TRACK_KEY_FORMAT % id

        try:
            track_entity = get_database().query(Track).filter(Track.id == id).one()
        except NoResultFound:
            # track was probably removed, edited and therefor recreated. either
            # way we just ignore it in either which case
            return

        album_name = track_entity.album.name if track_entity.album is not None else None
        artist_name = track_entity.artist.name if track_entity.artist is not None else None

        track = {
            'wikipedia': wikipedia.get_track(artist_name, album_name, track_entity.name)
        }

        cache.set(key, track)

        ws.emit_all('remotes.track.fetched', id)

    _fetch_track.bgtask_name = "Fetch info for track {0}"

    def get_track(self, track):
        key = Remotes.TRACK_KEY_FORMAT % track.id

        return cache.get(key)

    def update_album(self, album):
        key = Remotes.ALBUM_KEY_FORMAT % album.id

        if cache.needs_update(key, age = Remotes.ALBUM_AGE):
            cache.keep(key)
            cherrypy.engine.bgtask.put(self._fetch_album, 11, album.id)

    def _fetch_album(self, id):
        key = Remotes.ALBUM_KEY_FORMAT % id

        try:
            album_entity = get_database().query(Album).filter(Album.id == id).one()
        except NoResultFound:
            # album removed, just ignore
            return

        if len(album_entity.artists) > 0:
            artist_name = album_entity.artists[0].name
        else:
            artist_name = None

        album = {
            'wikipedia': wikipedia.get_album(artist_name, album_entity.name),
            'lastfm': lastfm.get_album(artist_name, album_entity.name),
            'musicbrainz': musicbrainz.get_album(album_entity)
        }

        cache.set(key, album)

        ws.emit_all('remotes.album.fetched', id, [track.id for track in album_entity.tracks])

    _fetch_album.bgtask_name = "Fetch info for album {0}"

    def get_album(self, album):
        key = Remotes.ALBUM_KEY_FORMAT % album.id

        return cache.get(key)

    def update_artist(self, artist):
        key = Remotes.ARTIST_KEY_FORMAT % artist.id

        if cache.needs_update(key, age = Remotes.ARTIST_AGE):
            cache.keep(key)
            cherrypy.engine.bgtask.put(self._fetch_artist, 12, artist.id)

    def _fetch_artist(self, id):
        key = Remotes.ARTIST_KEY_FORMAT % id

        try:
            artist_entity = get_database().query(Artist).filter(Artist.id == id).one()
        except NoResultFound:
            # artist removed, just ignore
            return

        artist = {
            'wikipedia': wikipedia.get_artist(artist_entity.name),
            'lastfm': lastfm.get_artist(artist_entity.name),
            'google': google.get_artist_search(artist_entity),
            'musicbrainz': musicbrainz.get_artist(artist_entity)
        }

        cache.set(key, artist)

        ws.emit_all('remotes.artist.fetched', id,
                    [album.id for album in artist_entity.albums],
                    [track.id for track in artist_entity.tracks])

    _fetch_artist.bgtask_name = "Fetch info for artist {0}"

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
