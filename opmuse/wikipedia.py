# Copyright 2012-2014 Mattias Fliesberg
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

import json
import re
from urllib import request, parse


class Wikipedia():
    BASE_URL = 'http://%s.wikipedia.org'
    LANGUAGES = ['en', 'sv', 'de', 'es', 'it', 'fr', 'no', 'da', 'fi', 'ja', 'zh', 'ko']
    BASE_API_URL = '%s/w/api.php' % BASE_URL
    BASE_TITLE_URL = '%s/wiki' % BASE_URL

    def get_track(self, artist_name, album_name, track_name):
        articles = []

        for extract, language in self.find_extract(track_name, ['song'], Wikipedia.LANGUAGES):
            summary = extract['extract']
            title = extract['title']
            url = extract['url']

            articles.append({
                'language': language,
                'summary': summary,
                'title': title,
                'url': url
            })

        return articles

    def get_album(self, artist_name, album_name):
        articles = []

        if album_name is not None and re.sub('[^a-z]+', '', album_name.lower()) == 'selftitled':
            album_name = artist_name

        if album_name is not None and artist_name is not None:
            for extract, language in self.find_extract(album_name,
                                                       ['%s album' % artist_name, 'album', 'ep', 'soundtrack'],
                                                       Wikipedia.LANGUAGES):
                summary = extract['extract']
                title = extract['title']
                url = extract['url']

                articles.append({
                    'language': language,
                    'summary': summary,
                    'title': title,
                    'url': url
                })

        return articles

    def get_artist(self, artist_name):

        articles = []

        for extract, language in self.find_extract(artist_name, ['band', 'musician', 'singer', 'artist'],
                                                   Wikipedia.LANGUAGES):

            summary = extract['extract']
            title = extract['title']
            url = extract['url']

            articles.append({
                'language': language,
                'summary': summary,
                'title': title,
                'url': url
            })

        return articles

    def find_extract(self, name, types, languages):
        title_format = "%s (%s)"

        for language in languages:
            extract = None

            for type in types:
                extract = self.query_extracts(title_format % (name, type), language)

                if extract is not None:
                    break

            if extract is None:
                title = None

                for type in types:
                    title = self.opensearch(title_format % (name, type), language)

                    if title is not None:
                        break

                if title is None:
                    title = self.opensearch(name, language)

                if title is not None:
                    extract = self.query_extracts(title, language)

            if extract is None:
                extract = self.query_extracts(name, language)

            if extract is not None:
                yield extract, language

    def opensearch(self, query, language):
        response = self._request({
            "action": "opensearch",
            "search": query,
            "format": "json",
            "limit": 1
        }, language)

        if len(response) > 1 and len(response[1]) > 0:
            return response[1][0]
        else:
            return None

    def query_extracts(self, title, language):
        response = self._request({
            "action": "query",
            "prop": "extracts",
            "format": "json",
            "exsentences": 20,
            "titles": title,
            "redirects": ""
        }, language)

        response = response['query']['pages'].popitem()[1]

        if 'extract' in response:
            return {
                'extract': response['extract'],
                'title': response['title'],
                'url': self._to_url(response['title'], language)
            }
        else:
            return None

    def _to_url(self, title, language):
        return "%s/%s" % (Wikipedia.BASE_TITLE_URL % language, parse.quote(title))

    def _request(self, params, language):
        response = request.urlopen("%s?%s" % (Wikipedia.BASE_API_URL % language, parse.urlencode(params)))
        return json.loads(response.read().decode("utf8"))


wikipedia = Wikipedia()
