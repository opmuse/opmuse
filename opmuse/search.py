import os
import cherrypy
from whooshalchemy import IndexService
from whoosh.filedb.fileindex import FileIndex
from whoosh.filedb.filestore import FileStorage
from pydispatch import dispatcher
from opmuse.library import Artist, Album, Track

indexdir = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'cache', 'index')
config = {"WHOOSH_BASE": indexdir}

index_service = IndexService(config=config)

class WhooshTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.start, priority=20)

    def start(self):
        index_service.register_class(Artist, cherrypy.request.database)
        index_service.register_class(Album, cherrypy.request.database)
        index_service.register_class(Track, cherrypy.request.database)

