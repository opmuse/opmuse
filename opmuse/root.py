import os, cherrypy

class Root(object):
    @cherrypy.expose
    @cherrypy.tools.jinja(filename='index.html')
    def index(self):
        return { 'name': 'world' }

    @cherrypy.expose
    def stream(self):
        return cherrypy.lib.static.serve_file(
            os.path.join(os.path.abspath("."), "data", "sample.ogg"),
            'audio/ogg'
        )

