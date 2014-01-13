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

import discogs_client
import cherrypy
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
