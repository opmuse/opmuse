import os
import cherrypy
from opmuse.covers import covers


class Cover:
    @cherrypy.expose
    @cherrypy.tools.expires(secs=3600 * 24 * 30, force=True)
    @cherrypy.tools.authenticated(needs_auth=True)
    def default(self, type, slug, hash = None, refresh = None, size="default"):
        try:
            mime, cover = covers.get_cover(type, slug, size)
        except ValueError:
            raise cherrypy.NotFound()

        if cover is None:
            cherrypy.response.headers['Content-Type'] = 'image/png'

            if size == "large":
                placeholder = 'cover_large_placeholder.png'
            else:
                placeholder = 'cover_placeholder.png'

            return cherrypy.lib.static.serve_file(os.path.join(
                os.path.abspath(os.path.dirname(__file__)),
                '..', 'public_static', 'images', placeholder
            ))
        else:
            cherrypy.response.headers['Content-Type'] = mime

            return cover

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.authorize(roles=['admin'])
    def refresh(self, type, slug):
        try:
            covers.refresh(type, slug)
        except ValueError:
            raise cherrypy.NotFound()

        return b''
