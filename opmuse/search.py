import os
import cherrypy
from whooshalchemy import IndexService
from whoosh.filedb.fileindex import FileIndex
from whoosh.filedb.filestore import FileStorage
from pydispatch import dispatcher
from opmuse.library import Artist, Album, Track

indexdir = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'cache', 'index')
config = {"WHOOSH_BASE": indexdir}

class WhooshPlugin(cherrypy.process.plugins.SimplePlugin):

    def __init__(self, bus):
        cherrypy.process.plugins.SimplePlugin.__init__(self, bus)
        self.bus.subscribe("bind", self.bind)

    def bind(self, session):
        index_service = IndexService(session, config=config)
        index_service.register_class(Artist)
        index_service.register_class(Album)
        index_service.register_class(Track)


