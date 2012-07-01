import os, cherrypy
from opmuse.library import Library

class Styles(object):
    @cherrypy.expose
    def default(self, file):
        cherrypy.response.headers['Content-Type'] = 'text/css'

        path = os.path.join(os.path.abspath("."), "public", "styles")

        csspath = os.path.join(path, file)

        if os.path.exists(csspath):
            return cherrypy.lib.static.serve_file(csspath)

        ext = os.path.splitext(file)
        lesspath = os.path.join(path, "%s%s" % (ext[0], ".less"))

        if os.path.exists(lesspath):
            from lesscpy.lessc import parser
            p = parser.LessParser()
            p.parse(
                filename=lesspath,
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
    @cherrypy.tools.jinja(filename='library.html')
    def library(self):
        library = Library(cherrypy.config['opmuse']['library.path'])

        return {'tracks': library.getTracks()}

    @cherrypy.expose
    def stream(self):
        return cherrypy.lib.static.serve_file(
            os.path.join(os.path.abspath("."), "data", "sample.ogg"),
            'audio/ogg'
        )

