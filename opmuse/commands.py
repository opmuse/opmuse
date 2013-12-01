import os
import argparse
import subprocess
from sqlalchemy.exc import ProgrammingError
from alembic.config import Config
from alembic import command
from opmuse.boot import configure
from opmuse.database import Base, get_engine, get_database_name, get_database_type

root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
parser = argparse.ArgumentParser(description='Do common tasks for opmuse.')


def command_cherrypy(*args):
    try:
        process = subprocess.Popen([
            'python', 'opmuse/boot.py'
        ] + list(args), cwd=root_path)

        process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait()


def command_database(action=None):
    alembic_config = Config(os.path.join("alembic.ini"))
    database_type = get_database_type()

    if action == "create":
        if database_type == "mysql":
            try:
                engine = get_engine(no_database=True)
                engine.execute("CREATE DATABASE %s" % get_database_name())
            except ProgrammingError as e:
                print('Error occured while creating database: %s' % e)
                return

        engine = get_engine()
        Base.metadata.create_all(engine)
        command.stamp(alembic_config, "head")
    elif action == "update":
        try:
            command.upgrade(alembic_config, "head")
        except ProgrammingError as e:
            print('Error occured while updating database: %s' % e)
    elif action == "drop":
        if database_type == "sqlite":
            parser.error('Dropping is unsupported for sqlite.')

        engine = get_engine(no_database=True)
        engine.execute("DROP DATABASE IF EXISTS %s" % get_database_name())
    elif action == "fixtures":
        from opmuse.fixtures import run_fixtures
        run_fixtures()
    else:
        parser.error('Needs to provide a valid action (create, update, drop, fixtures).')


def main():
    parser.add_argument('command', choices=('database', 'cherrypy'), help='Command to run.')
    parser.add_argument('additional', nargs='*', help='Additional arguments.')

    args = parser.parse_args()

    configure()

    globals()["command_%s" % args.command](*args.additional)


if __name__ == "__main__":
    main()
