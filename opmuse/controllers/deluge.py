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
from opmuse.deluge import deluge_dao, deluge, Torrent
from opmuse.library import library_dao
from opmuse.bgtask import NonUniqueQueueError
from opmuse.database import get_database
from opmuse.cache import cache


def log(msg, traceback=False):
    cherrypy.log(msg, context='controllers.deluge', traceback=traceback)


class Deluge:
    UPDATE_TORRENTS_KEY = "update_torrents"
    UPDATE_TORRENTS_KEY_DONE = "update_torrents_done"
    UPDATE_TORRENTS_AGE = 60 * 5

    @staticmethod
    def _update_torrents():
        deluge.connect()
        deluge.update_torrents()
        cache.keep(Deluge.UPDATE_TORRENTS_KEY_DONE)

    @staticmethod
    def _import_torrent(torrent_id):
        deluge_dao.update_import_status(torrent_id, 'importing')

        try:
            deluge.connect()
            torrent_files = deluge.import_torrent(torrent_id)

            for torrent_file in torrent_files:
                # update modified time to now, we don't want the one from deluge
                os.utime(torrent_file, None)

            tracks, messages = library_dao.add_files(
                torrent_files, move=True, remove_dirs=True
            )

            deluge_dao.update_import_status(torrent_id, 'imported')
        except Exception:
            log("Failed to import torrent", traceback=True)
            deluge_dao.update_import_status(torrent_id, 'failed')

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True, roles=['admin'])
    @cherrypy.tools.jinja(filename='deluge/index.html')
    def default(self, filter=None):
        config = cherrypy.tree.apps[''].config['opmuse']

        if 'deluge.host' not in config:
            raise cherrypy.NotFound()

        query = get_database().query(Torrent).order_by(Torrent.added.desc())

        if filter == "importable":
            query = query.filter(Torrent.importable)
        else:
            filter = "nothing"

        torrents = query.all()

        deluge_host = config['deluge.host']
        deluge_port = config['deluge.port']

        if cache.needs_update(Deluge.UPDATE_TORRENTS_KEY, age=Deluge.UPDATE_TORRENTS_AGE):
            cache.keep(Deluge.UPDATE_TORRENTS_KEY)

            try:
                cherrypy.engine.bgtask.put_unique(Deluge._update_torrents, 20)
            except NonUniqueQueueError:
                pass

        deluge_updated = cache.storage.get_updated(Deluge.UPDATE_TORRENTS_KEY_DONE)

        return {
            'deluge_host': deluge_host,
            'deluge_port': deluge_port,
            'filter': filter,
            'deluge_updated': deluge_updated,
            'torrents': torrents
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
