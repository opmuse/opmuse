# Copyright 2012-2014 Mattias Fliesberg
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

import logging
import hashlib
import cherrypy
import urllib
import re
import datetime
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import Column, Integer, String, Table, ForeignKey, DateTime
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.hybrid import hybrid_property
from opmuse.database import Base, get_session, get_database
from opmuse.utils import memoize, HTTPRedirect


class Role(Base):
    __tablename__ = 'roles'

    users_in_roles = Table('users_in_roles', Base.metadata,
                           Column('user_id', Integer, ForeignKey('users.id', name='fk_users_in_roles_user_id')),
                           Column('role_id', Integer, ForeignKey('roles.id', name='fk_users_in_roles_role_id')))

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
    active = Column(DateTime, index=True)
    created = Column(DateTime, index=True)

    def __init__(self, login, password, mail, salt):
        self.login = login
        self.password = password
        self.mail = mail
        self.salt = salt
        self.created = datetime.datetime.now()

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

        return '//www.gravatar.com/avatar/%s.png?size=%s' % (hash, size)


def is_granted(roles):
    if len(roles) > 0:
        for role in cherrypy.request.user.roles:
            if role.name in roles:
                break
        else:
            return False

    return True


def check_credentials(login, password):
    try:
        user = get_database().query(User).filter_by(login=login).one()
        user.active = datetime.datetime.now()

        hashed = hash_password(password, user.salt)

        if hashed == user.password:
            return True
    except NoResultFound:
        return False


class AuthenticatedTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'before_handler', self.start, priority=10)

    def start(self, needs_auth=False, roles=[]):
        if re.match('^/static', cherrypy.request.path_info):
            return

        login = cherrypy.session.get('_login')

        cherrypy.response.headers['X-Opmuse-Authenticated'] = 'true' if login else 'false'

        if login:
            cherrypy.request.user = get_database().query(User).filter_by(login=login).one()

            if not is_granted(roles):
                raise cherrypy.HTTPError(401)
        elif needs_auth:
            raise HTTPRedirect("/login")
        else:
            cherrypy.request.user = None


class SessionQueryStringTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource', self.start, priority=20)

    def start(self):
        params = urllib.parse.parse_qs(cherrypy.request.query_string)

        if 'session_id' in params and len(params['session_id']) == 1:
            cherrypy.request.cookie['session_id'] = params['session_id'][0]


def hash_password(password, salt):
    hashed = password

    # 4556 iterations of sha512
    for i in range(0, 4556):
        hashed = hashlib.sha512(("%s%s" % (hashed, salt)).encode()).hexdigest()

    return hashed


class SecurityDao:
    @memoize
    def get_user(self, id):
        try:
            return get_database().query(User).filter_by(id=id).one()
        except NoResultFound:
            pass


security_dao = SecurityDao()
