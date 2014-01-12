# Copyright 2012-2013 Mattias Fliesberg
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
import re
import threading
from urllib.parse import urlparse
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool

Base = declarative_base()
Base.__table_args__ = ({'mysql_charset': 'utf8', 'mysql_engine': 'InnoDB'}, )


database_data = threading.local()


def get_database():
    if hasattr(cherrypy.request, 'database'):
        return cherrypy.request.database
    else:
        if hasattr(database_data, 'database'):
            return database_data.database


def get_database_type():
    config = cherrypy.tree.apps[''].config['opmuse']
    url = config['database.url']
    return re.sub(r'(\+[^+]+)?$', '', urlparse(url).scheme)


def get_engine(no_database=False):
    config = cherrypy.tree.apps[''].config['opmuse']
    url = config['database.url']

    if no_database:
        url = re.sub(r'/[^/]+$', '', url)

    return create_engine(url, echo=False, poolclass=NullPool, isolation_level="READ UNCOMMITTED")


def get_database_name():
    config = cherrypy.tree.apps[''].config['opmuse']
    url = config['database.url']

    match = re.search(r'/([^/]+)$', url)

    return match.group(1)


def get_raw_session(create_all = False):
    engine = get_engine()

    if create_all:
        Base.metadata.create_all(engine)

    return sessionmaker(bind=engine)()


def get_session():
    session = scoped_session(sessionmaker(autoflush=True,
                                          autocommit=False))
    cherrypy.engine.publish('bind', session)

    return session


class SqlAlchemyPlugin(cherrypy.process.plugins.SimplePlugin):

    def __init__(self, bus):
        cherrypy.process.plugins.SimplePlugin.__init__(self, bus)
        self.engine = None
        self.bus.subscribe("bind", self.bind)

    def start(self):
        self.engine = get_engine()

    start.priority = 100

    def bind(self, session):
        # this occurs in unit tests when the cherrypy plugin start event thingie
        # hasn't been triggered...
        if self.engine is None:
            engine = get_engine()
        else:
            engine = self.engine

        session.configure(bind=engine)

    def stop(self):
        if self.engine is not None:
            self.engine.dispose()
            self.engine = None


class SqlAlchemyTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.bind_session, priority=10)

        self.session = scoped_session(sessionmaker(autoflush=True,
                                                   autocommit=False))

    def _setup(self):
        cherrypy.Tool._setup(self)
        cherrypy.request.hooks.attach('on_end_request',
                                      self.commit_transaction,
                                      priority=80)

    def commit_transaction(self):
        cherrypy.request.database = None
        try:
            self.session.commit()
        except:
            self.session.rollback()
            raise
        finally:
            self.session.remove()

    def bind_session(self):
        cherrypy.engine.publish('bind', self.session)
        cherrypy.request.database = self.session
