import musicbrainzngs as mb

mb.set_useragent("opmuse", "DEV", "http://opmu.se/")

class Musicbrainz:
    def get_artist(self, artist_entity):
        result = mb.search_artists(artist=artist_entity.name, alias=artist_entity.name)

        artists = []

        # only use artists which match name exactly
        for _artist in result['artist-list']:
            artist_name = artist_entity.name.lower()

            aliases = []
            if 'alias-list' in _artist:
                for alias in _artist['alias-list']:
                    aliases.append(alias['alias'])
                    aliases.append(alias['sort-name'])

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

        relations = {}

        if 'url-relation-list' in artist:
            for url in artist['url-relation-list']:
                if url['type'] not in relations:
                    relations[url['type']] = []

                relations[url['type']].append(url['target'])

        country = None

        if 'country' in artist:
            country = artist['country']

        return {
            'id': artist['id'],
            'name': artist['name'],
            'aliases': aliases,
            'relations': relations,
            'country': country
        }

musicbrainz = Musicbrainz()
