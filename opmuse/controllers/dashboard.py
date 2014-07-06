import datetime
import cherrypy
from datetime import timedelta
from collections import OrderedDict
from sqlalchemy.orm import joinedload, undefer
from sqlalchemy import func
from opmuse.library import Artist, Album, Track, library_dao
from opmuse.security import User, security_dao
from opmuse.database import get_database
from opmuse.remotes import remotes
from opmuse.queues import queue_dao
from opmuse.search import search
from opmuse.cache import cache


class Dashboard:
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

        all_users = [current_user] + users

        all_recent_tracks = Dashboard.get_recent_tracks()
        top_artists = Dashboard.get_top_artists(all_recent_tracks)
        recent_tracks = all_recent_tracks[0:8]
        new_albums = Dashboard.get_new_albums(8, 0)

        now = datetime.datetime.now()

        day_format = "%Y-%m-%d"

        today = now.strftime(day_format)
        yesterday = (now - timedelta(days=1)).strftime(day_format)
        week = now - timedelta(weeks=1)

        track_count = library_dao.get_track_count()
        track_duration = library_dao.get_track_duration()

        if track_count is not None and track_duration is not None and track_count > 0:
            track_average_duration = int(track_duration / track_count)
        else:
            track_average_duration = 0

        for recent_track in all_recent_tracks:
            track = recent_track['track']

            for user in all_users:
                if user['user'].id == recent_track['user'].id:
                    break

            if 'played_times' not in user:
                user['played_times'] = {
                    'today': 0,
                    'yesterday': 0,
                    'week': 0
                }

            track_datetime = datetime.datetime.fromtimestamp(recent_track['timestamp'])

            # if track isn't found estimate track to average duration of a track
            if track is None:
                duration = track_average_duration
            else:
                duration = track.duration

            if track_datetime.strftime(day_format) == yesterday:
                user['played_times']['yesterday'] += duration

            if track_datetime.strftime(day_format) == today:
                user['played_times']['today'] += duration

            if track_datetime >= week:
                user['played_times']['week'] += duration

        return {
            'current_user': current_user,
            'users': users,
            'top_artists': top_artists,
            'recent_tracks': recent_tracks,
            'new_albums': new_albums
        }

    @staticmethod
    def get_new_albums(limit, offset):
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

    @staticmethod
    def get_top_artists(recent_tracks):
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

    @staticmethod
    def get_recent_tracks():
        """
        Fetch all listened tracks one week back.

        also caches the result for an hour.
        """

        cache_key = "dashboard.get_recent_tracks"
        cache_age = 3600

        if cache.needs_update(cache_key, age = cache_age):
            now = datetime.datetime.now()

            timestamp = int((now - datetime.timedelta(weeks=1)).timestamp())

            listened_tracks = library_dao.get_listened_tracks_by_timestmap(timestamp)

            _recent_tracks = []

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

                _recent_tracks.append({
                    'artist_id': artist_id,
                    'track_id': track_id,
                    'artist_name': listened_track.artist_name,
                    'name': listened_track.name,
                    'timestamp': listened_track.timestamp,
                    'user_id': listened_track.user.id
                })

            cache.set(cache_key, _recent_tracks)
        else:
            _recent_tracks = cache.get(cache_key)

        recent_tracks = []

        for _recent_track in _recent_tracks:
            recent_track = _recent_track.copy()

            recent_track['track'] = library_dao.get_track(recent_track['track_id'])
            recent_track['artist'] = library_dao.get_artist(recent_track['artist_id'])
            recent_track['user'] = security_dao.get_user(recent_track['user_id'])

            recent_tracks.append(recent_track)

        return recent_tracks
