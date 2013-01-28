import cherrypy
import json
import sys


class HTTPRedirect(cherrypy.HTTPRedirect):
    def set_response(self):
        if cherrypy.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response = cherrypy.serving.response
            response.headers['X-Opmuse-Location'] = json.dumps(self.urls)
        else:
            cherrypy.HTTPRedirect.set_response(self)


# http://tools.cherrypy.org/wiki/CGITB
def cgitb_log_err():
    import cgitb

    tb = cgitb.text(sys.exc_info())

    def set_tb():
        cherrypy.log(tb)

    cherrypy.request.hooks.attach('after_error_response', set_tb)
