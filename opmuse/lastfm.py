# Copyright 2012-2014 Mattias Fliesberg
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

import logging
import re
import cherrypy
import calendar
import datetime
import time
import math
import json
import hashlib
from sqlalchemy import Column, String
from urllib import request
from urllib import parse
from urllib.error import HTTPError
from opmuse.security import User
from opmuse.search import search

User.lastfm_session_key = Column(String(32))
User.lastfm_user = Column(String(64))


class LastfmRetry(Exception):
    pass


class LastfmError(Exception):
    pass


class LastfmApiError(LastfmError):
    pass


def log(msg):
    cherrypy.log(msg, context='lastfm')


def debug(msg, traceback=False):
    cherrypy.log.error(msg, context='lastfm', severity=logging.DEBUG, traceback=traceback)


class LastfmNetwork:
    API_URL = "https://ws.audioscrobbler.com/2.0/"
    AUTH_URL = "https://last.fm/api/auth"

    def __init__(self, key, secret, session_key=None):
        self.key = key
        self.secret = secret
        self.session_key = session_key

    def get_user_info(self, user_name=None):
        if user_name is not None:
            params = {"user": user_name}
        else:
            params = {}

        return self._request("user.getInfo", params)['user']

    def get_auth_session(self, token):
        params = {
            'token': token
        }

        return self._request('auth.getSession', params)['session']

    def get_auth_token(self):
        return self._request('auth.getToken')['token']

    def track_update_now_playing(self, artist, title, album = None, album_artist = None,
                                 duration = None, track_number = None, mbid = None, context = None):
        params = {
            'artist': artist,
            'track': title,
            'album': album,
            'album_artist': album_artist,
            'duration': duration,
            'track_number': track_number,
            'mbid': mbid,
            'context': context
        }

        params = self._clean_params(params)

        self._request('track.updateNowPlaying', data_params = params)

    def track_scrobble(self, artist, title, timestamp, album = None, album_artist = None, track_number = None,
                       duration = None, stream_id = None, context = None, mbid = None):
        params = {
            'artist': artist,
            'track': title,
            'timestamp': timestamp,
            'album': album,
            'album_artist': album_artist,
            'track_number': track_number,
            'duration': duration,
            'stream_id': stream_id,
            'context': context,
            'mbid': mbid,
        }

        params = self._clean_params(params)

        self._request('track.scrobble', data_params = params)

    def get_user_recent_tracks(self, user_name, page = 1, limit = 50):
        """
        if page is None fetch all pages
        """

        if page is None:
            page = 1
            totalPages = None
        else:
            totalPages = 1

        tries = 1

        while totalPages is None or page <= totalPages:
            params = {
                'user': user_name,
                'page': page,
                'limit': limit
            }

            try:
                tries += 1

                debug('Fetching recent tracks page %d%s for %s' %
                      (page, ' of %d' % totalPages if totalPages is not None else '', user_name))

                result = self._request('user.getRecentTracks', params)['recenttracks']

                if totalPages is None:
                    totalPages = int(result['@attr']['totalPages'])

                if '@attr' in result:
                    total = int(result['@attr']['total'])
                else:
                    total = None

                if 'track' not in result:
                    raise LastfmRetry()

                for track in result['track']:
                    if 'date' in track:
                        timestamp = int(track['date']['uts'])
                    else:
                        timestamp = None

                    yield {
                        'artist': track['artist']['#text'],
                        'album': track['album']['#text'],
                        'name': track['name'],
                        'timestamp': timestamp,
                        'total': total
                    }

                page += 1
                tries = 1
            except (LastfmApiError, LastfmRetry, HTTPError) as error:
                if isinstance(error, LastfmApiError) or isinstance(error, HTTPError):
                    debug('Got error while fetching recent tracks for %s%s\n' %
                          (user_name, ', not retrying' if tries > 10 else ', retrying'), traceback=True)

                if tries > 10:
                    log("While fetching recent tracks for %s, tried and failed 10 times, skipping page %d" %
                        (user_name, page))
                    tries = 1
                    page += 1
                    continue

                time.sleep(10)
                continue

    def get_library_artists(self, user_name, limit):
        params = {
            'limit': limit,
            'user': user_name
        }

        artists = []

        result = self._request('library.getArtists', params)['artists']

        if 'artist' in result:
            for artist in self.process_list(result['artist']):
                artists.append({
                    'name': artist['name'],
                    'playcount': int(artist['playcount']),
                    'tagcount': artist['tagcount'],
                })

        return artists

    def get_user_top_artists(self, user_name, period, page, limit):
        params = {
            'user': user_name,
            'period': period,
            'page': page,
            'limit': limit,
        }

        artists = []

        result = self._request('user.getTopArtists', params)['topartists']

        if 'artist' in result:
            for artist in self.process_list(result['artist']):
                artists.append({
                    'name': artist['name'],
                    'playcount': int(artist['playcount']),
                })

        return artists

    def get_user_top_albums(self, user_name, period, page, limit):
        params = {
            'user': user_name,
            'period': period,
            'page': page,
            'limit': limit,
        }

        albums = []

        result = self._request('user.getTopAlbums', params)['topalbums']

        if 'album' in result:
            for album in self.process_list(result['album']):
                albums.append({
                    'name': album['name'],
                    'artist_name': album['artist']['name'],
                    'playcount': int(album['playcount']),
                })

        return albums

    def get_track_info(self, artist, track, mbid = None):
        params = {
            'artist': artist,
            'track': track,
            'mbid': mbid
        }

        params = self._clean_params(params)

        track = self._request('track.getInfo', params)['track']

        if 'wiki' in track:
            wiki = track['wiki']['summary']
        else:
            wiki = None

        if track['playcount'] != '':
            playcount = int(track['playcount'])
        else:
            playcount = None

        return {
            'artist': track['artist'],
            'name': track['name'],
            'listeners': int(track['listeners']),
            'mbid': track['mbid'],
            'playcount': playcount,
            'url': track['url'],
            'wiki': wiki,
        }

    def get_album_info(self, artist, album, mbid = None):
        params = {
            'artist': artist,
            'album': album,
            'mbid': mbid
        }

        params = self._clean_params(params)

        album = self._request('album.getInfo', params)['album']

        cover = None

        for image in album['image']:
            if image['size'] == "extralarge" and image['#text'] != '':
                cover = image['#text']
                break

        if 'wiki' in album:
            wiki = album['wiki']['summary']
        else:
            wiki = None

        if album['playcount'] != '':
            playcount = int(album['playcount'])
        else:
            playcount = None

        return {
            'artist': album['artist'],
            'name': album['name'],
            'listeners': int(album['listeners']),
            'mbid': album['mbid'],
            'playcount': playcount,
            'url': album['url'],
            'wiki': wiki,
            'cover': cover
        }

    def get_artist_top_tags(self, artist, mbid = None):
        params = {
            'artist': artist,
            'mbid': mbid
        }

        params = self._clean_params(params)

        tags = []

        result = self._request('artist.getTopTags', params)['toptags']

        if 'tag' in result:
            for tag in self.process_list(result['tag']):
                tags.append(tag['name'])

        return tags

    def get_track_top_tags(self, artist, track, mbid = None):
        params = {
            'artist': artist,
            'track': track,
            'mbid': mbid
        }

        params = self._clean_params(params)

        tags = []

        result = self._request('track.getTopTags', params)['toptags']

        if 'tag' in result:
            for tag in self.process_list(result['tag']):
                tags.append(tag['name'])

        return tags

    def get_album_top_tags(self, artist, album, mbid = None):
        params = {
            'artist': artist,
            'album': album,
            'mbid': mbid
        }

        params = self._clean_params(params)

        tags = []

        result = self._request('album.getTopTags', params)['toptags']

        if 'tag' in result:
            for tag in self.process_list(result['tag']):
                tags.append(tag['name'])

        return tags

    def get_artist_similar(self, artist, limit=None, mbid=None):
        params = {
            'artist': artist,
            'limit': limit,
            'mbid': mbid
        }

        params = self._clean_params(params)

        artists = []

        result = self._request('artist.getSimilar', params)['similarartists']

        if 'artist' in result:
            for artist in self.process_list(result['artist']):
                artists.append({
                    'name': artist['name'],
                    'url': artist['url'] if 'url' in artist else None,
                })

        return artists

    def get_artist_info(self, artist, mbid=None):
        params = {
            'artist': artist,
            'mbid': mbid
        }

        params = self._clean_params(params)

        artist = self._request('artist.getInfo', params)['artist']

        cover = None

        for image in artist['image']:
            if image['size'] == "extralarge" and image['#text'] != '':
                cover = image['#text']
                break

        return {
            'name': artist['name'],
            'listeners': int(artist['stats']['listeners']) if artist['stats']['listeners'] != '' else 0,
            'mbid': artist['mbid'],
            'playcount': int(artist['stats']['playcount']) if artist['stats']['playcount'] != '' else 0,
            'url': artist['url'],
            'bio': artist['bio']['summary'],
            'cover': cover
        }

    def get_tag_top_albums(self, tag_name, page, limit):
        params = {
            'tag': tag_name,
            'page': page,
            'limit': limit,
        }

        params = self._clean_params(params)

        albums = []

        result = self._request('tag.getTopAlbums', params)['topalbums']

        if 'album' in result:
            for album in self.process_list(result['album']):
                albums.append({
                    'name': album['name']
                })

        return albums

    def get_tag_top_artists(self, tag_name, page, limit):
        params = {
            'tag': tag_name,
            'page': page,
            'limit': limit,
        }

        params = self._clean_params(params)

        artists = []

        result = self._request('tag.getTopArtists', params)['topartists']

        if 'artist' in result:
            for artist in self.process_list(result['artist']):
                artists.append({
                    'name': artist['name']
                })

        return artists

    def get_web_auth_url(self, token):
        params = {
            'token': token,
            'api_key': self.key,
        }

        return "%s?%s" % (LastfmNetwork.AUTH_URL, parse.urlencode(params))

    def track_love(self, artist_name, track_name):
        params = {
            'artist': artist_name,
            'track': track_name,
        }

        params = self._clean_params(params)

        result = self._request('track.love', None, params)

        return result

    def _request(self, method, method_params = None, data_params = None):
        params = {
            'api_key': self.key,
            'method': method,
            'sk': self.session_key
        }

        if method_params is not None:
            params.update(method_params)

        if data_params is not None:
            params.update(data_params)

        api_sig = ""

        for name in sorted(params):
            value = params[name]
            api_sig = "%s%s%s" % (api_sig, name, value)

        api_sig = "%s%s" % (api_sig, self.secret)

        params['api_sig'] = self.md5(api_sig)
        params['format'] = 'json'

        if method_params is not None or data_params is None:
            url = "%s?%s" % (LastfmNetwork.API_URL, parse.urlencode(params))
        else:
            url = LastfmNetwork.API_URL

        if data_params is not None:
            data = parse.urlencode(params).encode()
        else:
            data = None

        f = request.urlopen(url, data)

        result = json.loads(f.read().decode('utf8', 'replace'))

        if result == "":
            raise LastfmApiError("Got empty response")

        if 'error' in result:
            raise LastfmApiError(result['message'])

        return result

    def _clean_params(self, params):
        new_params = {}

        for name, value in params.items():
            if value is not None:
                new_params[name] = value

        return params

    def md5(self, string):
        m = hashlib.md5()
        m.update(string.encode())
        return m.hexdigest()

    def process_list(self, result):
        """
        for processing lastfm's weird responses :/
        """
        if isinstance(result, list):
            for item in result:
                yield item
        elif isinstance(result, dict):
            yield result
        elif isinstance(result, str):
            yield {
                'name': result
            }
        else:
            raise ValueError('Unsupported type %s' % type(result))


