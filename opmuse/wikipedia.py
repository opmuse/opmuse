import json
import re
from urllib import request, parse


class Wikipedia():
    BASE_URL = 'http://en.wikipedia.org'
    BASE_API_URL = '%s/w/api.php' % BASE_URL
    BASE_TITLE_URL = '%s/wiki' % BASE_URL

    def get_track(self, artist_name, album_name, track_name):
        extract = self.find_extract(track_name, ['song'])

        if extract is None:
            summary = ''
            title = ''
            url = ''
        else:
            summary = extract['extract']
            title = extract['title']
            url = extract['url']

        return {
            'summary': summary,
            'title': title,
            'url': url
        }

    def get_album(self, artist_name, album_name):
        extract = None

        if album_name is not None and re.sub('[^a-z]+', '', album_name.lower()) == 'selftitled':
            album_name = artist_name

        if album_name is not None and artist_name is not None:
            extract = self.find_extract(album_name, ['%s album' % artist_name, 'album', 'ep', 'soundtrack'])

            if extract is None:
                extract = self.find_extract('%s - %s' % (artist_name, album_name))

        if extract is None:
            summary = ''
            title = ''
            url = ''
        else:
            summary = extract['extract']
            title = extract['title']
            url = extract['url']

        return {
            'summary': summary,
            'title': title,
            'url': url
        }

    def get_artist(self, artist_name):

        extract = self.find_extract(artist_name, ['band', 'musician', 'singer'])

        if extract is None:
            summary = ''
            title = ''
            url = ''
        else:
            summary = extract['extract']
            title = extract['title']
            url = extract['url']

        return {
            'summary': summary,
            'title': title,
            'url': url
        }

    def find_extract(self, name, types = []):
        extract = None

        title_format = "%s (%s)"

        for type in types:
            extract = self.query_extracts(title_format % (name, type))

            if extract is not None:
                break

        if extract is None:
            title = None

            for type in types:
                title = self.opensearch(title_format % (name, type))

                if title is not None:
                    break

            if title is None:
                title = self.opensearch(name)

            if title is not None:
                extract = self.query_extracts(title)

        if extract is None:
            extract = self.query_extracts(name)

        return extract

    def opensearch(self, query):
        response = self._request({
            "action": "opensearch",
            "search": query,
            "format": "json",
            "limit": 1
        })

        if len(response) > 1 and len(response[1]) > 0:
            return response[1][0]
        else:
            return None

    def query_extracts(self, title):
        response = self._request({
            "action": "query",
            "prop": "extracts",
            "format": "json",
            "exsentences": 20,
            "titles": title,
            "redirects": ""
        })

        response = response['query']['pages'].popitem()[1]

        if 'extract' in response:
            return {
                'extract': response['extract'],
                'title': response['title'],
                'url': self._to_url(response['title'])
            }
        else:
            return None

    def _to_url(self, title):
        return "%s/%s" % (Wikipedia.BASE_TITLE_URL, parse.quote(title))

    def _request(self, params):
        response = request.urlopen("%s?%s" % (Wikipedia.BASE_API_URL, parse.urlencode(params)))
        return json.loads(response.read().decode("utf8"))


wikipedia = Wikipedia()
