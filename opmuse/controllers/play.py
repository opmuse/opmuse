import datetime
import cherrypy
from repoze.who._compat import get_cookies
from opmuse.remotes import remotes
from opmuse.queues import queue_dao
from opmuse.transcoding import transcoding
from opmuse.ws import ws


class Play:
    STREAM_PLAYING = {}

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

        queue = queue_dao.get_next(user.id)

        if queue is None:
            raise cherrypy.HTTPError(status=409)

        transcoder, format = transcoding.determine_transcoder(
            queue.track,
            user_agent,
            [accept.value for accept in cherrypy.request.headers.elements('Accept')]
        )

        cherrypy.log(
            '%s is streaming "%s" in %s (original was %s) with "%s"' %
            (user.login, queue.track, format, queue.track.format, user_agent)
        )

        cherrypy.response.headers['Content-Type'] = format

        def track_generator():
            yield queue.track, queue.current_seconds

        #return transcoding.transcode(track_generator(), transcoder)

        for data in transcoding.transcode(track_generator(), transcoder):
            if data is None:
                continue

            ws.bemit(data)

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='play/opmuse.m3u')
    def opmuse_m3u(self):
        cherrypy.response.headers['Content-Type'] = 'audio/x-mpegurl'

        cookies = get_cookies(cherrypy.request.wsgi_environ)
        # TODO use "cookie_name" prop from authtkt plugin...
        auth_tkt = cookies.get('auth_tkt').value

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

        url = "%s://%s/play/stream?auth_tkt=%s" % (scheme, host, auth_tkt)

        cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=opmuse.m3u'

        return {'url': url}
