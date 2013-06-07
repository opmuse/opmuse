import os
import cherrypy
import re
import random
import locale
from json import dumps as json_dumps
from cherrypy.process.plugins import SimplePlugin
from cherrypy._cptools import HandlerWrapperTool
from jinja2 import Environment, FileSystemLoader
from urllib.parse import quote
from opmuse.security import is_granted as _is_granted
from opmuse.pretty import pretty_date as _pretty_date
from opmuse.library import TrackStructureParser
from opmuse.queues import queue_dao

VISIBLE_WS = "\u2423"


def is_granted(role):
    return _is_granted([role])


def rand_id():
    return str(random.randrange(1, 99999))


def replace_ws(string):
    match = re.search('\S', string)

    if match is not None:
        index = match.start()
        return "%s%s" % (index * VISIBLE_WS, string[index:])
    else:
        return len(string) * VISIBLE_WS


def show_ws(string):
    """
    Helper for replacing trailing whitespace with the unicode visible space
    character
    """
    if string is None or len(string) == 0:
        return "[MISSING]"

    return replace_ws(replace_ws(string)[::-1])[::-1]


def replace_ws(string):
    match = re.search('\S', string)

    if match is not None:
        index = match.start()
        return "%s%s" % (index * "\u2423", string[index:])
    else:
        return len(string) * "\u2423"


def show_ws(string):
    """
    Helper for replacing trailing whitespace with the unicode visible space
    character
    """
    if string is not None:
        return replace_ws(replace_ws(string)[::-1])[::-1]

    return string


def format_bytes(bytes, precision=2):
    bytes = int(bytes)

    suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
    suffixIndex = 0

    while bytes > 1024:
        suffixIndex += 1
        bytes = bytes / 1024.0

    return "%.*f %s" % (precision, bytes, suffixes[suffixIndex])


def track_path(track, artist = None):
    track_structure = TrackStructureParser(track, data_override = {'artist': artist})
    path = track_structure.get_path()

    if path is not None:
        return path.decode('utf8')
    else:
        return ''


def startswith(value, start):
    return value.startswith(start)


def json(value):
    return json_dumps(value)


def format_number(number):
    return locale.format('%d', number, grouping=True)


def pretty_date(date):
    return _pretty_date(date)


def format_seconds(seconds):
    if seconds is None:
        seconds = 0

    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours > 0:
        string = "%02d:" % (hours, )
    else:
        string = ""

    return "%s%02d:%02d" % (string, minutes, seconds)


# TODO this has been added in master
#       https://github.com/mitsuhiko/jinja2/commit/37303a86583eda14fb61b14b4922bdce073bce57
def urlencode(value):
    if value is not None:
        return quote(value)
    else:
        return ''


class JinjaPlugin(SimplePlugin):

    def __init__(self, bus):
        SimplePlugin.__init__(self, bus)
        self.env = None
        self.bus.subscribe("bind_jinja", self.bind_jinja)

    def start(self):
        auto_reload = cherrypy.config.get('jinja.auto_reload')

        if auto_reload is None:
            auto_reload = True

        self.env = Environment(
            loader=FileSystemLoader(
                os.path.join(
                    os.path.abspath(os.path.dirname(__file__)),
                    '..', 'templates'
                )
            ),
            extensions=['jinja2.ext.loopcontrols'],
            auto_reload=auto_reload,
            cache_size=-1
        )

        self.env.filters['format_seconds'] = format_seconds
        self.env.filters['pretty_date'] = pretty_date
        self.env.filters['urlencode'] = urlencode
        self.env.filters['format_number'] = format_number
        self.env.filters['show_ws'] = show_ws
        self.env.filters['format_bytes'] = format_bytes
        self.env.filters['json'] = json
        self.env.filters['startswith'] = startswith
        self.env.filters['track_path'] = track_path

        self.env.globals['rand_id'] = rand_id
        self.env.globals['is_granted'] = is_granted

    start.priority = 130

    def bind_jinja(self):
        return self.env

    def stop(self):
        self.env = None


def render_template(filename, dictionary):
    template = cherrypy.request.jinja.get_template(filename)

    template.globals['request'] = cherrypy.request
    template.globals['xhr'] = cherrypy.request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    template.globals['current_url'] = cherrypy.url()

    # TODO UGLY, this can hopefully be removed when we get symfony-style {% render %} tags...
    if cherrypy.request.user is not None:
        template.globals['queues'] = queue_dao.get_queues(cherrypy.request.user.id)

    return template.render(dictionary)


class Jinja(HandlerWrapperTool):

    def __init__(self):
        HandlerWrapperTool.__init__(self, self.jinja)

    def callable(self, filename=None, *args, **kwargs):
        HandlerWrapperTool.callable(self)

    def jinja(self, next_handler, *args, **kwargs):
        response_dict = next_handler(*args, **kwargs)
        conf = self._merged_args()

        if 'filename' not in conf:
            raise Exception('No template filename specified!')

        html = render_template(conf['filename'], response_dict)

        if 'text/html' == cherrypy.response.headers['Content-Type']:
            cherrypy.response.headers['Content-Type'] = 'text/html; charset=utf8'

        return html.encode('utf8', 'replace')


class JinjaEnvTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.bind_jinja, priority=10)

    def bind_jinja(self):
        binds = cherrypy.engine.publish('bind_jinja')
        cherrypy.request.jinja = binds[0]


class JinjaAuthenticatedTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'before_handler',
                               self.start, priority=20)

    def start(self):
        cherrypy.request.jinja.globals['authenticated'] = False
        cherrypy.request.jinja.globals['user'] = None

        if hasattr(cherrypy.request, 'user') and cherrypy.request.user is not None:
            cherrypy.request.jinja.globals['user'] = cherrypy.request.user
            cherrypy.request.jinja.globals['authenticated'] = True
