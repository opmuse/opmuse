import cherrypy
import math
from sqlalchemy import Column, Integer, ForeignKey, Boolean, or_, and_
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from sqlalchemy.orm.exc import NoResultFound
from opmuse.database import Base
from opmuse.security import User
from opmuse.library import Track, Artist, Album, library_dao
from opmuse.ws import ws


class Queue(Base):
    __tablename__ = 'queues'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    track_id = Column(Integer, ForeignKey('tracks.id'))
    weight = Column(Integer, index = True)
    current_seconds = Column(Integer)
    current = Column(Boolean)
    played = Column(Boolean)

    user = relationship("User", backref=backref('users', order_by=id))
    track = relationship("Track", backref=backref('tracks', cascade="all,delete", order_by=id))

    def __init__(self, weight):
        self.weight = weight


class QueueEvents:
    def __init__(self):
        cherrypy.engine.subscribe('transcoding.start', self.transcoding_start)
        cherrypy.engine.subscribe('transcoding.progress', self.transcoding_progress)
        cherrypy.engine.subscribe('transcoding.end', self.transcoding_end)
        cherrypy.engine.subscribe('transcoding.done', self.transcoding_done)
        cherrypy.engine.subscribe('queue.next', self.queue_next)

        ws.on('queue.open', self.queue_open)

    def queue_next(self, next):
        if next is None:
            ws.emit('queue.next.none')

    def queue_open(self, ws_user):
        track = ws_user.get('queue.current_track')
        progress = ws_user.get('queue.current_progress')

        if track is not None:
            ws.emit('queue.current_track', track, ws_user = ws_user)

        if progress is not None:
            ws.emit('queue.current_progress', progress, ws_user = ws_user)

    def transcoding_progress(self, progress, track):
        ws_user = ws.get_ws_user()
        ws_user.set('queue.current_progress', progress)

        ws.emit('queue.progress', progress, self.serialize_track(track))

        cherrypy.request.queue_progress = progress

    def transcoding_start(self, track):
        track = self.serialize_track(track)

        ws_user = ws.get_ws_user()
        ws_user.set('queue.current_track', track)

        ws.emit('queue.start', track)

    def transcoding_done(self, track):
        if hasattr(cherrypy.request, 'queue_current') and cherrypy.request.queue_current is not None:
            queue_current = cherrypy.request.queue_current

            queue_dao.update_queue(queue_current.id, current_seconds = None, played = True)

            # this is to avoid transcoding_end from firing
            cherrypy.request.queue_current = None

            ws_user = ws.get_ws_user()
            ws_user.set('queue.current_track', None)
            ws_user.set('queue.current_progress', None)

    def transcoding_end(self, track):
        if (hasattr(cherrypy.request, 'queue_progress') and cherrypy.request.queue_progress is not None and
            hasattr(cherrypy.request, 'queue_current') and cherrypy.request.queue_current is not None):
            queue_current = cherrypy.request.queue_current
            progress = cherrypy.request.queue_progress

            current_seconds = math.floor(progress['seconds'] - progress['seconds_ahead'])

            queue_dao.update_queue(queue_current.id, current_seconds = current_seconds)

    def serialize_track(self, track):
        return {
            'album': {
                'name': track.album.name
            },
            'artist': {
                'name': track.artist.name,
            },
            'name': track.name,
            'duration': track.duration,
        }


class QueueDao:
    def update_queue(self, id, **kwargs):
        cherrypy.request.database.query(Queue).filter_by(id=id).update(kwargs)
        cherrypy.request.database.commit()

    def get_next(self, user_id):
        database = cherrypy.request.database
        current_queue = next_queue = None

        try:
            current_queue = (database.query(Queue)
                     .filter_by(user_id=user_id, current=True)
                     .order_by(Queue.weight).one())

            if current_queue.current_seconds is not None:
                next_queue = current_queue
                current_queue = None
        except NoResultFound:
            pass

        if next_queue is None:
            if current_queue is not None:
                next_queue = (database.query(Queue)
                              .filter_by(user_id=user_id)
                              .filter(Queue.weight > current_queue.weight)
                              .order_by(Queue.weight).first())
            else:
                database.query(Queue).filter_by(user_id=user_id).update({'played': None})
                next_queue = (database.query(Queue)
                              .filter_by(user_id=user_id)
                              .order_by(Queue.weight).first())

        if current_queue is not None:
            current_queue.current = False

        if next_queue is not None:
            next_queue.current = True

        database.commit()

        cherrypy.request.queue_current = next_queue

        cherrypy.engine.publish('queue.next', next=next_queue)

        return next_queue

    def get_queues(self, user_id):
        queues = []

        album = None
        artist = None
        track = None

        current_queues = []

        for queue in cherrypy.request.database.query(Queue).filter_by(user_id=user_id).order_by(Queue.weight).all():

            if (album is not None and album.id != queue.track.album.id or
                artist is not None and artist.id != queue.track.artist.id or
                track is not None and track.disc != queue.track.disc):
                queues.append(current_queues)
                current_queues = []

            current_queues.append(queue)

            album = queue.track.album
            artist = queue.track.artist
            track = queue.track

        if len(current_queues) > 0:
            queues.append(current_queues)

        return queues

    def clear(self):
        user_id = cherrypy.request.user.id
        cherrypy.request.database.query(Queue).filter_by(user_id=user_id).delete()
        cherrypy.request.database.commit()
        ws.emit('queue.update')

    def clear_played(self):
        user_id = cherrypy.request.user.id
        cherrypy.request.database.query(Queue).filter_by(user_id=user_id, played=True).delete()
        cherrypy.request.database.commit()
        ws.emit('queue.update')

    def add_track(self, id):
        track = cherrypy.request.database.query(Track).filter_by(id=id).one()

        user_id = cherrypy.request.user.id
        user = cherrypy.request.database.query(User).filter_by(id=user_id).one()

        weight = self.get_new_pos(user_id)

        queue = Queue(weight)
        queue.track = track
        queue.user = user

        cherrypy.request.database.add(queue)
        cherrypy.request.database.commit()
        ws.emit('queue.update')

    def remove_track(self, id):
        user_id = cherrypy.request.user.id
        cherrypy.request.database.query(Queue).filter_by(user_id=user_id, track_id = id).delete()
        cherrypy.request.database.commit()
        ws.emit('queue.update')

    def get_new_pos(self, user_id):
        weight = cherrypy.request.database.query(func.max(Queue.weight)).filter_by(user_id=user_id).scalar()

        if weight is None:
            weight = 0
        else:
            weight += 1

        return weight

queue_dao = QueueDao()
queue_events = QueueEvents()
