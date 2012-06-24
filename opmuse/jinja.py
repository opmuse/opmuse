import os
from cherrypy._cptools import HandlerWrapperTool
from jinja2 import Environment, FileSystemLoader

env = Environment(
    loader=FileSystemLoader(os.path.join(os.path.abspath("."), "templates"))
)

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
