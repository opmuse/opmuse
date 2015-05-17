# Copyright 2012-2015 Mattias Fliesberg
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

import os
import cherrypy
import random
import string
from sqlalchemy import func
from sqlalchemy.orm.exc import NoResultFound
from opmuse.messages import messages as messages_service
from opmuse.sizeof import total_size
from opmuse.database import get_database
from opmuse.security import User, Role, hash_password
from opmuse.remotes import remotes
from opmuse.utils import HTTPRedirect
from opmuse.library import library_dao, Track
from opmuse.cache import cache


class AdminUsers:
    @staticmethod
    def _validate_user_params(login=None, mail=None, roles=None, password1=None, password2=None):
        if login is None or len(login) < 3:
            messages_service.warning('Login must be at least 3 chars.')
            raise cherrypy.HTTPError(status=409)

        if mail is None or len(mail) < 3:
            messages_service.warning('Mail must be at least 3 chars.')
            raise cherrypy.HTTPError(status=409)
            return

        if password1 is not None and password2 is not None:
            if password1 != password2:
                messages_service.warning('The passwords do not match.')
                raise cherrypy.HTTPError(status=409)

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='admin/users.html')
    def default(self):
        roles = (get_database().query(Role).order_by(Role.name).all())
        users = (get_database().query(User).order_by(User.login).all())

        for user in users:
            remotes.update_user(user)

        return {
            'users': users,
            'roles': roles
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='admin/users_add.html')
    def add(self):
        roles = (get_database().query(Role).order_by(Role.name).all())

        return {
            'roles': roles
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    def add_submit(self, login=None, mail=None, roles=None, password1=None, password2=None):

        AdminUsers._validate_user_params(login, mail, roles, password1, password2)

        if roles is None:
            roles = []

        if isinstance(roles, str):
            roles = [roles]

        salt = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(64))
        password = hash_password(password1, salt)

        user = User(login, password, mail, salt)

        get_database().add(user)

        for role in get_database().query(Role).filter(Role.id.in_(roles)):
            role.users.append(user)

        get_database().commit()

        messages_service.success('User was added.')

        raise HTTPRedirect('/admin/users')

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    @cherrypy.tools.jinja(filename='admin/users_edit.html')
    def edit(self, login):
        try:
            user = (get_database().query(User)
                    .filter_by(login=login)
                    .order_by(User.login).one())
        except NoResultFound:
            raise cherrypy.NotFound()

        roles = (get_database().query(Role).order_by(Role.name).all())

        return {
            'user': user,
            'roles': roles
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    def edit_submit(self, user_id, login=None, mail=None, roles=None,
                    password1=None, password2=None):
        try:
            user = (get_database().query(User)
                    .filter_by(id=user_id).one())
        except NoResultFound:
            raise cherrypy.NotFound()

        AdminUsers._validate_user_params(login, mail, roles, password1, password2)

        if roles is None:
            roles = []

        if isinstance(roles, str):
            roles = [roles]

        password = hash_password(password1, user.salt)

        user.login = login
        user.mail = mail
        user.password = password

        user.roles[:] = []

        for role in get_database().query(Role).filter(Role.id.in_(roles)):
            role.users.append(user)

        get_database().commit()

        messages_service.success('User was edited.')

        raise HTTPRedirect('/admin/users')


class Admin:
    users = AdminUsers()

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    def default(self):
        raise HTTPRedirect('/admin/dashboard')

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    @cherrypy.tools.jinja(filename='admin/dashboard.html')
    def dashboard(self):
        library_path = cherrypy.request.app.config.get('opmuse').get('library.path')

        stat = os.statvfs(os.path.realpath(library_path))

        disk = {
            'path': library_path,
            'free': stat.f_frsize * stat.f_bavail,
            'total': stat.f_frsize * stat.f_blocks
        }

        formats = (get_database().query(Track.format, func.sum(Track.duration),
                                        func.sum(Track.size), func.count(Track.format)).group_by(Track.format).all())

        stats = {
            'tracks': library_dao.get_track_count(),
            'invalid': library_dao.get_invalid_track_count(),
            'albums': library_dao.get_album_count(),
            'artists': library_dao.get_artist_count(),
            'track_paths': library_dao.get_track_path_count(),
            'duration': library_dao.get_track_duration(),
            'size': library_dao.get_track_size(),
            'scanning': cherrypy.request.library.scanning,
            'processed': cherrypy.request.library.processed,
            'files_found': cherrypy.request.library.files_found
        }

        return {
            'cache_size': cache.storage.size(),
            'disk': disk,
            'stats': stats,
            'formats': formats
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    @cherrypy.tools.jinja(filename='admin/bgtasks.html')
    def bgtasks(self):
        return {}

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    @cherrypy.tools.jinja(filename='admin/cache.html')
    def cache(self):
        values = []

        total_bytes = 0

        for key, item in cache.storage.values():
            bytes = total_size(item['value'])
            total_bytes += bytes
            values.append((key, bytes, type(item['value']), item['updated']))

        return {
            'values': values,
            'size': cache.storage.size(),
            'total_bytes': total_bytes
        }
