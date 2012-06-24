#!env python

import cherrypy

from opmuse.jinja import Jinja

if __name__ == '__main__':
    cherrypy.tools.jinja = Jinja()
    import opmuse.root

    cherrypy.tree.mount(opmuse.root.Root(), '/', {
        '/': { }
    })

    cherrypy.engine.start()
    cherrypy.engine.block()
