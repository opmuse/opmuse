import os
from cherrypy._cptools import HandlerWrapperTool
from jinja2 import Environment, FileSystemLoader
from urllib.parse import quote

env = Environment(
    loader=FileSystemLoader(os.path.join(os.path.abspath("."), "templates"))
)

def format_seconds(seconds):
    return "%02d:%02d" % divmod(seconds, 60)

# TODO this has been added in master
#       https://github.com/mitsuhiko/jinja2/commit/37303a86583eda14fb61b14b4922bdce073bce57
def urlencode(value):
    return quote(value)

env.filters['format_seconds'] = format_seconds
env.filters['urlencode'] = urlencode

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

        template = env.get_template(conf['filename'])

        html = template.render(response_dict)
        html = html.encode('utf8', 'replace').decode()

        return html
