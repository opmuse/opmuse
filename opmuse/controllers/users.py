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

import cherrypy
from datetime import datetime, timedelta
from sqlalchemy.orm.exc import NoResultFound
from opmuse.database import get_database
from opmuse.security import User, Role
from opmuse.remotes import remotes
from opmuse.library import library_dao
from opmuse.search import search
from opmuse.controllers.dashboard import Dashboard


class Users:
    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='users/index.html')
    def default(self, *args):
        if len(args) == 1:
            raise cherrypy.InternalRedirect('/users/_user/%s' % args[0])

        users = (get_database().query(User).order_by(User.active.desc()).all())

        for user in users:
            remotes.update_user(user)

        return {
            'users': users,
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='users/user.html')
    def _user(self, login):
        try:
            user = (get_database().query(User)
                    .filter_by(login=login)
                    .order_by(User.login).one())
        except NoResultFound:
            raise cherrypy.NotFound()

        remotes.update_user(user)
        remotes_user = remotes.get_user(user)

        Dashboard.update_recent_tracks()

        recently_listeneds = Dashboard.get_recently_listeneds(user)

        now = datetime.now()

        def get_year(year):
            return ('%s' % year, self._get_top_artists(user.id, datetime(year, 1, 1), datetime(year, 12, 31)))

        top_artists_categories = [
            ('Overall', self._get_top_artists(user.id, None, None)),
            get_year(now.year - 1),
            get_year(now.year - 2),
            get_year(now.year - 3),
            get_year(now.year - 4),
            get_year(now.year - 5),
            ('This Month', self._get_top_artists(user.id, datetime(now.year, now.month, 1), None)),
        ]

        uploaded_albums = library_dao.get_albums_by_created_user(user.id)

        return {
            'user': user,
            'uploaded_albums': uploaded_albums,
            'top_artists_categories': top_artists_categories,
            'recently_listeneds': recently_listeneds,
            'remotes_user': remotes_user
        }

    def _get_top_artists(self, user_id, start_date, end_date):
        top_artists = []

        for artist_name, count in library_dao.get_listened_artist_name_count(user_id, start_date, end_date, limit=50):
            artists = search.query_artist(artist_name, exact=True)

            if len(artists) > 0:
                artist = artists[0]
            else:
                artist = None

            top_artists.append((artist, artist_name, count))

        return top_artists
