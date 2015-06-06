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
import logging
import datetime
import tempfile
import shutil
import subprocess
from subprocess import CalledProcessError
from deluge_client import DelugeRPCClient
from opmuse.library import Library
from opmuse.database import Base, get_session, get_database
from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, Numeric
from sqlalchemy.ext.hybrid import hybrid_property


def debug(msg, traceback=False):
    log(msg, traceback=traceback, severity=logging.DEBUG)


def log(msg, traceback=False, severity=logging.INFO):
    cherrypy.log.error(msg, context='deluge', traceback=traceback, severity=severity)


class Torrent(Base):
    __tablename__ = 'torrents'

    id = Column(Integer, primary_key=True, autoincrement=True)
    torrent_id = Column(String(40), index=True, unique=True)
    name = Column(String(255))
    has_supported_files = Column(Boolean, default=False)
    added = Column(DateTime, index=True)
    size = Column(BigInteger)
    paused = Column(Boolean, default=False, index=True)
    finished = Column(Boolean, default=False, index=True)
    progress = Column(Numeric(precision=4, scale=1, asdecimal=True))
    import_status = Column(String(128), default='', nullable=False)

    @hybrid_property
    def importable(self):
        return (self.has_supported_files & self.finished &
                (self.import_status != "importing") & (self.import_status != "imported") &
                (self.import_status != "done"))


class Deluge:
    def _mkdtemp(self):
        cache_path = cherrypy.config['opmuse'].get('cache.path')
        dir = os.path.join(cache_path, 'deluge')

        if not os.path.exists(dir):
            os.mkdir(dir)

        return tempfile.mkdtemp(dir=dir)

    def connect(self, timeout=20):
        config = cherrypy.tree.apps[''].config['opmuse']

        host = config['deluge.host']
        port = config['deluge.port']
        user = config['deluge.user']
        password = config['deluge.password']

        DelugeRPCClient.timeout = timeout
        self.client = DelugeRPCClient(host, port, user, password)
        self.client.connect()

        return self.client.connected

    def update_torrents(self):
        torrents = self.client.call('core.get_torrents_status', {},
                                    ['name', 'files', 'save_path', 'time_added',
                                     'total_size', 'paused', 'is_finished', 'progress'])

        all_torrents = set()

        for torrent_id, in get_database().query(Torrent.torrent_id).all():
            all_torrents.add(torrent_id)

        for torrent_id, data in torrents.items():
            torrent_id = torrent_id.decode('utf-8')

            if torrent_id in all_torrents:
                all_torrents.remove(torrent_id)
                torrent = get_database().query(Torrent).filter(Torrent.torrent_id == torrent_id).one()
            else:
                torrent = Torrent()

            for file in data[b'files']:
                if Library.is_supported(file[b'path']):
                    has_supported_files = True
                    break
            else:
                has_supported_files = False

            torrent.torrent_id = torrent_id
            torrent.name = data[b'name'].decode('utf-8')
            torrent.has_supported_files = has_supported_files
            torrent.added = datetime.datetime.fromtimestamp(data[b'time_added'])
            torrent.size = data[b'total_size']
            torrent.paused = data[b'paused']
            torrent.finished = data[b'is_finished']
            torrent.progress = data[b'progress']

            get_database().add(torrent)
            get_database().commit()

        if len(all_torrents) > 0:
            (get_database().query(Torrent).filter(Torrent.torrent_id.in_(all_torrents))
                .delete(synchronize_session='fetch'))

        get_database().commit()

    def import_torrent(self, torrent_id):
        config = cherrypy.tree.apps[''].config['opmuse']
        ssh_host = config['deluge.ssh_host']

        if ssh_host is None:
            raise Exception('You need to set deluge.ssh_host')

        debug('fetching torrent %s info' % torrent_id)
        torrent = self.client.call('core.get_torrent_status', torrent_id, [])

        filelist_fd, filelist_path = tempfile.mkstemp()

        files = []

        tempdir = self._mkdtemp().encode()

        with os.fdopen(filelist_fd, 'bw') as f:
            for file in torrent[b'files']:
                path = os.path.join(torrent[b'save_path'], file[b'path'])
                f.write(path + b"\n")
                files.append(os.path.join(tempdir, path[1:]))

        try:
            debug('rsync torrent %s from %s' % (torrent_id, ssh_host))
            output = subprocess.check_output([
                'rsync',
                '-a',
                '-e', 'ssh -oBatchMode=yes -oVisualHostKey=no',
                '--files-from=%s' % filelist_path,
                '%s:/' % ssh_host,
                tempdir
            ], stderr=subprocess.STDOUT)
        except CalledProcessError as error:
            log('Failed to rsync', traceback=True)
            shutil.rmtree(tempdir)
            raise Exception(error.output.decode())
        except Exception:
            log('Failed to rsync', traceback=True)
            shutil.rmtree(tempdir)
            raise
        finally:
            os.remove(filelist_path)

        debug('done rsyncing torrent %s' % torrent_id)

        return files


deluge = Deluge()


class DelugeDao:
    def update_import_status(self, status, torrent_id=None):
        query = get_database().query(Torrent)

        if torrent_id is not None:
            query = query.filter(Torrent.torrent_id == torrent_id)

        query.update({'import_status': status[0:128]})

        get_database().commit()

    def get_torrents(self):
        return get_database().query(Torrent).order_by(Torrent.added.desc()).all()


deluge_dao = DelugeDao()
