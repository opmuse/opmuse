import datetime
import cherrypy
from datetime import timedelta
from collections import OrderedDict
from sqlalchemy.orm import joinedload, undefer
from sqlalchemy import func
from opmuse.library import Album, Track
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
        recent_tracks = Dashboard.get_recent_tracks(all_users)
        new_albums = Dashboard.get_new_albums(6, 0)

        now = datetime.datetime.now()

        day_format = "%Y-%m-%d"

        today = now.strftime(day_format)
        yesterday = (now - timedelta(days=1)).strftime(day_format)
        week = now.isocalendar()[0:1]

        for recent_track in recent_tracks:
            track = recent_track['track']

            if track is None:
                continue

            user = recent_track['user']

            if 'played_times' not in user:
                user['played_times'] = {
                    'today': 0,
                    'yesterday': 0,
                    'week': 0
                }

            track_datetime = datetime.datetime.fromtimestamp(int(recent_track['timestamp']))

            if track_datetime.strftime(day_format) == yesterday:
                user['played_times']['yesterday'] += track.duration

            if track_datetime.strftime(day_format) == today:
                user['played_times']['today'] += track.duration

            if track_datetime.isocalendar()[0:1] == week:
                user['played_times']['week'] += track.duration

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
    def get_recent_tracks(all_users, limit = 6):
        all_recent_tracks = []

        for user in all_users:
            if user['remotes_user'] is None or user['remotes_user']['lastfm'] is None:
                continue

            recent_tracks = []

            for recent_track in user['remotes_user']['lastfm']['recent_tracks']:
                recent_tracks.append((user, recent_track))

            all_recent_tracks += recent_tracks

        all_recent_tracks = sorted(all_recent_tracks,
                                   key=lambda recent_track: recent_track[1]['timestamp'], reverse=True)

        recent_tracks = []

        for user, recent_track in all_recent_tracks:
            results = search.query_artist(recent_track['artist'], exact=True)

            track = artist = None

            if len(results) > 0:
                artist = results[0]

                results = search.query_track(recent_track['name'], exact=True)

                if len(results) > 0:
                    for result in results:
                        if result.artist.id == artist.id:
                            track = result

            recent_tracks.append({
                'artist': artist,
                'track': track,
                'artist_name': recent_track['artist'],
                'name': recent_track['name'],
                'timestamp': recent_track['timestamp'],
                'user': user
            })

            if len(recent_tracks) == limit:
                break

        return recent_tracks
