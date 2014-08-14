import datetime
import cherrypy
from opmuse.search import search
from opmuse.remotes import remotes
from opmuse.utils import HTTPRedirect
from opmuse.cache import cache
from opmuse.controllers.library import Library
from opmuse.library import library_dao


class Search:
    CACHE_RECENT_KEY = "search_recent"
    MAX_RECENT = 10

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.json_out()
    def api(self, type, query):
        if type == "artist":
            entities = search.query_artist(query)
        elif type == "album":
            entities = search.query_album(query)
        elif type == "track":
            entities = search.query_track(query)
        else:
            raise cherrypy.NotFound()

        return [entity.name for entity in entities]

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='search/index.html')
    def default(self, query=None, type=None):
        artists = []
        albums = []
        tracks = []
        track_ids = []

        hierarchy = None

        album_track_ids = set()

        recent_searches = []

        if query is not None:
            albums = None
            tracks = None

            # only search for artists
            if type == 'artist':
                artists = search.query_artist(query, exact=True)
                albums = []
                tracks = []
            else:
                artists = search.query_artist(query)

            if albums is None:
                albums = search.query_album(query)

            if tracks is None:
                tracks = search.query_track(query)

            for artist in artists:
                remotes.update_artist(artist)

            for album in albums:
                remotes.update_album(album)

            for track in tracks:
                track_ids.append(track.id)
                remotes.update_track(track)

            entities = artists + albums + tracks

            if len(entities) == 1:
                for artist in artists:
                    raise HTTPRedirect('/%s' % artist.slug)
                for album in albums:
                    raise HTTPRedirect('/%s/%s' % (album.artists[0].slug, album.slug))
                for track in tracks:
                    raise HTTPRedirect('/library/track/%s' % track.slug)

            if cache.has(Search.CACHE_RECENT_KEY):
                recent_searches = cache.get(Search.CACHE_RECENT_KEY)
            else:
                cache.set(Search.CACHE_RECENT_KEY, recent_searches)

            if type is None and len(entities) > 0:
                if len(recent_searches) == 0 or query != recent_searches[0][0]:
                    recent_searches.insert(0, (query, datetime.datetime.now(), cherrypy.request.user.login))

                    if len(recent_searches) > Search.MAX_RECENT:
                        recent_searches.pop()

            entities = sorted(entities, key=lambda entity: entity._SEARCH_SCORE, reverse=True)

            hierarchy = Library._produce_track_hierarchy(entities)

            for key, result_artist in hierarchy['artists'].items():
                for key, result_album in result_artist['albums'].items():
                    for track_id in library_dao.get_track_ids_by_album_id(result_album['entity'].id):
                        album_track_ids.add(track_id)

        return {
            'query': query,
            'hierarchy': hierarchy,
            'tracks': tracks,
            'albums': albums,
            'artists': artists,
            'track_ids': track_ids,
            'album_track_ids': list(album_track_ids),
            'recent_searches': recent_searches
        }
