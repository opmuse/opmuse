import sys
import logging
import hashlib
import cherrypy
import urllib
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import Column, Integer, String
from repoze.who.middleware import PluggableAuthenticationMiddleware
from repoze.who.plugins.auth_tkt import AuthTktCookiePlugin
from repoze.who.plugins.redirector import RedirectorPlugin
from repoze.who.classifiers import default_request_classifier
from repoze.who.classifiers import default_challenge_decider
from repoze.who._compat import get_cookies
from opmuse.jinja import env
from opmuse.database import Base, get_session

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    login = Column(String(128), index=True, unique=True)
    password = Column(String(128))
    salt = Column(String(64))

    def __init__(self, login, password, salt):
        self.login = login
        self.password = password
        self.salt = salt

class AuthenticatedTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.start, priority=20)

    def start(self):
        if ('repoze.who.identity' not in cherrypy.request.wsgi_environ or
            not cherrypy.request.wsgi_environ.get('repoze.who.identity')):
            raise cherrypy.HTTPError(401)

# TODO move this to AuthenticatedTool
class JinjaAuthenticatedTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'before_handler',
                               self.start, priority=20)

    def start(self):

        env.globals['authenticated'] = ('repoze.who.identity' in cherrypy.request.wsgi_environ and
            cherrypy.request.wsgi_environ.get('repoze.who.identity'))

        identity = cherrypy.request.wsgi_environ.get('repoze.who.identity')

        if identity is not None:

            login = identity['repoze.who.plugins.auth_tkt.userid']

            user = (cherrypy.request.database.query(User)
                .filter_by(login=login).one())

            env.globals['user'] = cherrypy.request.user = user

class DatabaseAuthenticator(object):

    def authenticate(self, environ, identity):
        try:
            login = identity['login']
            password = identity['password']
        except KeyError:
            return None

        try:
            user = (cherrypy.request.database.query(User)
                .filter_by(login=login).one())

            hashed = hash_password(password, user.salt)

            if hashed == user.password:
                return user.login

        except NoResultFound:
            pass

        return None

class AuthTktQueryStringIdentifier:
    """
    identifier plugin that fakes a cookie from a query string param to auth
    with AuthTktCookiePlugin
    """
    def identify(self, environ):
        qs = urllib.parse.parse_qsl(environ.get('QUERY_STRING'))

        remove_index = auth_tkt = None
        for index, pair in enumerate(qs):
            # TODO use "cookie_name" prop from authtkt plugin...
            if pair[0] == 'auth_tkt':
                auth_tkt = pair[1]
                remove_index = index

        if remove_index is None:
            return

        qs.pop(remove_index)

        cookie = environ.get('HTTP_COOKIE')

        environ['QUERY_STRING'] = urllib.parse.urlencode(qs)
        # TODO use "cookie_name" prop from authtkt plugin...
        # TODO use repoze.who._compat.get_cookies
        environ['HTTP_COOKIE'] = 'auth_tkt="%s"; %s' % (auth_tkt, cookie)

    def remember(self, environ, identity):
        pass

    def forget(self, environ, identity):
        pass

class UserSecretAuthTktCookiePlugin(AuthTktCookiePlugin):
    """
    wrapper class around AuthTktCookiePlugin that uses the users unique salt
    as secret for the auth cookie
    """

    def __init__(self, **kwargs):
        secret = None
        AuthTktCookiePlugin.__init__(self, secret, **kwargs)

    def remember(self, environ, identity):
        self.secret = self.get_secret(environ, identity)
        return AuthTktCookiePlugin.remember(self, environ, identity)

    def identify(self, environ):
        self.secret = self.get_secret(environ)
        return AuthTktCookiePlugin.identify(self, environ)

    def get_secret(self, environ, identity = None):
        if identity is None or 'login' not in identity:
            cookies = get_cookies(environ)
            cookie = cookies.get(self.cookie_name)

            if cookie is None or not cookie.value:
                return None

            # XXX stolen from repoze.who._auth_tkt.parse_ticket(),
            #     which hopefully, and likely, won't change for a while...
            login, junk = cookie.value[40:].split('!', 1)
        else:
            login = identity['login']

        database = get_session()

        user = database.query(User).filter_by(login = login).one()

        salt = user.salt

        database.remove()

        return salt


def hash_password(password, salt):
    hashed = password

    # 4556 iterations of sha512
    for i in range(0, 4556):
        hashed = hashlib.sha512(("%s%s" % (hashed, salt)).encode()).hexdigest()

    return hashed

def repozewho_pipeline(app):

    database = DatabaseAuthenticator()
    redirector = RedirectorPlugin('/login')

    auth_tkt = UserSecretAuthTktCookiePlugin(cookie_name = 'auth_tkt', include_ip = True)
    query_string = AuthTktQueryStringIdentifier()

    identifiers = [('query_string', query_string), ('auth_tkt', auth_tkt)]
    authenticators = [('auth_tkt', auth_tkt), ('database', database)]
    challengers = [('redirector', redirector)]
    mdproviders = []

    return PluggableAuthenticationMiddleware(
        app,
        identifiers,
        authenticators,
        challengers,
        mdproviders,
        default_request_classifier,
        default_challenge_decider,
        log_stream = cherrypy.log.access_log,
        log_level = logging.INFO
    )

