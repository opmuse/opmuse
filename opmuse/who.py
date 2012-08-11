import sys
import logging
import hashlib
import cherrypy
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import Column, Integer, String
from repoze.who.middleware import PluggableAuthenticationMiddleware
from repoze.who.plugins.auth_tkt import AuthTktCookiePlugin
from repoze.who.plugins.redirector import RedirectorPlugin
from repoze.who.classifiers import default_request_classifier
from repoze.who.classifiers import default_challenge_decider
from opmuse.jinja import env
from opmuse.database import Base

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

def hash_password(password, salt):
    hashed = password

    # 4556 iterations of sha512
    for i in range(0, 4556):
        hashed = hashlib.sha512(("%s%s" % (hashed, salt)).encode()).hexdigest()

    return hashed

def repozewho_pipeline(app):

    database = DatabaseAuthenticator()
    redirector = RedirectorPlugin('/login')

    # TODO secret needs to be set properly (by config or whatever)
    auth_tkt = AuthTktCookiePlugin('secret', 'auth_tkt', include_ip = True)

    identifiers = [('auth_tkt', auth_tkt)]
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
        log_stream = sys.stdout,
        log_level = logging.DEBUG
    )

