import cherrypy
import sys
import logging
from io import StringIO
from repoze.who.middleware import PluggableAuthenticationMiddleware
from repoze.who.plugins.auth_tkt import AuthTktCookiePlugin
from repoze.who.plugins.htpasswd import HTPasswdPlugin
from repoze.who.plugins.redirector import RedirectorPlugin
from repoze.who.classifiers import default_request_classifier
from repoze.who.classifiers import default_challenge_decider
from opmuse.jinja import env

class AuthenticatedTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.start, priority=20)

    def start(self):
        if ('repoze.who.identity' not in cherrypy.request.wsgi_environ or
            not cherrypy.request.wsgi_environ.get('repoze.who.identity')):
            raise cherrypy.HTTPError(401)

class JinjaAuthenticatedTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.start, priority=20)

    def start(self):
        env.globals['authenticated'] = ('repoze.who.identity' in cherrypy.request.wsgi_environ and
            cherrypy.request.wsgi_environ.get('repoze.who.identity'))

def repozewho_pipeline(app):

    io = StringIO()
    salt = 'aa'
    for name, password in [('admin', 'admin')]:
        io.write('%s:%s\n' % (name, password))
    io.seek(0)
    def cleartext_check(password, hashed):
        return password == hashed

    htpasswd = HTPasswdPlugin(io, cleartext_check)
    redirector = RedirectorPlugin('/login')
    auth_tkt = AuthTktCookiePlugin('secret', 'auth_tkt')
    identifiers = [('auth_tkt', auth_tkt)]
    authenticators = [('auth_tkt', auth_tkt), ('htpasswd', htpasswd)]
    challengers = [('redirector', redirector)]
    mdproviders = []

    return PluggableAuthenticationMiddleware(
        app,
        identifiers,
        authenticators,
        challengers,
        mdproviders,
        default_request_classifier,
        default_challenge_decider,
        log_stream = sys.stdout,
        log_level = logging.DEBUG
    )

