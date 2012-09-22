import re
import cherrypy
import calendar
import datetime
from sqlalchemy import Column, String
from pylast import get_lastfm_network, SessionKeyGenerator, WSError, NetworkError
from pydispatch import dispatcher
from opmuse.security import User

User.lastfm_session_key = Column(String(32))
User.lastfm_user = Column(String(64))

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
            cherrypy.log('Network error, failed to update now playing for "%s - %s - %s".' % (
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
                cherrypy.log('%s skipped scrobbling "%s - %s - %s" which is %d seconds long and started playing %d seconds ago.' % (
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

            cherrypy.log('%s scrobbled "%s - %s - %s" which is %d seconds long and started playing %d seconds ago.' % (
                user,
                args['artist'],
                args['album'],
                args['title'],
                args['duration'],
                time_since_start
            ))

        except NetworkError:
            # TODO put in queue and scrobble later
            cherrypy.log('Network error, failed to scrobble "%s - %s - %s".' % (
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
            cherrypy.log("lastfm session key failed: %s" % e)

        return key

lastfm = Lastfm()

