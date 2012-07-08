import cherrypy
from os.path import join, abspath, dirname
from opmuse.jinja import Jinja, env
from opmuse.library import LibraryPlugin

if __name__ == '__main__':
    cherrypy.tools.jinja = Jinja()
    import opmuse.root

    cherrypy.tree.mount(opmuse.root.Root(), '/', {
        '/': {
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

    cherrypy.engine.library = LibraryPlugin(cherrypy.engine)
    cherrypy.engine.library.subscribe()

    config = cherrypy._cpconfig.Config(file=join(abspath(dirname(__file__)),
                                                 "../config/opmuse.ini"))
    cherrypy.config.update(config)
    env.globals['server_name'] = cherrypy.config['opmuse']['server_name']

    cherrypy.engine.start()
    cherrypy.engine.block()
