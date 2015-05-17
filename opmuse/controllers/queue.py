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
from opmuse.queues import queue_dao


class Queue:
    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='queue/player.html')
    def player(self):
        user = cherrypy.request.user
        queues, queue_info = queue_dao.get_queues(user.id)
        queue_current_track = queue_dao.get_current_track(user.id)

        return {
            'queues': queues,
            'queue_info': queue_info,
            'queue_current_track': queue_current_track
        }

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    @cherrypy.tools.authenticated(needs_auth=True)
    def update(self):
        queues = cherrypy.request.json['queues']

        updates = []

        for index, queue_id in enumerate(queues):
            updates.append((queue_id, {'index': index}))

        queue_dao.update_queues(updates)

        return {}

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='queue/cover.html')
    def cover(self):
        user = cherrypy.request.user
        queue_current_track = queue_dao.get_current_track(user.id)

        return {
            'queue_current_track': queue_current_track
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='queue/list.html')
    def list(self):
        user = cherrypy.request.user
        queues, queue_info = queue_dao.get_queues(user.id)
        queue_current_track = queue_dao.get_current_track(user.id)

        return {
            'queues': queues,
            'queue_info': queue_info,
            'queue_current_track': queue_current_track
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    def add_album(self, id):
        queue_dao.add_album_tracks(id)

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    def add(self, ids):
        queue_dao.add_tracks(ids.split(','))

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    def shuffle(self):
        queue_dao.shuffle()

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    def remove(self, ids):
        queue_dao.remove(ids.split(','))

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    def clear(self, what=None):
        if what is not None and what == 'played':
            queue_dao.clear_played()
        else:
            queue_dao.clear()

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    def stop(self):
        queue_dao.reset_current()
