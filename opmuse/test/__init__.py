import os
import cherrypy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from opmuse.boot import configure
from opmuse.database import get_raw_session
from opmuse.test.fixtures import run_fixtures


def setup_db(self):
    db_path = 'opmuse.db'

    if os.path.exists(db_path):
        os.remove(db_path)

    configure()

    cherrypy.tree.apps[''].config['opmuse']['database.url'] = 'sqlite:///./%s' % db_path

    self.session = get_raw_session(create_all = True)

    run_fixtures(self.session)


def teardown_db(self):
    self.session.close()
