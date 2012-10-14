import os
import cherrypy
from cherrypy.process.plugins import SimplePlugin
from cherrypy._cptools import HandlerWrapperTool
from jinja2 import Environment, FileSystemLoader
from urllib.parse import quote

def format_seconds(seconds):
    if seconds is not None:
        return "%02d:%02d" % divmod(seconds, 60)

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
        self.env.filters['urlencode'] = urlencode

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

        html = template.render(response_dict)
        html = html.encode('utf8', 'replace')

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
        cherrypy.request.jinja.globals['request'] = cherrypy.request

