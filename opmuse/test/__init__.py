import os
import cherrypy
import re
from os.path import join, abspath, dirname
from opmuse.boot import configure
from opmuse.database import get_raw_session
from opmuse.test.fixtures import run_fixtures

test_config_file = join(abspath(dirname(__file__)), '..', '..', 'config', 'opmuse.test.ini')


def remove_db():
    # we assume it's a sqlite dsn
    db_path = cherrypy.tree.apps[''].config['opmuse']['database.url'][10:]

    if os.path.exists(db_path):
        os.remove(db_path)


def setup_db(self):
    configure(config_file=test_config_file, environment='production')

    remove_db()

    self.session = get_raw_session(create_all = True)

    run_fixtures(self.session)


def teardown_db(self):
    self.session.close()


try:
    from cherrypy.test import helper

    class WebCase(helper.CPWebCase):
        @staticmethod
        def _opmuse_setup_server():
            configure(config_file=test_config_file, environment='production')

            remove_db()

            session = get_raw_session(create_all = True)
            run_fixtures(session)
            session.close()

        def assertHeaderMatches(self, key, pattern, msg=None):
            lowkey = key.lower()

            for k, v in self.headers:
                if k.lower() == lowkey:
                    if re.match(pattern, v):
                        return v

            if msg is None:
                msg = '%r pattern doesn\'t match any value of %r header' % (pattern, key)

            self._handlewebError(msg)

except ImportError:
    pass
