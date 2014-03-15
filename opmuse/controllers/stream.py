import cherrypy
from opmuse.remotes import remotes
from opmuse.queues import queue_dao
from opmuse.transcoding import transcoding


class Stream:

    STREAM_PLAYING = {}

    def __init__(self):
        cherrypy.engine.subscribe('transcoding.end', self.transcoding_end)
        cherrypy.engine.subscribe('transcoding.start', self.transcoding_start)

    def transcoding_start(self, transcoder, track):
        if 'User-Agent' not in cherrypy.request.headers:
            return

        Stream.STREAM_PLAYING[cherrypy.request.user.id] = cherrypy.request.headers['User-Agent']

    def transcoding_end(self, track, transcoder):
        Stream.STREAM_PLAYING[cherrypy.request.user.id] = None

    @cherrypy.expose
    @cherrypy.tools.transcodingsubprocess()
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.config(**{'response.stream': True})
    def default(self, **kwargs):

        user = cherrypy.request.user

        remotes.update_user(user)

        if 'dead' in kwargs and kwargs['dead'] == 'true':
            raise cherrypy.HTTPError(status=503)

        user_agent = cherrypy.request.headers['User-Agent']

        # allow only one streaming client at once, or weird things might occur
        if (user.id in Stream.STREAM_PLAYING and Stream.STREAM_PLAYING[user.id] is not None and
            Stream.STREAM_PLAYING[user.id] != user_agent):
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

        return transcoding.transcode(track_generator(), transcoder)
