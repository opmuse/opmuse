import os
import cherrypy
from json import dumps as json_dumps
from cherrypy.process.plugins import SimplePlugin
from cherrypy._cptools import HandlerWrapperTool
from jinja2 import Environment, FileSystemLoader
from urllib.parse import quote
import opmuse.pretty
import locale

def json(value):
    return json_dumps(value)

def format_number(number):
    return locale.format('%d', number, grouping=True)

def pretty_date(date):
    return opmuse.pretty.pretty_date(date)

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
    return quote(value)

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
        self.env.filters['json'] = json

    start.priority = 130

    def bind_jinja(self):
        return self.env

    def stop(self):
        self.env = None

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

        template = cherrypy.request.jinja.get_template(conf['filename'])

        template.globals['request'] = cherrypy.request
        template.globals['xhr'] = cherrypy.request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        html = template.render(response_dict)
        html = html.encode('utf8', 'replace')

        if 'text/html' == cherrypy.response.headers['Content-Type']:
            cherrypy.response.headers['Content-Type'] = 'text/html; charset=utf8'

        return html


class JinjaEnvTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.bind_jinja, priority=10)

    def bind_jinja(self):
        binds = cherrypy.engine.publish('bind_jinja')
        cherrypy.request.jinja = binds[0]


class JinjaGlobalsTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'before_handler',
                               self.start, priority=20)

    def start(self):
        cherrypy.request.jinja.globals['server_name'] = cherrypy.request.app.config['opmuse']['server_name']

