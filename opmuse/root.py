import os, cherrypy
from lesscpy.lessc import parser

class Styles(object):
    @cherrypy.expose
    def default(self, file):
        cherrypy.response.headers['Content-Type'] = 'text/css'

        p = parser.LessParser()
        p.parse(
            filename=os.path.join(os.path.abspath("."), "public", "styles", file),
            debuglevel=0
        )

        items = {
            'nl': '\n',
            'tab': '\t',
            'ws': ' ',
            'eb': '\n'
        }

        return ''.join([u.fmt(items) for u in p.result if u]).strip()

class Root(object):
    styles = Styles()

    @cherrypy.expose
    @cherrypy.tools.jinja(filename='index.html')
    def index(self):
        return { }

    @cherrypy.expose
    def stream(self):
        return cherrypy.lib.static.serve_file(
            os.path.join(os.path.abspath("."), "data", "sample.ogg"),
            'audio/ogg'
        )

