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
from opmuse.bgtask import NonUniqueQueueError


class Dashboard:
    RECENT_TRACK_CACHE_KEY = "dashboard_get_recent_tracks"
    RECENT_TRACK_CACHE_AGE = 1200  # 20min

    def __init__(self):
        cherrypy.engine.subscribe('transcoding.start', self.transcoding_start)
        cherrypy.engine.subscribe('transcoding.end', self.transcoding_end)

    def transcoding_start(self, transcoder, track):
        ws.emit_all('dashboard.listening_now.update')

    def transcoding_end(self, track, transcoder):
        Dashboard.update_recent_tracks()
        ws.emit_all('dashboard.listening_now.update')

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='dashboard/index.html')
    def default(self):
        users = []

        for user in (get_database()
                     .query(User)
                     .order_by(User.active.desc(), User.login)
                     .filter(User.id != cherrypy.request.user.id)
                     .limit(10).all()):

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

        all_users = users + [current_user]

        new_albums = self.get_new_albums(12, 0)

        top_artists = None

        Dashboard.update_recent_tracks()

        top_artists = Dashboard.get_top_artists()

        if top_artists is not None:
            top_artists = top_artists[0:18]

        recently_listeneds = Dashboard.get_recently_listeneds()

        return {
            'all_users': all_users,
            'current_user': current_user,
            'users': users,
            'top_artists': top_artists,
            'recently_listeneds': recently_listeneds,
            'new_albums': new_albums
        }

    @staticmethod
    def get_recently_listeneds(by_user=None):
        all_recent_tracks = Dashboard.get_recent_tracks()

        if all_recent_tracks is None:
            return None

        recently_listeneds = []
        last_recent_track = last_recently_listened = None

        count = 0

        for recent_track in all_recent_tracks:
            if by_user is not None and by_user.id != recent_track['user_id']:
                continue

            if recent_track['track_id'] is not None:
                recent_track['track'] = library_dao.get_track(recent_track['track_id'])
            else:
                recent_track['track'] = None

            if recent_track['artist_id'] is not None:
                recent_track['artist'] = library_dao.get_artist(recent_track['artist_id'])
            else:
                recent_track['artist'] = None

            recent_track['user'] = security_dao.get_user(recent_track['user_id'])

            recently_listened = None

            track = recent_track['track']
            user = recent_track['user']

            last_track = last_recent_track['track'] if last_recent_track is not None else None

            if track is not None and track.album is not None:
                if (last_track is None or
                   last_track.album is None or
                   last_track.album.id != track.album.id):
                    recently_listened = {
                        'entity': track.album,
                        'tracks': [track],
                        'users': set([user]),
                        'plays': 1
                    }
                elif last_recently_listened is not None:
                    last_recently_listened['users'].add(user)
                    last_recently_listened['tracks'].append(track)
                    last_recently_listened['plays'] += 1
            elif track is not None and track.album is None:
                recently_listened = {
                    'entity': track,
                    'users': [user],
                }
            elif track is None:
                recently_listened = {
                    'entity': recent_track,
                    'users': [user]
                }

            if recently_listened is not None:
                recently_listeneds.append(recently_listened)
                last_recently_listened = recently_listened
                count += 1

            if count > 20:
                break

            last_recent_track = recent_track

        return recently_listeneds

    def get_new_albums(self, limit, offset):
        return (get_database()
                .query(Album)
                .options(joinedload(Album.tracks))
                .options(undefer(Album.artist_count))
                .join(Track, Album.id == Track.album_id)
                .group_by(Album.id)
                .order_by(func.max(Track.created).desc())
                .limit(limit)
                .offset(offset)
                .all())

    @staticmethod
    def get_top_artists():
        all_recent_tracks = Dashboard.get_recent_tracks()

        if all_recent_tracks is None:
            return None

        top_artists = {}

        for recent_track in all_recent_tracks:
            if recent_track['artist_id'] is not None:
                recent_track['artist'] = library_dao.get_artist(recent_track['artist_id'])
            else:
                recent_track['artist'] = None

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

    @staticmethod
    def get_recent_tracks():
        cache_key = Dashboard.RECENT_TRACK_CACHE_KEY

        if cache.has(cache_key):
            return cache.get(cache_key)
        else:
            return None

    @staticmethod
    def update_recent_tracks():
        cache_key = Dashboard.RECENT_TRACK_CACHE_KEY
        cache_age = Dashboard.RECENT_TRACK_CACHE_AGE

        if cache.needs_update(cache_key, age = cache_age):
            cache.keep(cache_key)

            try:
                cherrypy.engine.bgtask.put_unique(Dashboard._fetch_recent_tracks, 9)
            except NonUniqueQueueError:
                pass

    @staticmethod
    def _fetch_recent_tracks():
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