class Lastfm:
    def __init__(self):
        cherrypy.engine.subscribe('transcoding.start', self.transcoding_start)
        cherrypy.engine.subscribe('transcoding.end', self.transcoding_end)
        cherrypy.engine.subscribe('transcoding.progress', self.transcoding_progress)

    def transcoding_progress(self, progress, transcoder, track):
        cherrypy.request.lastfm_progress = progress

    def transcoding_start(self, transcoder, track):
        if not hasattr(cherrypy.request, 'user'):
            return

        session_key = cherrypy.request.user.lastfm_session_key
        cherrypy.engine.bgtask.put(self.update_now_playing, 30, session_key, **self.track_to_args(track))

    def transcoding_end(self, track, transcoder):
        if hasattr(cherrypy.request, 'lastfm_progress') and cherrypy.request.lastfm_progress is not None:
            lastfm_progress = cherrypy.request.lastfm_progress

            seconds_ahead = lastfm_progress['seconds_ahead']
            session_key = cherrypy.request.user.lastfm_session_key
            user = cherrypy.request.user.login

            seconds = lastfm_progress['seconds'] - seconds_ahead
            cherrypy.engine.bgtask.put(self.scrobble, 30, user, session_key, seconds, **self.track_to_args(track))

    def get_network(self, session_key=None):
        config = cherrypy.tree.apps[''].config['opmuse']

        if 'lastfm.key' not in config or 'lastfm.secret' not in config:
            raise LastfmError('lastfm.key and lastfm.secret needs to be set for lastfm features.')

        key = config['lastfm.key']
        secret = config['lastfm.secret']

        return LastfmNetwork(key, secret, session_key)

    def get_authenticated_user_name(self, session_key=None):
        if session_key is None:
            session_key = cherrypy.request.user.lastfm_session_key

        network = self.get_network(session_key)

        user = network.get_user_info()

        return user['name']

    def track_love(self, artist_name, track_name, session_key=None):
        if session_key is None:
            session_key = cherrypy.request.user.lastfm_session_key
        network = self.get_network(session_key)

        result = network.track_love(artist_name, track_name)

        return result

    def update_now_playing(self, session_key, **args):
        if session_key is None:
            return

        try:
            network = self.get_network(session_key)
            network.track_update_now_playing(**args)
        except LastfmError as error:
            log('Error, failed to update now playing for "%s - %s - %s": %s.' % (
                args['artist'],
                args['album'],
                args['title'],
                error
            ))

    update_now_playing.bgtask_name = "Lastfm update now playing"

    def scrobble(self, user, session_key, seconds, **args):
        if session_key is None:
            return

        try:
            if not (args['duration'] > 30 and (seconds > 4 * 60 or seconds > args['duration'] / 2)):
                log('%s skipped scrobbling "%s - %s - %s" which is %d seconds long and started playing %d seconds ago.'
                    % (user, args['artist'], args['album'], args['title'], args['duration'], seconds))
                return

            network = self.get_network(session_key)

            args['timestamp'] = math.floor(self.get_utc_timestamp() - seconds)

            network.track_scrobble(**args)

            log('%s scrobbled "%s - %s - %s" which is %d seconds long and started playing %d seconds ago.' % (
                user,
                args['artist'],
                args['album'],
                args['title'],
                args['duration'],
                seconds
            ))

        except LastfmError as error:
            # TODO put in queue and scrobble later
            log('Error, failed to scrobble "%s - %s - %s": %s.' % (
                args['artist'],
                args['album'],
                args['title'],
                error
            ))

    scrobble.bgtask_name = "Lastfm scrobble track for {0}"

    def track_to_args(self, track):

        # lastfm can't handle track number that ain't numbers
        if track.number is not None and re.match('^[0-9]+$', track.number):
            track_number = track.number
        else:
            track_number = None

        return {
            'artist': track.artist.name if track.artist is not None else None,
            'title': track.name,
            'album': track.album.name if track.album is not None else None,
            'album_artist': None,
            'duration': track.duration,
            'track_number': track_number
        }

    def get_utc_timestamp(self):
        return calendar.timegm(
            datetime.datetime.utcnow().utctimetuple()
        )

    def get_user_tracks(self, user_name, session_key = None):
        if session_key is None:
            session_key = cherrypy.request.user.lastfm_session_key

        try:
            network = self.get_network(session_key)

            for track in network.get_user_recent_tracks(user_name, page=None):
                yield track
        except LastfmError as error:
            log('Failed to get user tracks "%s": %s.' % (
                user_name,
                error
            ))

    def get_user(self, user_name, session_key = None):
        if session_key is None:
            session_key = cherrypy.request.user.lastfm_session_key

        try:
            network = self.get_network(session_key)

            artists = {}

            for artist in network.get_library_artists(user_name, 1000):
                artists[artist['name'].lower()] = artist

            user = network.get_user_info(user_name)

            return {
                'artists': artists,
                'url': user['url'],
                'playcount': int(user['playcount']),
                'top_artists_overall': network.get_user_top_artists(user_name, 'overall', 1, 500),
                'top_albums_overall': network.get_user_top_albums(user_name, 'overall', 1, 500)
            }
        except LastfmError as error:
            log('Failed to get user "%s": %s.' % (
                user_name,
                error
            ))

    def _param_call(self, object, method, params, args):
        """
        hacky hack to send extra params to lastfm api
        """

        prev_get_params = object._get_params

        def _get_params():
            _params = prev_get_params()
            params.update(_params)
            return params

        object._get_params = _get_params

        ret = getattr(object, method)(*args)

        object._get_params = prev_get_params

        return ret

    def get_track(self, artist_name, track_name):
        try:
            network = self.get_network()
            track = network.get_track_info(artist_name, track_name)
            tags = network.get_track_top_tags(artist_name, track_name)

            return {
                'url': track['url'],
                'listeners': track['listeners'],
                'playcount': track['playcount'],
                'wiki': track['wiki'],
                'name': track['name'],
                'tags': tags[0:20],
            }
        except LastfmError as error:
            log('Failed to get track "%s - %s": %s' % (
                artist_name,
                track_name,
                error
            ))

    def get_album(self, artist_name, album_name):
        try:
            network = self.get_network()
            album = network.get_album_info(artist_name, album_name)
            tags = network.get_album_top_tags(artist_name, album_name)

            return {
                'url': album['url'],
                'listeners': album['listeners'],
                'playcount': album['playcount'],
                'wiki': album['wiki'],
                'name': album['name'],
                'tags': tags[0:20],
                'cover': album['cover']
            }
        except LastfmError as error:
            log('Failed to get album "%s - %s": %s' % (
                artist_name,
                album_name,
                error
            ))

    def get_tag(self, tag_name, limit = 50, page = 1):
        try:
            network = self.get_network()

            artists = network.get_tag_top_artists(tag_name, page, limit)
            albums = network.get_tag_top_albums(tag_name, page, limit)

            return {
                'artists': artists,
                'albums': albums
            }
        except LastfmError as error:
            log('Failed to get tag "%s": %s' % (
                tag_name,
                error
            ))

    def get_artist(self, artist_name):
        try:
            network = self.get_network()
            artist = network.get_artist_info(artist_name)

            similars = []

            count = 0

            for similar in network.get_artist_similar(artist_name, 100):
                name = similar['name']

                results = search.query_artist(name, exact=True)

                if len(results) > 0:
                    similars.append({
                        'name': results[0].name,
                        'slug': results[0].slug,
                    })

                    count += 1

                if count >= 20:
                    break

            tags = network.get_artist_top_tags(artist_name)

            return {
                'url': artist['url'],
                'bio': artist['bio'],
                'cover': artist['cover'],
                'listeners': artist['listeners'],
                'tags': tags[0:20],
                'similar': similars
            }
        except LastfmError as error:
            log('Failed to get artist "%s": %s' % (
                artist_name,
                error
            ))


class SessionKey:

    def __init__(self):
        self.network = lastfm.get_network()
        self.token = self.network.get_auth_token()
        self.auth_url = self.network.get_web_auth_url(self.token)

    def get_auth_url(self):
        return self.auth_url

    def get_session_key(self):
        key = None

        try:
            key = self.network.get_auth_session(self.token)['key']
        except LastfmError as e:
            log("session key failed: %s" % e)

        return key


lastfm = Lastfm()
