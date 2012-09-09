import cherrypy
from sqlalchemy import Column, Integer, ForeignKey, Boolean, or_, and_
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from sqlalchemy.orm.exc import NoResultFound
from opmuse.database import Base
from opmuse.who import User
from opmuse.library import Track, library_dao

class Queue(Base):
    __tablename__ = 'queues'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    track_id = Column(Integer, ForeignKey('tracks.id'))
    weight = Column(Integer, index = True)
    playing = Column(Boolean)
    played = Column(Boolean)

    user = relationship("User", backref=backref('users', order_by=id))
    track = relationship("Track", backref=backref('tracks', cascade="all,delete", order_by=id))

    def __init__(self, weight):
        self.weight = weight


class QueueDao:
    def get_next_track(self, user_id):
        database = cherrypy.request.database
        queue = next_queue = None
        try:
            queue = (database.query(Queue)
                .filter_by(user_id=user_id, playing=True)
                .order_by(Queue.weight).one())

            next_queue = (database.query(Queue)
                .filter_by(user_id=user_id)
                .filter(Queue.weight > queue.weight)
                .order_by(Queue.weight).first())
        except NoResultFound:
            pass

        if next_queue is None:
            next_queue = (database.query(Queue)
                .filter_by(user_id=user_id)
                .order_by(Queue.weight).first())

        if next_queue is None:
            return None

        next_queue.playing = True

        if queue is not None:
            queue.played = True
            queue.playing = False

        database.commit()

        return next_queue.track

    def get_queues(self, user_id):
        queues = (cherrypy.request.database.query(Queue)
            .filter_by(user_id=user_id).order_by(Queue.weight).all())

        return queues

    def clear(self):
        user_id = cherrypy.request.user.id
        cherrypy.request.database.query(Queue).filter_by(user_id=user_id).delete()

    def clear_played(self):
        user_id = cherrypy.request.user.id
        cherrypy.request.database.query(Queue).filter_by(user_id=user_id, played=True).delete()

    def add_track(self, slug):
        track = library_dao.get_track_by_slug(slug)

        user_id = cherrypy.request.user.id
        user = cherrypy.request.database.query(User).filter_by(id=user_id).one()

        weight = self.get_new_pos(user_id)

        queue = Queue(weight)
        queue.track = track
        queue.user = user

        cherrypy.request.database.add(queue)

    def remove_track(self, slug):
        user_id = cherrypy.request.user.id
        track = cherrypy.request.database.query(Track).filter_by(slug=slug).one()
        cherrypy.request.database.query(Queue).filter_by(user_id=user_id, track_id = track.id).delete()

    def add_album(self, slug):
        album = library_dao.get_album_by_slug(slug)

        user_id = cherrypy.request.user.id
        user = cherrypy.request.database.query(User).filter_by(id=user_id).one()

        weight = self.get_new_pos(user_id)

        for track in album.tracks:
            queue = Queue(weight)
            queue.track = track
            queue.user = user

            cherrypy.request.database.add(queue)

            weight += 1

    def get_new_pos(self, user_id):
        weight = (cherrypy.request.database.query(func.max(Queue.weight))
            .filter_by(user_id=user_id).scalar())

        if weight is None:
            weight = 0
        else:
            weight += 1

        return weight

queue_dao = QueueDao()

