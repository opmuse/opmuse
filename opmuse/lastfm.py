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

class NoSessionError(Exception):
    pass

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

    def end_transcoding(self, sender):
        try:
            self.scrobble(sender)
        except NetworkError:
            # TODO put in queue and scrobble later
            cherrypy.log('Network error, failed to scrobble.')
        except NoSessionError: # user hasn't authenticated his lastfm account, ignore
            pass

    def start_transcoding(self, sender):
        try:
            self.update_now_playing(sender)
        except NetworkError:
            cherrypy.log('Network error, failed to update now playing.')
        except NoSessionError: # user hasn't authenticated his lastfm account, ignore
            pass

    def get_network(self, session_key = ''):
        key = cherrypy.request.app.config['opmuse']['lastfm.key']
        secret = cherrypy.request.app.config['opmuse']['lastfm.secret']
        return get_lastfm_network(key, secret, session_key)

    def get_authenticated_user_name(self):
        session_key = cherrypy.request.user.lastfm_session_key

        if session_key is None:
            raise NoSessionError

        network = self.get_network(session_key)

        user = network.get_authenticated_user()

        if user is not None:
            return user.get_name()

    def update_now_playing(self, track):
        session_key = cherrypy.request.user.lastfm_session_key

        if session_key is None:
            raise NoSessionError

        network = self.get_network(session_key)

        network.update_now_playing(**self._get_args(track))

    def _get_args(self, track):

        # lastfm can't handle track number that ain't numbers
        if re.match('^[0-9]+$', track.number):
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

    def scrobble(self, track):
        session_key = cherrypy.request.user.lastfm_session_key

        if session_key is None:
            raise NoSessionError

        network = self.get_network(session_key)

        args = {
            # assume track started playing track length seconds ago
            'timestamp': self.get_utc_timestamp() - track.duration
        }

        args.update(self._get_args(track))

        network.scrobble(**args)

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

