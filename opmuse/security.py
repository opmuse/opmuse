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

import sys
import logging
import hashlib
import cherrypy
import urllib
import re
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.hybrid import hybrid_property
from repoze.who.middleware import PluggableAuthenticationMiddleware
from repoze.who.plugins.auth_tkt import AuthTktCookiePlugin
from repoze.who.plugins.redirector import RedirectorPlugin
from repoze.who.classifiers import default_request_classifier
from repoze.who.classifiers import default_challenge_decider
from repoze.who._compat import get_cookies
from opmuse.database import Base, get_session, get_database


class Role(Base):
    __tablename__ = 'roles'

    users_in_roles = Table('users_in_roles', Base.metadata,
                           Column('user_id', Integer, ForeignKey('users.id')),
                           Column('role_id', Integer, ForeignKey('roles.id')))

    id = Column(Integer, primary_key=True)
    name = Column(String(128), index=True, unique=True)

    users = relationship("User", secondary=users_in_roles,
                         backref=backref('roles', lazy='joined'))

    def __init__(self, name):
        self.name = name


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    login = Column(String(128), index=True, unique=True)
    mail = Column(String(255), index=True, unique=True)
    password = Column(String(128))
    salt = Column(String(64))

    def __init__(self, login, password, mail, salt):
        self.login = login
        self.password = password
        self.mail = mail
        self.salt = salt

    @hybrid_property
    def gravatar_xsmall(self):
        return self._get_gravatar(28)

    @hybrid_property
    def gravatar_small(self):
        return self._get_gravatar(65)

    @hybrid_property
    def gravatar(self):
        return self._get_gravatar(80)

    @hybrid_property
    def gravatar_large(self):
        return self._get_gravatar(180)

    def _get_gravatar(self, size):
        if self.mail is None:
            return None

        hash = hashlib.md5(self.mail.encode()).hexdigest()

        return '%s://www.gravatar.com/avatar/%s.png?size=%s' % (cherrypy.request.scheme, hash, size)


def is_authenticated():
    if ('repoze.who.identity' not in cherrypy.request.wsgi_environ or
        not cherrypy.request.wsgi_environ.get('repoze.who.identity')):
        raise cherrypy.HTTPError(401)


def is_granted(roles):
    for role in cherrypy.request.user.roles:
        if role.name in roles:
            break
    else:
        return False

    return True


class AuthenticatedTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.start, priority=20)

    def start(self, needs_auth=False):
        if needs_auth:
            is_authenticated()

        identity = cherrypy.request.wsgi_environ.get('repoze.who.identity')
        cherrypy.request.user = None

        if identity is not None:
            login = identity['repoze.who.plugins.auth_tkt.userid']
            cherrypy.request.user = get_database().query(User).filter_by(login=login).one()


class AuthorizeTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.start, priority=25)

    def start(self, roles=[]):
        is_authenticated()

        if not is_granted(roles):
            raise cherrypy.HTTPError(403)


class DatabaseAuthenticator:

    def authenticate(self, environ, identity):
        try:
            login = identity['login']
            password = identity['password']
        except KeyError:
            return None

        try:
            user = get_database().query(User).filter_by(login=login).one()

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

        if identity is not None:
            identity['max_age'] = 3600 * 24 * 14

        return AuthTktCookiePlugin.remember(self, environ, identity)

    def identify(self, environ):
        uri = environ['REQUEST_URI']

        if re.match(b'^/static', uri):
            return

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

        # TODO fix, this is because it happens before database is initialized..?
        database = get_session()

        salt = ''

        try:
            user = database.query(User).filter_by(login = login).one()
            salt = user.salt
        except NoResultFound:
            pass

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

    auth_tkt = UserSecretAuthTktCookiePlugin(cookie_name = 'auth_tkt', include_ip = False)
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
