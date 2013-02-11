import cherrypy
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
    playing = Column(Boolean)
    played = Column(Boolean)

    user = relationship("User", backref=backref('users', order_by=id))
    track = relationship("Track", backref=backref('tracks', cascade="all,delete", order_by=id))

    def __init__(self, weight):
        self.weight = weight


class QueueEvents:
    def __init__(self):
        cherrypy.engine.subscribe('transcoding.start', self.transcoding_start)
        cherrypy.engine.subscribe('transcoding.progress', self.transcoding_progress)

        ws.on('queue.open', self.queue_open)

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

    def transcoding_start(self, track):
        track = self.serialize_track(track)

        ws_user = ws.get_ws_user()
        ws_user.set('queue.current_track', track)

        ws.emit('queue.start', track)

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
    def get_next_track(self, user_id, repeat = False):
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

        if not repeat and next_queue.played:
            return None

        next_queue.playing = True

        if queue is not None:
            queue.played = True
            queue.playing = False

        database.commit()

        return next_queue.track

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
