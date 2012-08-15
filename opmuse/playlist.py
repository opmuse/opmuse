import cherrypy
from sqlalchemy import Column, Integer, ForeignKey, Boolean, or_, and_
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from sqlalchemy.orm.exc import NoResultFound
from opmuse.database import Base
from opmuse.who import User
from opmuse.library import Track, library

class Playlist(Base):
    __tablename__ = 'playlists'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    track_id = Column(Integer, ForeignKey('tracks.id'))
    weight = Column(Integer, index = True)
    playing = Column(Boolean)

    user = relationship("User", backref=backref('users', order_by=id))
    track = relationship("Track", backref=backref('tracks', order_by=id))

    def __init__(self, weight):
        self.weight = weight


# TODO use underscore for method names?
class Model:
    def getNextTrack(self, user_id):
        database = cherrypy.request.database
        playlist = next_playlist = None
        try:
            playlist = (database.query(Playlist)
                .filter_by(user_id=user_id, playing=True)
                .order_by(Playlist.weight).one())

            next_playlist = (database.query(Playlist)
                .filter_by(user_id=user_id)
                .filter(Playlist.weight > playlist.weight)
                .order_by(Playlist.weight).first())
        except NoResultFound:
            pass

        if next_playlist is None:
            next_playlist = (database.query(Playlist)
                .filter_by(user_id=user_id)
                .order_by(Playlist.weight).first())

        if next_playlist is None:
            return None

        next_playlist.playing = True

        if playlist is not None:
            playlist.playing = False

        database.commit()

        return next_playlist.track

    def getPlaylists(self, user_id):
        playlists = (cherrypy.request.database.query(Playlist)
            .filter_by(user_id=user_id).order_by(Playlist.weight).all())

        return playlists

    def getTracks(self, user_id):
        playlists = self.getPlaylists(user_id)

        tracks = [playlist.track for playlist in playlists]

        return tracks

    def clear(self):
        user_id = cherrypy.request.user.id
        cherrypy.request.database.query(Playlist).filter_by(user_id=user_id).delete()

    def addTrack(self, slug):
        track = library.get_track_by_slug(slug)

        user_id = cherrypy.request.user.id
        user = cherrypy.request.database.query(User).filter_by(id=user_id).one()

        weight = self.getNewPos(user_id)

        playlist = Playlist(weight)
        playlist.track = track
        playlist.user = user

        cherrypy.request.database.add(playlist)

    def removeTrack(self, slug):
        user_id = cherrypy.request.user.id
        track = cherrypy.request.database.query(Track).filter_by(slug=slug).one()
        cherrypy.request.database.query(Playlist).filter_by(user_id=user_id, track_id = track.id).delete()

    def addAlbum(self, slug):
        album = library.get_album_by_slug(slug)

        user_id = cherrypy.request.user.id
        user = cherrypy.request.database.query(User).filter_by(id=user_id).one()

        weight = self.getNewPos(user_id)

        for track in album.tracks:
            playlist = Playlist(weight)
            playlist.track = track
            playlist.user = user

            cherrypy.request.database.add(playlist)

            weight += 1

    def getNewPos(self, user_id):
        weight = (cherrypy.request.database.query(func.max(Playlist.weight))
            .filter_by(user_id=user_id).scalar())

        if weight is None:
            weight = 0
        else:
            weight += 1

        return weight

playlist_model = Model()

