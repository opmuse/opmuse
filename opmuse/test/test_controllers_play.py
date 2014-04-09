from . import WebCase
from http.cookies import BaseCookie


class PlayTest(WebCase):
    setup_server = WebCase._opmuse_setup_server

    def _login(self):
        self.getPage('/login', method='POST', body='login=admin&password=admin')

        cookie = BaseCookie()
        cookie.load(self.cookies[0][1])

        return cookie['auth_tkt'].value.strip("\"")

    def test_opmuse_m3u(self):

        auth_tkt = self._login()

        self.getPage("/play/opmuse.m3u", headers=self.cookies)

        self.assertHeader('Content-Type', 'audio/x-mpegurl')
        self.assertMatchesBody('#EXTM3U')
        self.assertMatchesBody('http://127.0.0.1:54583/play/stream\?auth_tkt=%s' % auth_tkt)

    def test_stream(self):
        auth_tkt = self._login()

        self.getPage('http://127.0.0.1:54583/play/stream?auth_tkt=%s' % auth_tkt)

        # queue is empty
        self.assertStatus(409)
