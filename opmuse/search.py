import os
import cherrypy
from whooshalchemy import IndexService
from whoosh.filedb.fileindex import FileIndex
from whoosh.filedb.filestore import FileStorage
from pydispatch import dispatcher
from opmuse.library import Track

indexdir = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'cache', 'index')

config = {"WHOOSH_BASE": indexdir}

def start_db_session(sender):
    create_index_service(sender)

dispatcher.connect(
    start_db_session,
    signal='start_db_session',
    sender=dispatcher.Any
)

def create_index_service(session):
    index_service = IndexService(config=config, session=session)
    index_service.register_class(Track)
    return index_service

class WhooshTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.start, priority=20)

    def start(self):
        index_service = create_index_service(cherrypy.request.database)

