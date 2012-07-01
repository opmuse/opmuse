import os
from cherrypy._cptools import HandlerWrapperTool
from jinja2 import Environment, FileSystemLoader
from urllib.parse import quote

env = Environment(
    loader=FileSystemLoader(os.path.join(os.path.abspath("."), "templates"))
)

# TODO this has been added in master
#       https://github.com/mitsuhiko/jinja2/commit/37303a86583eda14fb61b14b4922bdce073bce57
def urlencode(value):
    return quote(value)

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
        return template.render(response_dict)
