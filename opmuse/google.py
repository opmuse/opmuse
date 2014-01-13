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
import urllib.parse
import urllib.request
import os
import opmuse.remotes


class Google:
    IMAGES_URL = 'http://ajax.googleapis.com/ajax/services/search/images?v=1.0&%s'
    SEARCH_URL = 'https://ajax.googleapis.com/ajax/services/search/web?v=1.0&%s'

    def get_artist_search(self, artist):
        remotes_artist = opmuse.remotes.remotes.get_artist(artist)

        tags = self._tags(remotes_artist)

        query = self._query('"%s"' % artist.name, tags)

        return self.search("-discogs.com -wikipedia.org -last.fm %s" % query)

    def get_album_images(self, album):
        remotes_album = opmuse.remotes.remotes.get_album(album)

        tags = self._tags(remotes_album)

        if len(album.artists) > 0:
            artist = album.artists[0]
            name = '"%s" AND "%s"' % (artist.name, album.name)
        else:
            name = '"%s"' % album.name

        query = self._query(name, tags)

        return self.images(query)

    def get_artist_images(self, artist):
        remotes_artist = opmuse.remotes.remotes.get_artist(artist)

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

    def search(self, query):
        url = Google.SEARCH_URL % urllib.parse.urlencode({
            'q': query
        })

        results = json.loads(urllib.request.urlopen(url).read().decode("utf8", "replace"))

        hits = []

        if results is not None and results['responseData'] is not None:
            for hit in results['responseData']['results']:
                hits.append({
                    'content': hit['content'],
                    'url': hit['url'],
                    'title': hit['titleNoFormatting'],
                    'visible_url': hit['visibleUrl'],
                })

        return hits

    def images(self, query):
        url = Google.IMAGES_URL % urllib.parse.urlencode({
            'q': query
        })

        results = json.loads(urllib.request.urlopen(url).read().decode("utf8", "replace"))

        urls = []

        if results is not None and results['responseData'] is not None:
            for hit in results['responseData']['results']:
                path = urllib.parse.urlparse(hit['url']).path
                ext = os.path.splitext(path)[1].lower()[1:]

                if ext in ['gif', 'png', 'jpg']:
                    urls.append(hit['url'])

        return urls


google = Google()
