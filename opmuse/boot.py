import cherrypy
import sys
import logging
from os.path import join, abspath, dirname
from opmuse.jinja import Jinja, env
from opmuse.library import LibraryPlugin
from opmuse.database import SqlAlchemyPlugin, SqlAlchemyTool
from opmuse.who import repozewho_pipeline, AuthenticatedTool, JinjaAuthenticatedTool

def multi_headers():
    if hasattr(cherrypy.response, 'multiheaders'):
        headers = []
        for header in cherrypy.response.multiheaders:
            new_header = tuple()
            for val in header:
                if isinstance(val, str):
                    val = val.encode()
                new_header += (val, )
            headers.append(new_header)
        cherrypy.response.header_list.extend(headers)

if __name__ == '__main__':
    cherrypy.tools.jinja = Jinja()
    cherrypy.tools.database = SqlAlchemyTool()
    cherrypy.tools.authenticated = AuthenticatedTool()
    cherrypy.tools.jinjaauthenticated = JinjaAuthenticatedTool()
    cherrypy.tools.multiheaders = cherrypy.Tool('on_end_resource', multi_headers)
    import opmuse.controllers

    app = cherrypy.tree.mount(opmuse.controllers.Root(), '/', {
        '/': {
            'tools.database.on': True,
            'tools.sessions.on': True,
            'tools.jinjaauthenticated.on': True,
            'tools.sessions.storage_type': "ram",
            'tools.sessions.locking': "explicit",
            'tools.sessions.timeout': 60 * 30,
        }, '/scripts': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': join(abspath(dirname(__file__)),
                                        "../public/scripts"),
        },
        '/images': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': join(abspath(dirname(__file__)),
                                        "../public/images"),
        },
    })

    app.wsgiapp.pipeline.append(('repoze.who', repozewho_pipeline))

    cherrypy.engine.database = SqlAlchemyPlugin(cherrypy.engine)
    cherrypy.engine.database.subscribe()

    cherrypy.engine.library = LibraryPlugin(cherrypy.engine)
    cherrypy.engine.library.subscribe()

    config = cherrypy._cpconfig.Config(file=join(abspath(dirname(__file__)),
                                                 "../config/opmuse.ini"))
    cherrypy.config.update(config)
    env.globals['server_name'] = cherrypy.config['opmuse']['server_name']

    cherrypy.engine.start()
    cherrypy.engine.block()
