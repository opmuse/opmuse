#!env python

import os, cherrypy

from opmuse.jinja import Jinja

if __name__ == '__main__':
    cherrypy.tools.jinja = Jinja()
    import opmuse.root

    cherrypy.tree.mount(opmuse.root.Root(), '/', {
        '/': { },
        '/scripts': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': os.path.join(os.path.abspath("."), "public/scripts"),
        }
    })

    cherrypy.engine.start()
    cherrypy.engine.block()
