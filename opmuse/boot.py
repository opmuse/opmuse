import cherrypy
from os.path import join, abspath, dirname
from opmuse.jinja import Jinja, env
from opmuse.library import LibraryPlugin
from opmuse.database import SqlAlchemyPlugin, SqlAlchemyTool

if __name__ == '__main__':
    cherrypy.tools.jinja = Jinja()
    cherrypy.tools.database = SqlAlchemyTool()
    import opmuse.controllers

    cherrypy.tree.mount(opmuse.controllers.Root(), '/', {
        '/': {
            'tools.database.on': True,
            'tools.sessions.on': True,
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
