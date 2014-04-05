from . import WebCase


class MainTest(WebCase):
    setup_server = WebCase._opmuse_setup_server

    def test_login_redirect(self):
        self.getPage("/")
        self.assertHeader('Location', 'http://127.0.0.1:54583/login')
        self.getPage("/", headers=[('Referer', 'http://www.google.com/')])
        self.assertNoHeader('Location')

    def test_login(self):
        self.getPage('/login', method='POST', body='login=admin&password=admin')
        self.assertHeader('Location', 'http://127.0.0.1:54583/')
        self.assertHeaderMatches('Set-Cookie', 'auth_tkt="[0-9a-f]{40}admin!"')
        self.getPage('/', headers=self.cookies)
        # opmuseGlobals script tag
        self.assertMatchesBody('authenticated: true,')
        # on dashboard "You"
        self.assertMatchesBody('<strong>admin</strong>')

    def test_logout(self):
        self.getPage('/login', method='POST', body='login=admin&password=admin')
        self.getPage('/logout', headers=self.cookies)
        self.assertHeaderMatches('Set-Cookie', 'auth_tkt="INVALID"')
