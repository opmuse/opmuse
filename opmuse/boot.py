#!env python

import cherrypy
from os.path import join, abspath, dirname
from opmuse.jinja import Jinja

if __name__ == '__main__':
    cherrypy.tools.jinja = Jinja()
    import opmuse.root

    cherrypy.tree.mount(opmuse.root.Root(), '/', {
        '/': { },
        '/scripts': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': join(abspath(dirname(__file__)), "../public/scripts"),
        }
    })

    config = cherrypy._cpconfig.Config(file=join(abspath(dirname(__file__)), "../config/opmuse.ini"))
    cherrypy.config.update(config)

    cherrypy.engine.start()
    cherrypy.engine.block()
