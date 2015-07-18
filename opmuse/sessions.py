import cherrypy
import pickle
from cherrypy.lib.sessions import Session as cpSession
from sqlalchemy import Column, Integer, DateTime, String, BLOB, func
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.dialects import mysql
from opmuse.database import Base, get_database, get_session


class Session(Base):
    __tablename__ = 'sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    sess_id = Column(String(40), index=True, unique=True)
    data = Column(BLOB().with_variant(mysql.LONGBLOB(), 'mysql'))
    expiration_time = Column(DateTime, index=True)


class SqlalchemySession(cpSession):
    """
    Stores sessions in Sqlalchemy entity.

    Should only be used for development, doesn't support locking.
    """

    pickle_protocol = pickle.HIGHEST_PROTOCOL

    def __init__(self, id=None, **kwargs):
        cpSession.__init__(self, id, **kwargs)

    def _exists(self):
        try:
            return (get_database().query(func.count(Session.id))
                    .filter(Session.sess_id == self.id).scalar())
        except NoResultFound:
            return 0

    def _load(self):
        try:
            session = get_database().query(Session).filter(Session.sess_id == self.id).one()
        except NoResultFound:
            return None

        data = pickle.loads(session.data)

        return data, session.expiration_time

    def _save(self, expiration_time):
        data = pickle.dumps(self._data, self.pickle_protocol)

        if self._exists():
            (get_database().query(Session).filter(Session.sess_id == self.id)
                                          .update({'data': data, 'expiration_time': expiration_time}))
        else:
            params = {'sess_id': self.id, 'data': data, 'expiration_time': expiration_time}
            get_database().execute(Session.__table__.insert(), params)

        get_database().commit()

    def _delete(self):
        get_database().query(Session).filter(Session.sess_id == self.id).delete()

    def acquire_lock(self):
        self.locked = True

    def release_lock(self):
        self.locked = False

    def clean_up(self):
        # uses get_session() because this runs in a background thread and needs to
        # setup its own connection
        session = get_session()
        session.query(Session).filter(Session.expiration_time < self.now()).delete()
        session.commit()


cherrypy.lib.sessions.SqlalchemySession = SqlalchemySession
