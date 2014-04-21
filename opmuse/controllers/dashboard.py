import datetime
import cherrypy
from datetime import timedelta
from collections import OrderedDict
from sqlalchemy.orm import joinedload, undefer
from sqlalchemy import func
from opmuse.library import Album, Track, library_dao
from opmuse.security import User
from opmuse.database import get_database
from opmuse.remotes import remotes
from opmuse.queues import queue_dao
from opmuse.search import search


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

        top_artists = Dashboard.get_top_artists(all_users)
        all_recent_tracks = Dashboard.get_recent_tracks(all_users)
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
    def get_top_artists(all_users, limit = 12):
        top_artists = OrderedDict({})

        index = 0

        while True:
            stop = True

            for user in all_users:
                if user['remotes_user'] is None or user['remotes_user']['lastfm'] is None:
                    continue

                top = user['remotes_user']['lastfm']['top_artists_month']

                if top is not None and index < len(top):
                    stop = False

                    artist = top[index]

                    results = search.query_artist(artist['name'], exact=True)

                    if len(results) > 0:
                        top_artists[results[0]] = None

                    if len(top_artists) >= limit:
                        stop = True
                        break
            if stop:
                break

            index += 1

        top_artists = list(top_artists.keys())

        return top_artists

    @staticmethod
    def get_recent_tracks(all_users):
        now = datetime.datetime.now()

        timestamp = int((now - datetime.timedelta(weeks=1)).timestamp())

        listened_tracks = library_dao.get_listened_tracks_by_timestmap(timestamp)

        recent_tracks = []

        for listened_track in listened_tracks:
            results = search.query_artist(listened_track.artist_name, exact=True)

            track = artist = None

            if len(results) > 0:
                artist = results[0]

                results = search.query_track(listened_track.name, exact=True)

                if len(results) > 0:
                    for result in results:
                        if result.artist.id == artist.id:
                            track = result

            recent_tracks.append({
                'artist': artist,
                'track': track,
                'artist_name': listened_track.artist_name,
                'name': listened_track.name,
                'timestamp': listened_track.timestamp,
                'user': listened_track.user
            })

        return recent_tracks
