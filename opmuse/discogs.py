import discogs_client
from discogs_client import HTTPError
from requests.exceptions import ConnectionError


discogs_client.user_agent = 'opmuse/DEV'


def log(msg):
    cherrypy.log(msg, context='discogs')


class Discogs:
    def get_artist(self, name):
        artist = {
            'aliases': []
        }

        try:
            discogs_artist = discogs_client.Artist(name)

            for alias in discogs_artist.aliases:
                artist['aliases'].append(alias.name)

        except (HTTPError, ConnectionError) as error:
            log("Failed to fetch artist: %s" % error)

        return artist


discogs = Discogs()
