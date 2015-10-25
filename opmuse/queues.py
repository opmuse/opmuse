# Copyright 2012-2015 Mattias Fliesberg
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
import math
import random
from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, or_, and_
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from sqlalchemy.orm.exc import NoResultFound, ObjectDeletedError
from opmuse.database import Base, get_database
from opmuse.security import User
from opmuse.library import Track, Artist, Album, library_dao
from opmuse.cache import cache
from opmuse.ws import ws
from opmuse.utils import memoize


__all__ = ["Queue", "QueueEvents", "QueueDao", "queue_dao", "queue_events"]


class Queue(Base):
    __tablename__ = 'queues'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', name='fk_queues_user_id'))
    track_id = Column(Integer, ForeignKey('tracks.id', name='fk_queues_track_id'))
    index = Column(Integer, index=True)
    current_seconds = Column(Integer)
    current = Column(Boolean, default=False)
    playing = Column(Boolean, default=False)
    played = Column(Boolean, default=False)
    error = Column(String(255))

    user = relationship("User", backref=backref('users', order_by=id))
    track = relationship("Track", lazy='joined', backref=backref('tracks', cascade="all,delete", order_by=id))

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
        track = cache.get('queue.current_track_%d' % ws_user.id)
        progress = cache.get('queue.current_progress_%d' % ws_user.id)

        if track is not None:
            ws.emit('queue.current_track_%d' % ws_user.id, track, ws_user=ws_user)

        if progress is not None:
            ws.emit('queue.current_progress_%d' % ws_user.id, progress, ws_user=ws_user)

    def transcoding_progress(self, progress, transcoder, track):
        ws_user = ws.get_ws_user()

        if ws_user is not None:
            cache.set('queue.current_progress_%d' % ws_user.id, progress)

        if 'User-Agent' in cherrypy.request.headers:
            user_agent = cherrypy.request.headers['User-Agent']
        else:
            user_agent = None

        format = transcoder.__class__.outputs()

        ws.emit('queue.progress', progress, self.serialize_track(track), user_agent, format)

        cherrypy.request.queue_progress = progress

    def transcoding_start(self, transcoder, track):
        if hasattr(cherrypy.request, 'queue_current_id') and cherrypy.request.queue_current_id is not None:
            queue_current_id = cherrypy.request.queue_current_id
            queue_dao.update_queue(queue_current_id, current_seconds=None, playing=True)

        track = self.serialize_track(track)

        if 'User-Agent' in cherrypy.request.headers:
            user_agent = cherrypy.request.headers['User-Agent']
        else:
            user_agent = None

        format = transcoder.__class__.outputs()

        ws_user = ws.get_ws_user()

        if ws_user is not None:
            cache.set('queue.current_track_%d' % ws_user.id, track)

        ws.emit('queue.start', track, user_agent, format)

    def transcoding_done(self, track):
        if hasattr(cherrypy.request, 'queue_current_id') and cherrypy.request.queue_current_id is not None:
            queue_current_id = cherrypy.request.queue_current_id

            queue_dao.update_queue(queue_current_id, played=True)

            cherrypy.request.queues_done = True

            ws_user = ws.get_ws_user()
            cache.set('queue.current_track_%d' % ws_user.id, None)
            cache.set('queue.current_progress_%d' % ws_user.id, None)

    def transcoding_end(self, track, transcoder):
        if hasattr(cherrypy.request, 'queue_current_id') and cherrypy.request.queue_current_id is not None:
            queue_current = queue_dao.get_queue(cherrypy.request.queue_current_id)

            if queue_current is not None:
                queue_dao.update_queue(queue_current.id, playing=False)

            if queue_current is not None and queue_current.current:
                if (hasattr(cherrypy.request, 'queue_progress') and cherrypy.request.queue_progress is not None and
                        not hasattr(cherrypy.request, 'queues_done') or not cherrypy.request.queues_done):
                    progress = cherrypy.request.queue_progress
                    current_seconds = math.floor(progress['seconds'] - progress['seconds_ahead'])
                else:
                    current_seconds = None

                if transcoder.success:
                    error = None
                else:
                    error = transcoder.error

                queue_dao.update_queue(queue_current.id, current_seconds=current_seconds, error=error)

            ws.emit('queue.update')

        track = self.serialize_track(track)

        user_agent = cherrypy.request.headers['User-Agent']

        ws.emit('queue.end', track, user_agent)

    def serialize_track(self, track):
        return {
            'id': track.id,
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
        track = cache.get('queue.current_track_%d' % user_id)

        if track is not None:
            track = library_dao.get_track(track['id'])

            if track is None:
                return self._get_current_track(user_id)
            else:
                return track
        else:
            return None

    @memoize
    def get_playing_track(self, user_id):
        try:
            return (get_database()
                    .query(Track)
                    .join(Queue, Track.id == Queue.track_id)
                    .join(User, Queue.user_id == User.id)
                    .filter(and_(User.id == user_id, Queue.current, Queue.playing))
                    .group_by(Track.id)
                    .limit(1)
                    .one())
        except NoResultFound:
            return None

    def _get_current_track(self, user_id):
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

    @memoize
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
        try:
            get_database().query(Queue).filter_by(id=id).update(kwargs)
            get_database().commit()
        except ObjectDeletedError:
            pass

    def get_random_track(self, user_id):
        tracks = library_dao.get_random_tracks(1)

        if len(tracks) > 0:
            return tracks[0]
        else:
            return None

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

    @memoize
    def get_queues(self, user_id):
        queues = []

        album = None
        artist = None
        track = None

        info = current_queues = None

        query = get_database().query(Queue).filter_by(user_id=user_id).order_by(Queue.index)

        for index, queue in enumerate(query.all()):
            if (index == 0 or
                    queue.track.album is not None and album is not None and album.id != queue.track.album.id or
                    queue.track.album is None and album is not None or
                    queue.track.artist is None and artist is not None or
                    track is not None and track.disc != queue.track.disc):

                if info is not None and current_queues is not None:
                    queues.append((info, current_queues))

                info = {
                    'duration': 0,
                    'artists': set(),
                    'album': queue.track.album,
                    'disc': queue.track.disc,
                }

                current_queues = []

            info['duration'] += queue.track.duration if queue.track.duration is not None else 0
            info['artists'].add(queue.track.artist)

            current_queues.append(queue)

            album = queue.track.album
            artist = queue.track.artist
            track = queue.track

        if current_queues is not None and len(current_queues) > 0:
            queues.append((info, current_queues))

        full_info = {
            'duration': 0
        }

        for info, queue in queues:
            full_info['duration'] += info['duration']
            info['artists'] = list(info['artists'])

        return queues, full_info

    def clear(self):
        user_id = cherrypy.request.user.id

        get_database().query(Queue).filter(Queue.user_id == user_id).delete(synchronize_session='fetch')

        get_database().commit()

        self._reset_current()

        ws.emit('queue.update')

    def shuffle(self):
        user_id = cherrypy.request.user.id

        current_index = (get_database().query(Queue.index)
                                       .filter(Queue.user_id == user_id, Queue.current)
                                       .scalar())

        query = get_database().query(Queue).filter(Queue.user_id == user_id)

        if current_index is None:
            current_index = 0
        else:
            query = query.filter(Queue.index > current_index)

        queue_count = query.count()

        indexes = list(range(queue_count))

        random.shuffle(indexes)

        for index, queue in enumerate(query.all()):
            queue.index = current_index + 1 + indexes[index]

        get_database().commit()

        ws.emit('queue.update')

    def clear_played(self):
        user_id = cherrypy.request.user.id
        get_database().query(Queue).filter(and_(Queue.user_id == user_id, Queue.played,
                                           "not current")).delete(synchronize_session='fetch')
        get_database().commit()
        ws.emit('queue.update')

    def add_album_tracks(self, album_id):
        try:
            album = get_database().query(Album).filter_by(id=album_id).one()
            self.add_tracks([track.id for track in album.tracks])
        except NoResultFound:
            return

    def add_tracks(self, track_ids):
        user_id = cherrypy.request.user.id

        queues = []

        for track_id in track_ids:
            if track_id == "":
                continue

            index = self.get_new_pos(user_id)

            queue = Queue(index)
            queue.track_id = track_id
            queue.user_id = user_id

            get_database().add(queue)

            queues.append(queue)

        get_database().commit()

        for queue in queues:
            # always update seen, True means now
            if queue.track.album is not None:
                queue.track.album.seen = True

        ws.emit('queue.update')

    def reset_current(self):
        user_id = cherrypy.request.user.id

        (get_database().query(Queue)
         .filter(and_(Queue.user_id == user_id, Queue.current))
         .update({'current': False, 'current_seconds': None}, synchronize_session='fetch'))

        get_database().commit()

        self._reset_current()

        ws.emit('queue.update')

    def remove(self, ids):
        user_id = cherrypy.request.user.id

        query = get_database().query(Queue).filter(and_(Queue.user_id == user_id, Queue.id.in_(ids)))

        try:
            query.filter("current").one()

            self._reset_current()
        except NoResultFound:
            pass

        query.delete(synchronize_session='fetch')

        get_database().commit()

        ws.emit('queue.update')

    def _reset_current(self):
        ws_user = ws.get_ws_user()
        cache.set('queue.current_track_%d' % ws_user.id, None)
        cache.set('queue.current_progress_%d' % ws_user.id, None)

        ws.emit('queue.reset')

    def get_new_pos(self, user_id):
        index = get_database().query(func.max(Queue.index)).filter_by(user_id=user_id).scalar()

        if index is None:
            index = 0
        else:
            index += 1

        return index

queue_dao = QueueDao()
queue_events = QueueEvents()
