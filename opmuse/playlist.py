import cherrypy
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from sqlalchemy.orm.exc import NoResultFound
from opmuse.database import Base
from opmuse.who import User
from opmuse.library import Track

class Playlist(Base):
    __tablename__ = 'playlists'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    track_id = Column(Integer, ForeignKey('tracks.id'))
    pos = Column(Integer, index = True)

    user = relationship("User", backref=backref('users', order_by=id))
    track = relationship("Track", backref=backref('tracks', order_by=id))

    def __init__(self, pos):
        self.pos = pos


# TODO use underscore for method names?
class Model:
    def getTracks(self):
        user_id = cherrypy.session.get('user_id')

        playlists = (cherrypy.request.database.query(Playlist)
                .filter_by(user_id=user_id).order_by(Playlist.pos).all())

        tracks = [playlist.track for playlist in playlists]

        return tracks

    def clear(self):
        user_id = cherrypy.session.get('user_id')
        cherrypy.request.database.query(Playlist).filter_by(user_id=user_id).delete()

    def addTrack(self, slug):
        library = cherrypy.engine.library.library
        track = library.get_track_by_slug(slug)

        user_id = cherrypy.session.get('user_id')
        user = cherrypy.request.database.query(User).filter_by(id=user_id).one()

        pos = self.getNewPos(user_id)

        playlist = Playlist(pos)
        playlist.track = track
        playlist.user = user

        cherrypy.request.database.add(playlist)

    def removeTrack(self, slug):
        user_id = cherrypy.session.get('user_id')
        track = cherrypy.request.database.query(Track).filter_by(slug=slug).one()
        cherrypy.request.database.query(Playlist).filter_by(user_id=user_id, track_id = track.id).delete()

    def addAlbum(self, slug):
        library = cherrypy.engine.library.library
        album = library.get_album_by_slug(slug)

        user_id = cherrypy.session.get('user_id')
        user = cherrypy.request.database.query(User).filter_by(id=user_id).one()

        pos = self.getNewPos(user_id)

        for track in album.tracks:
            playlist = Playlist(pos)
            playlist.track = track
            playlist.user = user

            cherrypy.request.database.add(playlist)

            pos += 1

    def getNewPos(self, user_id):
        pos = (cherrypy.request.database.query(func.max(Playlist.pos))
            .filter_by(user_id=user_id).scalar())

        if pos is None:
            pos = 0
        else:
            pos += 1

        return pos

playlist_model = Model()

