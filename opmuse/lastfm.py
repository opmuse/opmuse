import re
import cherrypy
import calendar
import datetime
import math
from cherrypy.process.plugins import Monitor
from functools import lru_cache
from sqlalchemy import Column, String
from pylast import get_lastfm_network, SessionKeyGenerator, WSError, NetworkError, MalformedResponseError
from pylast import PERIOD_OVERALL
from opmuse.security import User
from opmuse.database import get_session
from opmuse.cache import Cache

User.lastfm_session_key = Column(String(32))
User.lastfm_user = Column(String(64))


def log(msg):
    cherrypy.log(msg, context='lastfm')


class Lastfm:
    def __init__(self):
        cherrypy.engine.subscribe('transcoding.start', self.transcoding_start)
        cherrypy.engine.subscribe('transcoding.end', self.transcoding_end)
        cherrypy.engine.subscribe('transcoding.progress', self.transcoding_progress)

    def transcoding_progress(self, progress, track):
        cherrypy.request.lastfm_progress = progress['seconds'] - progress['seconds_ahead']

    def transcoding_start(self, track):
        session_key = cherrypy.request.user.lastfm_session_key
        cherrypy.engine.bgtask.put(self.update_now_playing, session_key, **self.track_to_args(track))

    def transcoding_end(self, track):
        if hasattr(cherrypy.request, 'lastfm_progress') and cherrypy.request.lastfm_progress is not None:
            seconds = cherrypy.request.lastfm_progress
            session_key = cherrypy.request.user.lastfm_session_key
            user = cherrypy.request.user.login
            cherrypy.engine.bgtask.put(self.scrobble, user, session_key, seconds, **self.track_to_args(track))

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
            datetime.datetime.utcnow().utctimetuple()
        )

    def get_user(self, user_name, session_key = None):
        if session_key is None:
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
                'url': user.get_url(),
                'top_artists_overall': self.get_top_artists_overall(user_name, 1, 500, session_key),
                'top_albums_overall': self.get_top_albums_overall(user_name, 1, 500, session_key)
            }

        except NetworkError:
            log('Network error, failed to get user "%s".' % (
                user_name
            ))

    def get_top_albums_overall(self, user_name, page = 1, limit = 50, session_key = None):
        if session_key is None:
            session_key = cherrypy.request.user.lastfm_session_key

        try:
            network = self.get_network(session_key)
            user = network.get_user(user_name)

            top_albums_overall = []

            index = (page - 1) * limit
            sub_index = 0
            last_weight = None

            for album in self._param_call(user, 'get_top_albums', {'limit': limit, 'page': page}, [PERIOD_OVERALL]):
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

                top_albums_overall.append({
                    'name': album.item.get_name(),
                    'playcount': playcount,
                    'weight': int(album.weight),
                    'index': index
                })

                last_weight = album.weight

            return top_albums_overall
        except NetworkError:
            log('Network error, failed to get %s.' % user_name)

    def get_top_artists_overall(self, user_name, page = 1, limit = 50, session_key = None):
        if session_key is None:
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

                playcount = None

                try:
                    playcount = artist.item.get_playcount()
                except MalformedResponseError:
                    # this seems to occur on some items :/
                    pass

                top_artists_overall.append({
                    'name': artist.item.get_name(),
                    'playcount': playcount,
                    'weight': int(artist.weight),
                    'index': index
                })

                last_weight = artist.weight

            return top_artists_overall
        except NetworkError:
            log('Network error, failed to get %s.' % user_name)

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
        except (WSError, NetworkError, MalformedResponseError) as error:
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

            for similar in artist.get_similar(10):
                similars.append({
                    'name': similar.item.get_name()
                })

            tags = [str(topItem.item) for topItem in artist.get_top_tags(10)]

            return {
                'url': artist.get_url(),
                'cover': artist.get_cover_image(),
                'listeners': artist.get_listener_count(),
                'tags': tags,
                'bio': artist.get_bio_summary(),
                'similar': similars
            }
        except (WSError, NetworkError, MalformedResponseError) as error:
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


class Users:
    AGE = 3600 * 2
    KEY_FORMAT = "lastfm_user_%d"

    def __init__(self, session):
        self._cache = Cache(session)

    def needs_update(self, user):
        return self._cache.needs_update(Users.KEY_FORMAT % user.id, Users.AGE)

    def get(self, user):
        return self._cache.get(Users.KEY_FORMAT % user.id)

    def set(self, user, lastfm_user):
        self._cache.set(Users.KEY_FORMAT % user.id, lastfm_user)


class LastfmMonitor(Monitor):
    FREQUENCY = 120

    def __init__(self, bus, *args, **kwargs):
        Monitor.__init__(self, bus, self.run, LastfmMonitor.FREQUENCY, *args, **kwargs)

    def run(self):
        session = get_session()

        users = Users(session)

        for user in session.query(User).filter("lastfm_user is not null").all():
            if users.needs_update(user):
                lastfm_user = lastfm.get_user(user.lastfm_user, user.lastfm_session_key)
                users.set(user, lastfm_user)
                log("Updated user %s." % user.login)


class LastfmTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.bind_session, priority=20)

    def bind_session(self):
        cherrypy.request.lastfm_users = Users(cherrypy.request.database)

lastfm = Lastfm()
