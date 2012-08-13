import cherrypy
from sqlalchemy import Column, String
from pylast import get_lastfm_network, SessionKeyGenerator, WSError
from opmuse.who import User

User.lastfm_session_key = Column(String(32))

class Lastfm:
    def get_network(self, session_key = ''):
        key = cherrypy.config['opmuse']['lastfm.key']
        secret = cherrypy.config['opmuse']['lastfm.secret']
        return get_lastfm_network(key, secret, session_key)

    def get_authenticated_user(self, session_key):
        network = self.get_network(session_key)
        return network.get_authenticated_user()

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
