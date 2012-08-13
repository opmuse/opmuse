import cherrypy
from sqlalchemy import Column, String
from pylast import get_lastfm_network, SessionKeyGenerator, WSError
from opmuse.who import User

User.lastfm_session_key = Column(String(32))
User.lastfm_user = Column(String(64))

class NoSessionError(Exception):
    pass

class Lastfm:
    def get_network(self, session_key = ''):
        key = cherrypy.config['opmuse']['lastfm.key']
        secret = cherrypy.config['opmuse']['lastfm.secret']
        return get_lastfm_network(key, secret, session_key)

    def get_authenticated_user_name(self):
        session_key = cherrypy.request.user.lastfm_session_key

        if session_key is None:
            raise NoSessionError

        network = self.get_network(session_key)

        user = network.get_authenticated_user()

        if user is not None:
            return user.get_name()


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
