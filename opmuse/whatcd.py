# Copyright 2012-2015 Mattias Fliesberg
#
# This file is part of opmuse.
#
# opmuse is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# opmuse is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with opmuse.  If not, see <http://www.gnu.org/licenses/>.


import cherrypy
from urllib.request import Request, urlopen, build_opener, HTTPCookieProcessor
from urllib.parse import urlencode
from urllib.error import HTTPError
from http import cookiejar
import json
from pprint import pprint


class WhatcdError(Exception):
    pass


class Whatcd:
    USER_AGENT = 'opmuse'
    DOMAIN = 'ssl.what.cd'
    URL = "https://%s/%%s" % DOMAIN

    def __init__(self):
        self.cj = None

    def login(self):
        config = cherrypy.tree.apps[''].config['opmuse']

        if 'whatcd.user' in config and 'whatcd.password' in config:
            user = config['whatcd.user']
            password = config['whatcd.password']
        else:
            user = None
            password = None

        if user is None or password is None:
            raise WhatcdError('whatcd is not configured')

        data = urlencode({'username': user, 'password': password}).encode()

        response = self._request("login.php", data=data, login=False)

        if response.geturl() != Whatcd.URL % "index.php":
            raise WhatcdError('whatcd login failed')

    def search(self, query):
        response = self._request("ajax.php?action=browse&searchstr=%s" % query)

        data = json.loads(response.read().decode('utf8'))

        for result in data['response']['results']:
            if 'torrents' not in result:
                continue

            for torrent in result['torrents']:
                artists = []

                for artist in torrent['artists']:
                    artists.append(artist['name'])

                yield {
                    'artists': artists,
                    'name': result['groupName'],
                    'year': result['groupYear'],
                    'cover': result['cover'],
                    'size': torrent['size'],
                    'format': torrent['format'],
                    'encoding': torrent['encoding'],
                    'seeders': torrent['seeders'],
                    'leechers': torrent['leechers'],
                    'media': torrent['media'],
                }

    def _request(self, url, data=None, login=True):
        if self.cj is None:
            self.cj = cookiejar.CookieJar()

        url = Whatcd.URL % url

        opener = build_opener(HTTPCookieProcessor(self.cj))
        opener.addheaders = [('User-Agent', Whatcd.USER_AGENT)]

        if login:
            cookie = None

            if Whatcd.DOMAIN in self.cj._cookies and 'session' in self.cj._cookies[Whatcd.DOMAIN]['/']:
                cookie = self.cj._cookies[Whatcd.DOMAIN]['/']['session']

            if cookie is None or cookie.is_expired():
                self.login()

        return opener.open(url, data=data)


whatcd = Whatcd()
