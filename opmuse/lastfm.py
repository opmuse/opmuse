import re
import cherrypy
import calendar
import datetime
from functools import lru_cache
from sqlalchemy import Column, String
from pylast import get_lastfm_network, SessionKeyGenerator, WSError, NetworkError
from pylast import PERIOD_OVERALL
from pydispatch import dispatcher
from opmuse.security import User

User.lastfm_session_key = Column(String(32))
User.lastfm_user = Column(String(64))

def log(msg):
    cherrypy.log(msg, context='lastfm')

class Lastfm:
    def __init__(self):
        dispatcher.connect(
            self.start_transcoding,
            signal='start_transcoding',
            sender=dispatcher.Any
        )
        dispatcher.connect(
            self.end_transcoding,
            signal='end_transcoding',
            sender=dispatcher.Any
        )

    def start_transcoding(self, sender):
        cherrypy.request.lastfm_start_transcoding_time = self.get_utc_timestamp()
        session_key = cherrypy.request.user.lastfm_session_key
        cherrypy.engine.bgtask.put(self.update_now_playing, session_key,
            **self.track_to_args(sender))

    def end_transcoding(self, sender):
        session_key = cherrypy.request.user.lastfm_session_key
        user = cherrypy.request.user.login
        start_time = cherrypy.request.lastfm_start_transcoding_time
        cherrypy.request.lastfm_start_transcoding_time = None
        cherrypy.engine.bgtask.put(self.scrobble, user, session_key,
            start_time, **self.track_to_args(sender))

    def get_network(self, session_key = ''):
        config = cherrypy.tree.apps[''].config['opmuse']
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
        except NetworkError:
            log('Network error, failed to update now playing for "%s - %s - %s".' % (
                args['artist'],
                args['album'],
                args['title'],
            ))

    def scrobble(self, user, session_key, start_time, **args):
        if session_key is None:
            return

        try:
            time_since_start = self.get_utc_timestamp() - start_time

            if not (args['duration'] > 30 and (time_since_start > 4 * 60 or
                time_since_start > args['duration'] / 2)):
                log('%s skipped scrobbling "%s - %s - %s" which is %d seconds long and started playing %d seconds ago.' % (
                    user,
                    args['artist'],
                    args['album'],
                    args['title'],
                    args['duration'],
                    time_since_start
                ))
                return

            network = self.get_network(session_key)

            args['timestamp'] = start_time

            network.scrobble(**args)

            log('%s scrobbled "%s - %s - %s" which is %d seconds long and started playing %d seconds ago.' % (
                user,
                args['artist'],
                args['album'],
                args['title'],
                args['duration'],
                time_since_start
            ))

        except NetworkError:
            # TODO put in queue and scrobble later
            log('Network error, failed to scrobble "%s - %s - %s".' % (
                args['artist'],
                args['album'],
                args['title'],
            ))

    def track_to_args(self, track):

        # lastfm can't handle track number that ain't numbers
        if track.number is not None and re.match('^[0-9]+$', track.number):
            track_number = track.number
        else:
            track_number = None

        return {
            'artist': track.artist.name,
            'title': track.name,
            'album': track.album.name,
            'album_artist': None,
            'duration': track.duration,
            'track_number': track_number
        }

    def get_utc_timestamp(self):
        return calendar.timegm(
            datetime.datetime
                .utcnow()
                .utctimetuple()
        )

    @lru_cache(maxsize=None)
    def get_user(self, user_name):
        session_key = cherrypy.request.user.lastfm_session_key

        try:
            network = self.get_network(session_key)
            user = network.get_user(user_name)

            recent_tracks = []

            for playedTrack in user.get_recent_tracks(40):
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
                'url': user.get_url()
            }

        except NetworkError:
            log('Network error, failed to get user "%s".' % (
                user_name
            ))

    @lru_cache(maxsize=None)
    def get_top_artists_overall(self, user_name, page = 1, limit = 50):
        session_key = cherrypy.request.user.lastfm_session_key

        try:
            network = self.get_network(session_key)
            user = network.get_user(user_name)

            top_artists_overall = []

            index = (page - 1) * limit
            sub_index = 0
            last_weight = None

            for artist in self._param_call(user, 'get_top_artists', {'limit': limit, 'page': page}, [PERIOD_OVERALL]):
                sub_index += 1

                if last_weight is None or artist.weight != last_weight:
                    index += sub_index
                    sub_index = 0

                top_artists_overall.append({
                    'name': artist.item.get_name(),
                    'playcount': artist.item.get_playcount(),
                    'weight': int(artist.weight),
                    'index': index
                })

                last_weight = artist.weight

            return top_artists_overall
        except NetworkError:
            log('Network error, failed to get album "%s - %s".' % (
                artist_name,
                album_name
            ))

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

    @lru_cache(maxsize=None)
    def get_album(self, artist_name, album_name):
        try:
            network = self.get_network()
            album = network.get_album(artist_name, album_name)

            return {
                'url': album.get_url(),
                'name': album.get_name(),
                'wiki': album.get_wiki_summary(),
                'cover': album.get_cover_image()
            }
        except (WSError, NetworkError) as error:
            log('Failed to get album "%s - %s": %s' % (
                artist_name,
                album_name,
                error
            ))

    @lru_cache(maxsize=None)
    def get_artist(self, artist_name):
        try:
            network = self.get_network()
            artist = network.get_artist(artist_name)

            similars = []

            for similar in artist.get_similar(5):
                similars.append({
                    'name': similar.item.get_name()
                })

            tags = [str(topItem.item) for topItem in artist.get_top_tags(5)]

            return {
                'url': artist.get_url(),
                'cover': artist.get_cover_image(),
                'tags': tags,
                'bio': artist.get_bio_summary(),
                'similar': similars
            }
        except (WSError, NetworkError) as error:
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

