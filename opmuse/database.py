import cherrypy
from urllib.parse import urlparse
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool

Base = declarative_base()
Base.__table_args__ = ({'mysql_charset': 'utf8', 'mysql_engine': 'InnoDB'}, )


def get_type():
    config = cherrypy.tree.apps[''].config['opmuse']
    url = config['database.url']
    return urlparse(url).scheme


def get_engine():
    config = cherrypy.tree.apps[''].config['opmuse']
    url = config['database.url']
    echo = config['database.echo']
    return create_engine(url, echo=echo, poolclass=NullPool,
                                isolation_level="READ UNCOMMITTED")


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
        Base.metadata.create_all(self.engine)

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
