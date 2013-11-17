import argparse
from opmuse.boot import configure

parser = argparse.ArgumentParser(description='Do common tasks for opmuse.')


def command_database(action=None):
    if action == "update":
        from opmuse.database import Base, get_engine
        Base.metadata.create_all(get_engine())
    else:
        parser.error('Needs to provide a valid action (update).')


def main():
    parser.add_argument('command', choices=('database', ), help='Command to run.')
    parser.add_argument('additional', nargs='*', help='Additional arguments.')

    args = parser.parse_args()

    configure()

    globals()["command_%s" % args.command](*args.additional)


if __name__ == "__main__":
    main()
