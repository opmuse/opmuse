import datetime
import cherrypy
from sqlalchemy.orm import joinedload, undefer
from sqlalchemy import func
from opmuse.library import Album, Track, library_dao
from opmuse.security import User, security_dao
from opmuse.database import get_database
from opmuse.remotes import remotes
from opmuse.queues import queue_dao
from opmuse.search import search
from opmuse.cache import cache
from opmuse.ws import ws


class Dashboard:
    RECENT_TRACK_CACHE_KEY = "dashboard_get_recent_tracks"
    RECENT_TRACK_CACHE_AGE = 1200  # 20min

    def __init__(self):
        cherrypy.engine.subscribe('transcoding.end', self.transcoding_end)

    def transcoding_end(self, track, transcoder):
        self.update_recent_tracks()

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='dashboard/index.html')
    def default(self):
        users = []

        for user in (get_database()
                     .query(User)
                     .order_by(User.login)
                     .filter(User.id != cherrypy.request.user.id)
                     .limit(8).all()):

            remotes.update_user(user)

            remotes_user = remotes.get_user(user)

            users.append({
                'remotes_user': remotes_user,
                'user': user,
                'playing_track': queue_dao.get_playing_track(user.id)
            })

        remotes.update_user(cherrypy.request.user)

        remotes_user = remotes.get_user(cherrypy.request.user)

        current_user = {
            'user': cherrypy.request.user,
            'playing_track': queue_dao.get_playing_track(cherrypy.request.user.id),
            'remotes_user': remotes_user,
        }

        new_albums = self.get_new_albums(8, 0)

        recent_tracks = top_artists = None

        self.update_recent_tracks()

        all_recent_tracks = self.get_recent_tracks()

        if all_recent_tracks is not None:
            # artist is needed for get_top_artists() fetch it for all
            for recent_track in all_recent_tracks:
                recent_track['artist'] = library_dao.get_artist(recent_track['artist_id'])

            top_artists = self.get_top_artists(all_recent_tracks)[0:10]

            recent_tracks = []

            # track and user is only needed in template so we only fetch them for recent_tracks
            for recent_track in all_recent_tracks[0:8]:
                recent_track['track'] = library_dao.get_track(recent_track['track_id'])
                recent_track['user'] = security_dao.get_user(recent_track['user_id'])

                recent_tracks.append(recent_track)

        return {
            'current_user': current_user,
            'users': users,
            'top_artists': top_artists,
            'recent_tracks': recent_tracks,
            'new_albums': new_albums
        }

    def get_new_albums(self, limit, offset):
        return (get_database()
                .query(Album)
                .options(joinedload(Album.tracks))
                .options(undefer(Album.artist_count))
                .join(Track, Album.id == Track.album_id)
                .group_by(Album.id)
                .order_by(func.max(Track.added).desc())
                .limit(limit)
                .offset(offset)
                .all())

    def get_top_artists(self, recent_tracks):
        top_artists = {}

        for recent_track in recent_tracks:
            if recent_track['artist'] is not None:
                if recent_track['artist'] not in top_artists:
                    top_artists[recent_track['artist']] = 1
                else:
                    top_artists[recent_track['artist']] += 1

        result = []

        for artist, count in sorted(top_artists.items(), key=lambda x: x[1], reverse=True):
            result.append({
                'artist': artist,
                'count': count
            })

        return result

    def get_recent_tracks(self):
        cache_key = Dashboard.RECENT_TRACK_CACHE_KEY

        if cache.has(cache_key):
            return cache.get(cache_key)
        else:
            return None

    def update_recent_tracks(self):
        cache_key = Dashboard.RECENT_TRACK_CACHE_KEY
        cache_age = Dashboard.RECENT_TRACK_CACHE_AGE

        if cache.needs_update(cache_key, age = cache_age):
            cache.keep(cache_key)
            cherrypy.engine.bgtask.put(self._fetch_recent_tracks, 9)

    def _fetch_recent_tracks(self):
        """
        Look up all listened tracks 4 weeks back in whoosh/search.
        """

        now = datetime.datetime.now()

        timestamp = int((now - datetime.timedelta(weeks=4)).timestamp())

        listened_tracks = library_dao.get_listened_tracks_by_timestmap(timestamp)

        recent_tracks = []

        for listened_track in listened_tracks:
            results = search.get_results_artist(listened_track.artist_name, exact=True)
            results = sorted(results, key=lambda result: result[1], reverse=True)

            track_id = artist_id = None

            if len(results) > 0:
                artist_id = results[0][0]

                tracks = search.query_track(listened_track.name, exact=True)

                if len(tracks) > 0:
                    for track in tracks:
                        if track.artist.id == artist_id:
                            track_id = track.id

            recent_tracks.append({
                'artist_id': artist_id,
                'track_id': track_id,
                'artist_name': listened_track.artist_name,
                'name': listened_track.name,
                'timestamp': listened_track.timestamp,
                'user_id': listened_track.user.id
            })

        cache.set(Dashboard.RECENT_TRACK_CACHE_KEY, recent_tracks)

        ws.emit_all('dashboard.recent_tracks.fetched')

    _fetch_recent_tracks.bgtask_name = "Fetch recent tracks for dashboard"
