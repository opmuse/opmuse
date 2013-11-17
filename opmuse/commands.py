import os
import argparse
import subprocess
from opmuse.boot import configure
from opmuse.database import Base, get_engine
from alembic.config import Config
from alembic import command

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
    if action == "update":
        Base.metadata.create_all(get_engine())
        alembic_config = Config(os.path.join("alembic.ini"))
        command.stamp(alembic_config, "head")
    else:
        parser.error('Needs to provide a valid action (update).')


def main():
    parser.add_argument('command', choices=('database', 'cherrypy'), help='Command to run.')
    parser.add_argument('additional', nargs='*', help='Additional arguments.')

    args = parser.parse_args()

    configure()

    globals()["command_%s" % args.command](*args.additional)


if __name__ == "__main__":
    main()
