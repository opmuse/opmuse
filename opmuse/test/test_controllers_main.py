from . import WebCase
from http.cookies import BaseCookie


class MainTest(WebCase):
    setup_server = WebCase._opmuse_setup_server

    def _login(self):
        self.getPage('/login', method='POST', body='login=admin&password=admin')

        cookie = BaseCookie()
        cookie.load(self.cookies[0][1])

        return cookie['session_id'].value

    def test_login_redirect(self):
        self.getPage("/")
        self.assertHeader('Location', 'http://127.0.0.1:54583/login')
        self.getPage("/", headers=[('Referer', 'http://www.google.com/')])
        self.assertNoHeader('Location')

    def test_login(self):
        self._login()
        self.assertHeader('Location', 'http://127.0.0.1:54583/')
        self.assertHeaderMatches('Set-Cookie', 'session_id=[0-9a-f]{40}')
        self.getPage('/', headers=self.cookies)
        # opmuseGlobals script tag
        self.assertMatchesBody('authenticated: true,')
        # on dashboard "You"
        self.assertMatchesBody('<strong>admin</strong>')

    def test_logout(self):
        self._login()
        self.getPage('/logout', headers=self.cookies)
        self.getPage('/login', headers=self.cookies)
        # opmuseGlobals script tag
        self.assertMatchesBody('authenticated: false,')

    def test_opmuse_m3u(self):
        session_id = self._login()

        self.getPage("/play/opmuse.m3u", headers=self.cookies)

        self.assertHeader('Content-Type', 'audio/x-mpegurl')
        self.assertMatchesBody('#EXTM3U')
        self.assertMatchesBody('http://127.0.0.1:54583/play/stream\?session_id=%s' % session_id)

    def test_stream(self):
        session_id = self._login()

        self.getPage('http://127.0.0.1:54583/play/stream?session_id=%s' % session_id)

        # queue is empty
        self.assertStatus(409)
