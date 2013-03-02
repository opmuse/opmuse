import os
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


def profile_pipeline(app):
    from repoze.profile import ProfileMiddleware

    profile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cache', 'profile')

    return ProfileMiddleware(
        app,
        log_filename=os.path.join(profile_path, 'profile.log'),
        cachegrind_filename=os.path.join(profile_path, 'cachegrind.out'),
        discard_first_request=True,
        flush_at_shutdown=True,
        path='/__profile__',
        unwind=False,
    )
