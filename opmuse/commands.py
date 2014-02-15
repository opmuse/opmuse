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

import os
import shutil
import argparse
import subprocess
import sys
from sqlalchemy.exc import ProgrammingError
from alembic.config import Config
from alembic import command
from opmuse.boot import configure
from opmuse.database import Base, get_engine, get_database_name, get_database_type
from opmuse.library import TrackPath, Track, Artist, Album
from opmuse.queues import Queue
from opmuse.cache import CacheObject
from opmuse.search import search

root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
parser = argparse.ArgumentParser(description='Do common tasks for opmuse.')


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
        if not os.path.exists(search.index_dir):
            return

        for file in os.listdir(search.index_dir):
            if file[0:1] == ".":
                continue

            path = os.path.join(search.index_dir, file)

            if os.path.isfile(path):
                os.unlink(path)
            else:
                shutil.rmtree(path)
    else:
        parser.error('Needs to provide a valid action (drop).')


def command_cherrypy(*args):
    try:
        process = subprocess.Popen([
            sys.executable, 'opmuse/boot.py'
        ] + list(args), cwd=root_path)

        process.wait()
    except KeyboardInterrupt:
        process.terminate()
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
    elif action == "update":
        try:
            command.upgrade(alembic_config, "head")
        except ProgrammingError as e:
            parser.error('Error occured while updating database: %s' % e)
    elif action == "drop":
        if database_type == "sqlite":
            parser.error('Dropping is unsupported for sqlite.')

        engine = get_engine(no_database=True)
        engine.execute("DROP DATABASE IF EXISTS %s" % get_database_name())
        command_whoosh("drop")
    elif action == "fixtures":
        from opmuse.fixtures import run_fixtures
        run_fixtures()
    elif action == "reset":
        engine = get_engine()
        engine.execute(Queue.__table__.delete())
        engine.execute(TrackPath.__table__.delete())
        engine.execute(Track.__table__.delete())
        engine.execute(Album.__table__.delete())
        engine.execute(Artist.__table__.delete())
        engine.execute(CacheObject.__table__.delete())
        command_whoosh("drop")
    else:
        parser.error('Needs to provide a valid action (create, update, drop, fixtures, reset).')


def main():
    parser.add_argument('command', choices=('database', 'cherrypy', 'whoosh', 'less', 'jinja'), help='Command to run.')
    parser.add_argument('additional', nargs='*', help='Additional arguments.')

    args = parser.parse_args()

    configure()

    globals()["command_%s" % args.command](*args.additional)


if __name__ == "__main__":
    main()
