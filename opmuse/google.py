import json
import urllib.parse
import urllib.request
from opmuse.remotes import remotes


class Google:
    IMAGES_URL = 'http://ajax.googleapis.com/ajax/services/search/images?v=1.0&%s'

    def get_album_images(self, album):
        remotes_album = remotes.get_album(album)

        tags = self._tags(remotes_album)

        if len(album.artists) > 0:
            artist = album.artists[0]
            name = '"%s" AND "%s"' % (artist.name, album.name)
        else:
            name = '"%s"' % album.name

        query = self._query(name, tags)

        return self.images(query)

    def get_artist_images(self, artist):
        remotes_artist = remotes.get_artist(artist)

        tags = self._tags(remotes_artist)

        query = self._query('"%s"' % artist.name, tags)

        return self.images(query)

    def _tags(self, remotes_entity):
        tags = []

        if remotes_entity is not None and remotes_entity['lastfm'] is not None:
            for tag_name in remotes_entity['lastfm']['tags']:
                tags.append(tag_name)

                if len(tags) == 3:
                    break

        return tags

    def _query(self, name, tags):
        query = '%s' % name

        if len(tags) > 0:
            query += ' AND "%s"' % '" OR "'.join(tags)

        return query

    def images(self, query):
        url = Google.IMAGES_URL % urllib.parse.urlencode({
            'q': query
        })

        results = json.loads(urllib.request.urlopen(url).read().decode("utf8", "replace"))

        urls = []

        if results is not None and results['responseData'] is not None:
            for hit in results['responseData']['results']:
                urls.append(hit['url'])

        return urls


google = Google()
