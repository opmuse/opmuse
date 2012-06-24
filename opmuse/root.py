import cherrypy

class Root(object):
    @cherrypy.expose
    @cherrypy.tools.jinja(filename='index.html')
    def index(self):
        return { 'name': 'world' }

