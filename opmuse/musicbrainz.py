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

import musicbrainzngs as mb
from musicbrainzngs.musicbrainz import ResponseError, NetworkError
import opmuse

mb.set_useragent("opmuse", opmuse.__version__, "http://opmu.se/")


class Musicbrainz:
    def get_album(self, album_entity):
        artistname = album_entity.artists[0].name if len(album_entity.artists) > 0 else None

        try:
            result = mb.search_releases(release=album_entity.name, artistname=artistname)
        except (ResponseError, NetworkError) as error:
            return None

        if len(result['release-list']) == 0:
            return None

        release = mb.get_release_by_id(result['release-list'][0]['id'],
                                       includes=['release-rels', 'url-rels'])['release']

        translit = None

        if 'release-relation-list' in release:
            for release_rel in release['release-relation-list']:
                if release_rel['type'] == 'transl-tracklisting':
                    translit = release_rel['release']['title']
                    break

        urls = {}

        if 'url-relation-list' in release:
            for url in release['url-relation-list']:
                if url['type'] not in urls:
                    urls[url['type']] = []

                urls[url['type']].append(url['target'])

        return {
            'id': release['id'],
            'translit': translit,
            'urls': urls
        }

    def get_artist(self, artist_entity):
        try:
            result = mb.search_artists(artist=artist_entity.name, alias=artist_entity.name)
        except ResponseError:
            return None

        artists = []

        # only use artists which match name exactly
        for _artist in result['artist-list']:
            artist_name = artist_entity.name.lower()

            aliases = []
            if 'alias-list' in _artist:
                for alias in _artist['alias-list']:
                    aliases.append(alias['alias'].lower())
                    aliases.append(alias['sort-name'].lower())

            if (_artist['name'].lower() != artist_name and _artist['sort-name'].lower() != artist_name and
                    artist_name not in aliases):
                continue

            artists.append(_artist)

        if len(artists) == 0:
            return None

        genres = set()

        for track in artist_entity.tracks:
            if track.genre is not None:
                genres.add(track.genre.lower())

        artist = None

        dates = []

        for album in artist_entity.albums:
            if album.date is not None:
                date = album.date[0:4]

                if len(date) == 4 and date.isdigit():
                    dates.append(int(date))

        dates = sorted(dates)

        if len(dates) > 0:
            first_date = dates[0]
        else:
            first_date = None

        if len(artists) == 1:
            artist = artists[0]
        else:
            # if we have more than one match we need to be a bit clever
            # to figure out which one is the right one.
            for _artist in artists:
                # if genre matches a tag on the mb artist
                if 'tag-list' in _artist:
                    for tag in _artist['tag-list']:
                        tag_name = tag['name'].lower()
                        for genre in genres:
                            if genre in tag_name or tag_name in genre:
                                artist = _artist
                                break
                        else:
                            continue
                        break
                    else:
                        continue
                    break

                # if genre matches the mb disambiguation
                if 'disambiguation' in _artist:
                    for genre in genres:
                        if genre in _artist['disambiguation']:
                            artist = _artist
                            break
                    else:
                        continue
                    break

                # if album is within or after the lifespan of the artist
                if 'life-span' in _artist:
                    life = _artist['life-span']

                    begin = end = None

                    if 'end' in life:
                        end = int(life['end'][0:4])

                    if 'begin' in life:
                        begin = int(life['begin'][0:4])

                    if begin is not None and end is not None:
                        if first_date is not None and first_date >= begin and first_date <= end:
                            artist = _artist
                            break
                    elif begin is not None:
                        if first_date is not None and first_date >= begin:
                            artist = _artist
                            break

        # if we failed to be smart just take the first one
        if artist is None:
            artist = artists[0]

        result = mb.get_artist_by_id(artist['id'], includes=['aliases', 'url-rels'])

        artist = result['artist']

        aliases = []

        if 'alias-list' in artist:
            for alias in artist['alias-list']:
                aliases.append(alias['alias'])

        urls = {}

        if 'url-relation-list' in artist:
            for url in artist['url-relation-list']:
                if url['type'] not in urls:
                    urls[url['type']] = []

                urls[url['type']].append(url['target'])

        country = None

        if 'country' in artist:
            country = artist['country']

        return {
            'id': artist['id'],
            'name': artist['name'],
            'aliases': aliases,
            'urls': urls,
            'country': country
        }

musicbrainz = Musicbrainz()
