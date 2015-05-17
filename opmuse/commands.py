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
import pwd
import grp
import shutil
import argparse
import subprocess
import sys
import string
import random
import cherrypy
import signal
from sqlalchemy.exc import ProgrammingError
from alembic.config import Config
from alembic import command
from opmuse.boot import configure
from opmuse.database import Base, get_engine, get_database_name, get_database_type, get_raw_session
from opmuse.library import TrackPath, Track, Artist, Album, UserAndAlbum, ListenedTrack
from opmuse.security import User, Role, hash_password
from opmuse.queues import Queue
from opmuse.cache import CacheObject
from opmuse.search import search, write_handlers

root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
parser = argparse.ArgumentParser(description='Do common tasks for opmuse.')


def get_env_var(var):
    """
    Extracts env var from opmuse "default" file.

    If you know of any better way to do this please do tell.
    """

    if not os.path.exists("/etc/default/opmuse"):
        return None

    args = ["/bin/sh", "-c", ". /etc/default/opmuse; echo $%s" % var]

    value = subprocess.check_output(args, env={}).strip().decode('utf8')

    if value == "":
        value = None

    return value


def drop_privileges():
    if os.getuid() == 0:
        user = get_env_var("USER")

        if user is None:
            return False

        group = get_env_var("GROUP")

        uid = pwd.getpwnam(user).pw_uid

        os.setgroups([])

        if group is not None:
            gid = grp.getgrnam(group).gr_gid
            os.setgid(gid)

        os.setuid(uid)

        os.umask(0o027)

        return True
    else:
        return False


def command_jinja(action=None, path=None):
    if action == "compile":
        if path is None:
            parser.error('Needs to provide a path.')

        from opmuse.jinja import get_jinja_env
        jinja_env = get_jinja_env()

        if os.path.exists(path):
            shutil.rmtree(path)

        jinja_env.compile_templates(path, zip=None)
    else:
        parser.error('Needs to provide a valid action (compile).')


def command_less():
    from opmuse.utils import less_compiler
    less_compiler.compile()
    print("compiled main.css")


def command_whoosh(action=None):
    if action == "drop":
        write_handlers.drop_indexes()
    elif action == "reindex":
        # drop root privileges if root, obviously the index needs to be
        # created with the same permissions as the app is running with.
        drop_privileges()

        from opmuse.library import library_dao
        from opmuse.database import database_data, get_session

        database_data.database = get_session()

        write_handlers.init_indexes()

        for artist in library_dao.get_artists():
            search.add_artist(artist)

        for album in library_dao.get_albums():
            search.add_album(album)

        for track in library_dao.get_tracks():
            search.add_track(track)

        write_handlers.commit()

        database_data.database.remove()
        database_data.database = None
    else:
        parser.error('Needs to provide a valid action (drop, reindex).')


def command_cherrypy(*args):
    def preexec_fn():
        # ignore SIGINT, e.g. KeyboardInterrupt
        signal.signal(signal.SIGINT, signal.SIG_IGN)

    try:
        process = subprocess.Popen([
            sys.executable, 'opmuse/boot.py'
        ] + list(args), cwd=root_path, preexec_fn=preexec_fn)

        process.wait()
    except KeyboardInterrupt:
        try:
            process.terminate()
            process.wait()
        except KeyboardInterrupt:
            process.send_signal(signal.SIGKILL)
            process.wait()


def command_database(action=None):
    config_path = os.path.join(root_path, "alembic.ini")

    if not os.path.exists(config_path):
        config_path = "/usr/share/opmuse/alembic.ini"

    alembic_config = Config(config_path)

    database_type = get_database_type()

    if action == "create":
        if database_type == "mysql":
            try:
                engine = get_engine(no_database=True)
                engine.execute("CREATE DATABASE IF NOT EXISTS %s" % get_database_name())
            except ProgrammingError as e:
                parser.error('Error occured while creating database: %s' % e)

        engine = get_engine()
        Base.metadata.create_all(engine)
        command.stamp(alembic_config, "head")
    # TODO rename to upgrade
    elif action == "update":
        try:
            command.upgrade(alembic_config, "head")
        except ProgrammingError as e:
            parser.error('Error occured while updating database: %s' % e)
    elif action == "downgrade":
        try:
            command.downgrade(alembic_config, "-1")
        except ProgrammingError as e:
            parser.error('Error occured while downgrading database: %s' % e)
    elif action == "drop":
        if database_type == "sqlite":
            parser.error('Dropping is unsupported for sqlite.')

        engine = get_engine(no_database=True)
        engine.execute("DROP DATABASE IF EXISTS %s" % get_database_name())
        command_whoosh("drop")
    elif action == "fixtures":
        from opmuse.test.fixtures import run_fixtures
        run_fixtures()
    elif action == "reset":
        engine = get_engine()
        engine.execute(Queue.__table__.delete())
        engine.execute(TrackPath.__table__.delete())
        engine.execute(Track.__table__.delete())
        engine.execute(ListenedTrack.__table__.delete())
        engine.execute(UserAndAlbum.__table__.delete())
        engine.execute(Album.__table__.delete())
        engine.execute(Artist.__table__.delete())
        engine.execute(CacheObject.__table__.delete())
        command_whoosh("drop")
    else:
        parser.error('Needs to provide a valid action (create, update, downgrade, drop, fixtures, reset).')


def command_user(action=None, *args):
    if action == "add_role":
        if len(args) >= 1:
            name = args[0]

            database = get_raw_session()

            role = Role(name)

            database.add(role)
            database.commit()
        else:
            parser.error('Needs to provide a name.')
    elif action == "add":
        if len(args) >= 3:
            login = args[0]
            password = args[1]
            mail = args[2]

            if len(args) >= 4:
                role = args[3]
            else:
                role = None

            database = get_raw_session()

            salt = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(64))

            user = User(login, hash_password(password, salt), mail, salt)

            database.add(user)

            if role is not None:
                role = database.query(Role).filter(Role.name == role).one()
                role.users.append(user)

            database.commit()
        else:
            parser.error('Needs to provide a login, password, mail and optionally role.')
    else:
        parser.error('Needs to provide a valid action (add, add_role).')


def main():
    parser.add_argument('command', choices=('database', 'cherrypy', 'whoosh', 'less', 'jinja', 'user'),
                        help='Command to run.')
    parser.add_argument('additional', nargs='*', help='Additional arguments.')

    args = parser.parse_args()

    configure()

    cmd = os.path.basename(sys.argv[0])

    if cmd == "opmuse-console":
        cherrypy.config.update({
            'environment': 'production'
        })

    globals()["command_%s" % args.command](*args.additional)


if __name__ == "__main__":
    main()
