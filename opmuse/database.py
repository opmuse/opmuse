import cherrypy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from pydispatch import dispatcher

Base = declarative_base()
Base.__table_args__ = {'mysql_charset': 'utf8', 'mysql_engine': 'InnoDB'}

def get_session():
    url = cherrypy.config['opmuse']['database.url']
    session = sessionmaker(bind=create_engine(url))()
    dispatcher.send(signal='start_db_session', sender=session)
    return session

class SqlAlchemyPlugin(cherrypy.process.plugins.SimplePlugin):

    def __init__(self, bus):
        cherrypy.process.plugins.SimplePlugin.__init__(self, bus)
        self.engine = None
        self.bus.subscribe("bind", self.bind)

    def start(self):
        url = cherrypy.config['opmuse']['database.url']
        echo = cherrypy.config['opmuse']['database.echo']
        self.engine = create_engine(url, echo=echo,
                                    isolation_level="READ UNCOMMITTED")
        Base.metadata.create_all(self.engine)

    # TODO use decorator?
    start.priority = 10

    def bind(self, session):
        session.configure(bind=self.engine)

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

