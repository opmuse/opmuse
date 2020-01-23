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
import os
from sqlalchemy import or_
from opmuse.utils import HTTPRedirect
from opmuse.deluge import deluge_dao, deluge, Torrent, DelugeBackgroundTaskCron
from opmuse.library import library_dao
from opmuse.bgtask import NonUniqueQueueError
from opmuse.database import get_database
from opmuse.cache import cache
from opmuse.whatcd import whatcd, WhatcdError


def log(msg, traceback=False):
    cherrypy.log(msg, context='controllers.deluge', traceback=traceback)


class Deluge:
    @staticmethod
    def _import_torrent(torrent_id):
        deluge_dao.update_import_status('importing', None, torrent_id)

        try:
            deluge.connect()
            torrent_files = deluge.import_torrent(torrent_id)

            for torrent_file in torrent_files:
                # update modified time to now, we don't want the one from deluge
                os.utime(torrent_file, None)

            tracks, messages = library_dao.add_files(
                torrent_files, move=True, remove_dirs=True
            )

            deluge_dao.update_import_status('imported', None, torrent_id)
        except Exception as e:
            log("Failed to import torrent", traceback=True)
            deluge_dao.update_import_status('failed', str(e), torrent_id)

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    @cherrypy.tools.jinja(filename='torrents/deluge/index.html')
    def default(self, filter="importable"):
        config = cherrypy.tree.apps[''].config['opmuse']

        if 'deluge.host' not in config:
            raise cherrypy.NotFound()

        pending_query = get_database().query(Torrent).order_by(Torrent.added.desc())

        if filter == "importable":
            pending_query = pending_query.filter(Torrent.importable)
        else:
            filter = "nothing"

        pending_torrents = pending_query.all()

        import_torrents = (get_database().query(Torrent).order_by(Torrent.import_date.desc())
                            .filter(or_(Torrent.import_status == 'importing', Torrent.import_status == "imported"))).all()

        deluge_host = config['deluge.host']
        deluge_port = config['deluge.port']

        deluge_updated = cache.storage.get_updated(DelugeBackgroundTaskCron.UPDATE_TORRENTS_KEY_DONE)

        return {
            'deluge_host': deluge_host,
            'deluge_port': deluge_port,
            'filter': filter,
            'deluge_updated': deluge_updated,
            'pending_torrents': pending_torrents,
            'import_torrents': import_torrents
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    @cherrypy.tools.json_out()
    def test_connectivity(self):
        try:
            connected = deluge.connect(timeout=5)
        except:
            connected = False

        return {'connected': connected}

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    @cherrypy.tools.json_out()
    def import_torrent(self, torrent_id):
        status = 'importing'

        try:
            cherrypy.engine.bgtask.put_unique(Deluge._import_torrent, 25, torrent_id)
        except NonUniqueQueueError:
            pass

        return {'status': status}

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    @cherrypy.tools.json_out()
    def mark_all_as_done(self):
        deluge_dao.update_import_status('done')

        return {}


class Search:
    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    @cherrypy.tools.jinja(filename='torrents/search/index.html')
    def default(self, query=None):
        error = None

        if query is not None:
            torrents = []

            try:
                for torrent in whatcd.search(query):
                    torrents.append(torrent)

            except WhatcdError as e:
                error = str(e)
        else:
            torrents = None

        return {"query": query, "torrents": torrents, "error": error}


class Torrents:
    deluge = Deluge()
    search = Search()

    @cherrypy.expose
    def default(self):
        raise HTTPRedirect('/torrents/deluge')
