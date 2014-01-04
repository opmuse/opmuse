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

import re
import cherrypy
import calendar
import datetime
import math
from sqlalchemy import Column, String
from pylast import get_lastfm_network, SessionKeyGenerator, WSError, NetworkError, MalformedResponseError
from pylast import PERIOD_OVERALL
from opmuse.security import User
from opmuse.database import get_session
from opmuse.cache import cache
from opmuse.search import search

User.lastfm_session_key = Column(String(32))
User.lastfm_user = Column(String(64))


class LastfmError(Exception):
    pass


def log(msg):
    cherrypy.log(msg, context='lastfm')


class Lastfm:
    def __init__(self):
        cherrypy.engine.subscribe('transcoding.start', self.transcoding_start)
        cherrypy.engine.subscribe('transcoding.end', self.transcoding_end)
        cherrypy.engine.subscribe('transcoding.progress', self.transcoding_progress)

    def transcoding_progress(self, progress, transcoder, track):
        cherrypy.request.lastfm_progress = progress

    def transcoding_start(self, transcoder, track):
        session_key = cherrypy.request.user.lastfm_session_key
        cherrypy.engine.bgtask.put(self.update_now_playing, 30, session_key, **self.track_to_args(track))

    def transcoding_end(self, track, transcoder):
        if hasattr(cherrypy.request, 'lastfm_progress') and cherrypy.request.lastfm_progress is not None:
            lastfm_progress = cherrypy.request.lastfm_progress

            seconds_ahead = lastfm_progress['seconds_ahead']
            session_key = cherrypy.request.user.lastfm_session_key
            user = cherrypy.request.user.login

            seconds = lastfm_progress['seconds'] - seconds_ahead
            cherrypy.engine.bgtask.put(self.scrobble, 30, user, session_key, seconds, **self.track_to_args(track))

    def get_network(self, session_key = ''):
        config = cherrypy.tree.apps[''].config['opmuse']

        if 'lastfm.key' not in config or 'lastfm.secret' not in config:
            raise LastfmError('lastfm.key and lastfm.secret needs to be set for lastfm features.')

        key = config['lastfm.key']
        secret = config['lastfm.secret']
        return get_lastfm_network(key, secret, session_key)

    def get_authenticated_user_name(self):
        session_key = cherrypy.request.user.lastfm_session_key

        network = self.get_network(session_key)

        user = network.get_authenticated_user()

        if user is not None:
            return user.get_name()

    def update_now_playing(self, session_key, **args):
        if session_key is None:
            return

        try:
            network = self.get_network(session_key)
            network.update_now_playing(**args)
        except (LastfmError, WSError, NetworkError, MalformedResponseError) as error:
            log('Network error, failed to update now playing for "%s - %s - %s": %s.' % (
                args['artist'],
                args['album'],
                args['title'],
                error
            ))

    update_now_playing.bgtask_name = "Lastfm update now playing"

    def scrobble(self, user, session_key, seconds, **args):
        if session_key is None:
            return

        try:
            if not (args['duration'] > 30 and (seconds > 4 * 60 or seconds > args['duration'] / 2)):
                log('%s skipped scrobbling "%s - %s - %s" which is %d seconds long and started playing %d seconds ago.' % (
                    user,
                    args['artist'],
                    args['album'],
                    args['title'],
                    args['duration'],
                    seconds
                ))
                return

            network = self.get_network(session_key)

            args['timestamp'] = math.floor(self.get_utc_timestamp() - seconds)

            network.scrobble(**args)

            log('%s scrobbled "%s - %s - %s" which is %d seconds long and started playing %d seconds ago.' % (
                user,
                args['artist'],
                args['album'],
                args['title'],
                args['duration'],
                seconds
            ))

        except (LastfmError, WSError, NetworkError, MalformedResponseError) as error:
            # TODO put in queue and scrobble later
            log('Network error, failed to scrobble "%s - %s - %s": %s.' % (
                args['artist'],
                args['album'],
                args['title'],
                error
            ))

    scrobble.bgtask_name = "Lastfm scrobble track for {0}"

    def track_to_args(self, track):

        # lastfm can't handle track number that ain't numbers
        if track.number is not None and re.match('^[0-9]+$', track.number):
            track_number = track.number
        else:
            track_number = None

        return {
            'artist': track.artist.name if track.artist is not None else None,
            'title': track.name,
            'album': track.album.name if track.album is not None else None,
            'album_artist': None,
            'duration': track.duration,
            'track_number': track_number
        }

    def get_utc_timestamp(self):
        return calendar.timegm(
            datetime.datetime.utcnow().utctimetuple()
        )

    def get_user(self, user_name, session_key = None):
        if session_key is None:
            session_key = cherrypy.request.user.lastfm_session_key

        try:
            network = self.get_network(session_key)
            user = network.get_user(user_name)

            recent_tracks = []

            for playedTrack in user.get_recent_tracks(200):
                album = playedTrack.track.get_album()

                if album is None:
                    album = ''

                recent_tracks.append({
                    "artist": str(playedTrack.track.get_artist()),
                    "album": str(album),
                    "name": str(playedTrack.track.get_title()),
                    "timestamp": playedTrack.timestamp
                })

            return {
                'recent_tracks': recent_tracks,
                'url': user.get_url(),
                'playcount': user.get_playcount(),
                'top_artists_month': self.get_top_artists('1month', user_name, 1, 500, session_key),
                'top_artists_overall': self.get_top_artists(PERIOD_OVERALL, user_name, 1, 500, session_key),
                'top_albums_overall': self.get_top_albums(PERIOD_OVERALL, user_name, 1, 500, session_key)
            }

        except (LastfmError, WSError, NetworkError, MalformedResponseError) as error:
            log('Failed to get user "%s": %s.' % (
                user_name,
                error
            ))

    def get_top_albums(self, type, user_name, page = 1, limit = 50, session_key = None):
        if session_key is None:
            session_key = cherrypy.request.user.lastfm_session_key

        try:
            network = self.get_network(session_key)
            user = network.get_user(user_name)

            top_albums = []

            index = (page - 1) * limit
            sub_index = 0
            last_weight = None

            for album in self._param_call(user, 'get_top_albums', {'limit': limit, 'page': page}, [type]):
                sub_index += 1

                if last_weight is None or album.weight != last_weight:
                    index += sub_index
                    sub_index = 0

                playcount = None

                try:
                    playcount = album.item.get_playcount()
                except MalformedResponseError:
                    # this seems to occur on some items :/
                    pass

                top_albums.append({
                    'name': album.item.get_name(),
                    'playcount': playcount,
                    'weight': int(album.weight),
                    'index': index
                })

                last_weight = album.weight

            return top_albums
        except (LastfmError, WSError, NetworkError, MalformedResponseError) as error:
            log('Network error, failed to get %s: %s.' % (user_name, error))

    def get_top_artists(self, type, user_name, page = 1, limit = 50, session_key = None):
        if session_key is None:
            session_key = cherrypy.request.user.lastfm_session_key

        try:
            network = self.get_network(session_key)
            user = network.get_user(user_name)

            top_artists = []

            index = (page - 1) * limit
            sub_index = 0
            last_weight = None

            for artist in self._param_call(user, 'get_top_artists', {'limit': limit, 'page': page}, [type]):
                sub_index += 1

                if last_weight is None or artist.weight != last_weight:
                    index += sub_index
                    sub_index = 0

                playcount = None

                try:
                    playcount = artist.item.get_playcount()
                except MalformedResponseError:
                    # this seems to occur on some items :/
                    pass

                top_artists.append({
                    'name': artist.item.get_name(),
                    'playcount': playcount,
                    'weight': int(artist.weight),
                    'index': index
                })

                last_weight = artist.weight

            return top_artists
        except (LastfmError, WSError, NetworkError, MalformedResponseError) as error:
            log('Network error, failed to get %s: %s.' % (user_name, error))

    def _param_call(self, object, method, params, args):
        """
        hacky hack to send extra params to lastfm api
        """

        prev_get_params = object._get_params

        def _get_params():
            _params = prev_get_params()
            params.update(_params)
            return params

        object._get_params = _get_params

        ret = getattr(object, method)(*args)

        object._get_params = prev_get_params

        return ret

    def get_album(self, artist_name, album_name):
        try:
            network = self.get_network()
            album = network.get_album(artist_name, album_name)
            tags = [str(tag) for tag in album.get_top_tags(20)]

            return {
                'url': album.get_url(),
                'date': album.get_release_date(),
                'listeners': album.get_listener_count(),
                'wiki': album.get_wiki_summary(),
                'name': album.get_name(),
                'tags': tags,
                'cover': album.get_cover_image()
            }
        except (LastfmError, WSError, NetworkError, MalformedResponseError) as error:
            log('Failed to get album "%s - %s": %s' % (
                artist_name,
                album_name,
                error
            ))

    def get_tag(self, tag_name, limit = 50, page = 1):
        try:
            network = self.get_network()
            tag = network.get_tag(tag_name)

            artists = []

            for artist in self._param_call(tag, 'get_top_artists', {'limit': limit, 'page': page}, []):
                artists.append({
                    'name': artist.item.get_name()
                })

            albums = []

            for album in self._param_call(tag, 'get_top_albums', {'limit': limit, 'page': page}, []):
                albums.append({
                    'name': album.item.get_name()
                })

            return {
                'url': tag.get_url(),
                'artists': artists,
                'albums': albums
            }
        except (LastfmError, WSError, NetworkError, MalformedResponseError) as error:
            log('Failed to get tag "%s": %s' % (
                tag_name,
                error
            ))

    def get_artist(self, artist_name):
        try:
            network = self.get_network()
            artist = network.get_artist(artist_name)

            similars = []

            count = 0

            for similar in artist.get_similar(100):
                name = similar.item.get_name()

                results = search.query_artist(name, exact=True)

                if len(results) > 0:
                    similars.append({
                        'name': results[0].name,
                        'slug': results[0].slug,
                    })

                    count += 1

                if count >= 20:
                    break

            tags = [str(topItem.item) for topItem in artist.get_top_tags(20)]

            bio = (artist._request("artist.getInfo", True)
                   .getElementsByTagName("bio")[0]
                   .getElementsByTagName('summary')[0]
                   .firstChild)

            if bio is not None:
                bio = bio.wholeText
            else:
                bio = ''

            return {
                'url': artist.get_url(),
                'bio': bio.strip(),
                'cover': artist.get_cover_image(),
                'listeners': artist.get_listener_count(),
                'tags': tags,
                'similar': similars
            }
        except (LastfmError, WSError, NetworkError, MalformedResponseError) as error:
            log('Failed to get artist "%s": %s' % (
                artist_name,
                error
            ))


class SessionKey:

    def __init__(self):
        self.network = lastfm.get_network()
        self.generator = SessionKeyGenerator(self.network)
        self.auth_url = self.generator.get_web_auth_url()

    def get_auth_url(self):
        return self.auth_url

    def get_session_key(self):
        key = None

        try:
            key = self.generator.get_web_auth_session_key(self.auth_url)
        except WSError as e:
            log("session key failed: %s" % e)

        return key


lastfm = Lastfm()
