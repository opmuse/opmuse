import cherrypy
from opmuse.cache import cache
from opmuse.lastfm import SessionKey, lastfm, LastfmError
from opmuse.remotes import remotes
from opmuse.messages import messages as messages_service
from opmuse.security import hash_password
from opmuse.utils import HTTPRedirect


class Settings:
    @cherrypy.expose
    @cherrypy.tools.jinja(filename='settings/index.html')
    @cherrypy.tools.authenticated(needs_auth=True)
    def default(self):
        user = cherrypy.request.user

        auth_url = new_auth = None
        need_config = False

        cache_key = 'settings_lastfm_session_key_%d' % cherrypy.request.user.id

        if user.lastfm_session_key is None:
            session_key = cache.get(cache_key)

            if session_key is not None:
                auth_url = session_key.get_auth_url()
                key = session_key.get_session_key()

                if key is not None:
                    cache.set(cache_key, None)
                    user.lastfm_session_key = key
                    user.lastfm_user = lastfm.get_authenticated_user_name()
                    auth_url = None
                    new_auth = True
            else:
                try:
                    session_key = SessionKey()
                    auth_url = session_key.get_auth_url()
                    cache.set(cache_key, session_key)
                except LastfmError:
                    need_config = True

        remotes.update_user(user)

        return {
            "user": user,
            'need_config': need_config,
            'auth_url': auth_url,
            'new_auth': new_auth
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    def submit(self, login = None, mail = None, password1 = None, password2 = None):

        user = cherrypy.request.user

        if mail == '':
            mail = None

        if password1 == '':
            password1 = None

        if password2 == '':
            password2 = None

        if mail is not None and user.mail != mail:
            user.mail = mail
            messages_service.success('Your mail was changed.')

        if password1 is not None and password2 is not None:
            if password1 != password2:
                messages_service.warning('The passwords do not match.')
            else:
                user.password = hash_password(password1, user.salt)
                messages_service.success('Your password was changed.')

        raise HTTPRedirect('/settings')
