#!env python

import cherrypy

if __name__ == '__main__':
    import opmuse.root

    cherrypy.tree.mount(opmuse.root.Root(), '/', {
        '/': {}
    })

    cherrypy.engine.start()
    cherrypy.engine.block()
