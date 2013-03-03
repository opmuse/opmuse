import discogs_client
from discogs_client import HTTPError

discogs_client.user_agent = 'opmuse/DEV'


class Discogs:
    def get_artist(self, name):
        artist = {
            'aliases': []
        }

        try:
            discogs_artist = discogs_client.Artist(name)

            for alias in discogs_artist.aliases:
                artist['aliases'].append(alias.name)

        except HTTPError:
            pass

        return artist

discogs = Discogs()
