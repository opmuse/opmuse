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

import datetime
import cherrypy
from opmuse.remotes import remotes
from opmuse.queues import queue_dao
from opmuse.transcoding import transcoding


class Play:
    STREAM_PLAYING = {}
    STREAM_MODE = {}

    def __init__(self):
        cherrypy.engine.subscribe('transcoding.end', self.transcoding_end)
        cherrypy.engine.subscribe('transcoding.start', self.transcoding_start)

    def transcoding_start(self, transcoder, track):
        if 'User-Agent' not in cherrypy.request.headers:
            return

        Play.STREAM_PLAYING[cherrypy.request.user.id] = cherrypy.request.headers['User-Agent']

    def transcoding_end(self, track, transcoder):
        Play.STREAM_PLAYING[cherrypy.request.user.id] = None

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    def mode(self, mode):
        if mode not in ('regular', 'random'):
            raise cherrypy.HTTPError(status=409)

        user = cherrypy.request.user

        Play.STREAM_MODE[user.id] = mode

    @cherrypy.expose
    @cherrypy.tools.session_query_string()
    @cherrypy.tools.transcodingsubprocess()
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.config(**{'response.stream': True})
    def stream(self, **kwargs):

        user = cherrypy.request.user

        user.active = datetime.datetime.now()

        remotes.update_user(user)

        if 'dead' in kwargs and kwargs['dead'] == 'true':
            raise cherrypy.HTTPError(status=503)

        if 'User-Agent' in cherrypy.request.headers:
            user_agent = cherrypy.request.headers['User-Agent']
        else:
            user_agent = None

        # allow only one streaming client at once, or weird things might occur
        if (user.id in Play.STREAM_PLAYING and Play.STREAM_PLAYING[user.id] is not None and
                Play.STREAM_PLAYING[user.id] != user_agent):
            raise cherrypy.HTTPError(status=503)

        if user.id in Play.STREAM_MODE and Play.STREAM_MODE[user.id] is not None:
            mode = Play.STREAM_MODE[user.id]
        else:
            mode = 'regular'

        if mode == "random":
            track = queue_dao.get_random_track(user.id)
            current_seconds = 0
        else:
            queue = queue_dao.get_next(user.id)

            if queue is not None:
                track = queue.track
                current_seconds = queue.current_seconds
            else:
                track = None

        if track is None:
            raise cherrypy.HTTPError(status=409)

        transcoder, format = transcoding.determine_transcoder(
            track,
            user_agent,
            [accept.value for accept in cherrypy.request.headers.elements('Accept')]
        )

        cherrypy.log(
            '%s is streaming "%s" in %s (original was %s) with "%s"' %
            (user.login, track, format, track.format, user_agent)
        )

        cherrypy.response.headers['Content-Type'] = format

        def track_generator():
            yield track, current_seconds

        return transcoding.transcode(track_generator(), transcoder)

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='play/opmuse.m3u')
    def opmuse_m3u(self):
        cherrypy.response.headers['Content-Type'] = 'audio/x-mpegurl'

        stream_ssl = cherrypy.request.app.config.get('opmuse').get('stream.ssl')

        if stream_ssl is False:
            scheme = 'http'
        else:
            scheme = cherrypy.request.scheme

        forwarded_host = cherrypy.request.headers.get('X-Forwarded-Host')

        if forwarded_host is not None:
            host = forwarded_host.split(",")[0].strip()
        else:
            host = cherrypy.request.headers.get('host')

        if stream_ssl is False:
            if ':' in host:
                host = host[:host.index(':')]

            host = '%s:%s' % (host, cherrypy.config['server.socket_port'])

        url = "%s://%s/play/stream?session_id=%s" % (scheme, host, cherrypy.session.id)

        filename = 'opmuse_%s.m3u' % cherrypy.request.user.login

        cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=%s' % filename

        return {'url': url}
