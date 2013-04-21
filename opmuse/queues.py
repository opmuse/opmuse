import cherrypy
import math
from sqlalchemy import Column, Integer, ForeignKey, Boolean, or_, and_
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from sqlalchemy.orm.exc import NoResultFound
from opmuse.database import Base, get_database
from opmuse.security import User
from opmuse.library import Track, Artist, Album, library_dao
from opmuse.ws import ws


class Queue(Base):
    __tablename__ = 'queues'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    track_id = Column(Integer, ForeignKey('tracks.id'))
    index = Column(Integer, index = True)
    current_seconds = Column(Integer)
    current = Column(Boolean)
    played = Column(Boolean)

    user = relationship("User", backref=backref('users', order_by=id))
    track = relationship("Track", backref=backref('tracks', cascade="all,delete", order_by=id))

    def __init__(self, index):
        self.index = index


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
        if hasattr(cherrypy.request, 'queue_current_id') and cherrypy.request.queue_current_id is not None:
            queue_current_id = cherrypy.request.queue_current_id
            queue_dao.update_queue(queue_current_id, current_seconds = None)

        track = self.serialize_track(track)

        ws_user = ws.get_ws_user()
        ws_user.set('queue.current_track', track)

        ws.emit('queue.start', track)

    def transcoding_done(self, track):
        if hasattr(cherrypy.request, 'queue_current_id') and cherrypy.request.queue_current_id is not None:
            queue_current_id = cherrypy.request.queue_current_id

            queue_dao.update_queue(queue_current_id, played = True)

            # this is to avoid transcoding_end from firing
            cherrypy.request.queue_current_id = None

            ws_user = ws.get_ws_user()
            ws_user.set('queue.current_track', None)
            ws_user.set('queue.current_progress', None)

    def transcoding_end(self, track):
        if (hasattr(cherrypy.request, 'queue_progress') and cherrypy.request.queue_progress is not None and
            hasattr(cherrypy.request, 'queue_current_id') and cherrypy.request.queue_current_id is not None):
            queue_current = queue_dao.get_queue(cherrypy.request.queue_current_id)

            if queue_current is not None and queue_current.current:
                progress = cherrypy.request.queue_progress
                current_seconds = math.floor(progress['seconds'] - progress['seconds_ahead'])
                queue_dao.update_queue(queue_current.id, current_seconds = current_seconds)

    def serialize_track(self, track):
        return {
            'album': {
                'name': track.album.name if track.album is not None else None
            },
            'artist': {
                'name': track.artist.name if track.artist is not None else None,
            },
            'name': track.name,
            'duration': track.duration,
        }


class QueueDao:
    def get_current_track(self, user_id):
        try:
            return (get_database()
                    .query(Track)
                    .join(Queue, Track.id == Queue.track_id)
                    .join(User, Queue.user_id == User.id)
                    .filter(and_(User.id == user_id, Queue.current))
                    .group_by(Track.id)
                    .limit(1)
                    .one())
        except NoResultFound:
            return None

    def get_queue(self, id):
        try:
            return get_database().query(Queue).filter_by(id=id).one()
        except NoResultFound:
            return None

    def update_queues(self, queues):
        for id, args in queues:
            get_database().query(Queue).filter_by(id=id).update(args)

        get_database().commit()

        ws.emit('queue.update')

    def update_queue(self, id, **kwargs):
        get_database().query(Queue).filter_by(id=id).update(kwargs)
        get_database().commit()

    def get_next(self, user_id):
        database = get_database()
        current_queue = next_queue = None

        try:
            current_queue = (database.query(Queue)
                             .filter_by(user_id=user_id, current=True)
                             .order_by(Queue.index).one())

            if current_queue.current_seconds is not None:
                next_queue = current_queue
                current_queue = None
        except NoResultFound:
            pass

        if next_queue is None:
            if current_queue is not None:
                next_queue = (database.query(Queue)
                              .filter_by(user_id=user_id)
                              .filter(Queue.index > current_queue.index)
                              .order_by(Queue.index).first())
            else:
                database.query(Queue).filter_by(user_id=user_id).update({'played': None})
                next_queue = (database.query(Queue)
                              .filter_by(user_id=user_id)
                              .order_by(Queue.index).first())

        if current_queue is not None:
            current_queue.current = False

        if next_queue is not None:
            next_queue.current = True

        database.commit()

        if next_queue is not None:
            cherrypy.request.queue_current_id = next_queue.id

        cherrypy.engine.publish('queue.next', next=next_queue)

        return next_queue

    def get_queues(self, user_id):
        queues = []

        album = None
        artist = None
        track = None

        current_queues = []

        for queue in get_database().query(Queue).filter_by(user_id=user_id).order_by(Queue.index).all():
            if (queue.track.album is not None and album is not None and album.id != queue.track.album.id or
                queue.track.artist is not None and artist is not None and artist.id != queue.track.artist.id or
                queue.track.album is None and album is not None or
                queue.track.artist is None and artist is not None or
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
        get_database().query(Queue).filter_by(user_id=user_id).delete()
        get_database().commit()
        ws.emit('queue.update')

    def clear_played(self):
        user_id = cherrypy.request.user.id
        get_database().query(Queue).filter_by(user_id=user_id, played=True).delete()
        get_database().commit()
        ws.emit('queue.update')

    def add_tracks(self, ids):
        user_id = cherrypy.request.user.id
        user = get_database().query(User).filter_by(id=user_id).one()

        for id in ids:
            if id == "":
                continue

            track = get_database().query(Track).filter_by(id=id).one()

            index = self.get_new_pos(user_id)

            queue = Queue(index)
            queue.track = track
            queue.user = user

            get_database().add(queue)

        get_database().commit()

        ws.emit('queue.update')

    def remove_tracks(self, ids):
        user_id = cherrypy.request.user.id

        for id in ids:
            if id == "":
                continue

            get_database().query(Queue).filter_by(user_id=user_id, track_id = id).delete()

        get_database().commit()

        ws.emit('queue.update')

    def get_new_pos(self, user_id):
        index = get_database().query(func.max(Queue.index)).filter_by(user_id=user_id).scalar()

        if index is None:
            index = 0
        else:
            index += 1

        return index

queue_dao = QueueDao()
queue_events = QueueEvents()
