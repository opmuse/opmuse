import sys
import os

VENDOR = os.path.join(os.path.dirname(__file__), '..', 'vendor')
sys.path.append(os.path.join(VENDOR, 'WhooshAlchemy'))

import cherrypy
from os.path import join, abspath, dirname
from opmuse.jinja import Jinja, env
from opmuse.library import LibraryPlugin
from opmuse.database import SqlAlchemyPlugin, SqlAlchemyTool
from opmuse.who import User, repozewho_pipeline, AuthenticatedTool, JinjaAuthenticatedTool
from opmuse.transcoding import TranscodingSubprocessTool
from opmuse.jinja import JinjaGlobalsTool
from opmuse.search import WhooshPlugin
import opmuse.lastfm

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

def configure():
    cherrypy.tools.jinja = Jinja()
    cherrypy.tools.database = SqlAlchemyTool()
    cherrypy.tools.authenticated = AuthenticatedTool()
    cherrypy.tools.jinjaauthenticated = JinjaAuthenticatedTool()
    cherrypy.tools.jinjaglobals = JinjaGlobalsTool()
    cherrypy.tools.transcodingsubprocess = TranscodingSubprocessTool()
    cherrypy.tools.multiheaders = cherrypy.Tool('on_end_resource', multi_headers)
    import opmuse.controllers

    config_file = join(abspath(dirname(__file__)), '..', 'config', 'opmuse.ini')

    app_config = {
        '/': {
            'tools.encode.on': True,
            'tools.encode.encoding': 'utf-8',
            'tools.database.on': True,
            'tools.sessions.on': True,
            'tools.jinjaauthenticated.on': True,
            'tools.jinjaglobals.on': True,
            'tools.sessions.storage_type': "file",
            'tools.sessions.storage_path': join(abspath(dirname(__file__)),
                                            '..', 'cache', 'session'),
            'tools.sessions.locking': "explicit",
            'tools.sessions.persistent': False,
            'tools.sessions.httponly': True,
        }, '/scripts': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': join(abspath(dirname(__file__)),
                                        '..', 'public', 'scripts'),
        },
        '/images': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': join(abspath(dirname(__file__)),
                                        '..', 'public', 'images'),
        },
    }

    app = cherrypy.tree.mount(opmuse.controllers.Root(), '/', app_config)

    app.merge(config_file)

    app.wsgiapp.pipeline.append(('repoze.who', repozewho_pipeline))

    cherrypy.engine.database = SqlAlchemyPlugin(cherrypy.engine)
    cherrypy.engine.database.subscribe()

    cherrypy.engine.library = LibraryPlugin(cherrypy.engine)
    cherrypy.engine.library.subscribe()

    cherrypy.engine.whoosh = WhooshPlugin(cherrypy.engine)
    cherrypy.engine.whoosh.subscribe()

    config = cherrypy._cpconfig.Config(file=config_file)
    cherrypy.config.update(config)

    env.globals['server_name'] = app.config['opmuse']['server_name']

def boot():
    cherrypy.engine.start()
    cherrypy.engine.block()

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='opmuse')
    parser.add_argument('-d', '--daemon', action='store_true', help='Run as daemon')
    parser.add_argument('-l', '--log', action='store', help='Log file location.')
    parser.add_argument('-u', '--user', action='store', help='When running as daemon, what user to run as.', default='nobody')
    parser.add_argument('-e', '--env', action='store', help='cherrypy environment.')

    args = parser.parse_args()

    configure()

    if args.env is not None:
        cherrypy.config.update({
            'environment': args.env
        })

    if args.log is not None:
        cherrypy.config.update({
            'log.screen': False,
            'log.error_file': args.log,
            'log.access_file': args.log
        })

    if args.daemon:
        if os.getuid() != 0:
            parser.error('Needs to run as root when running as daemon.')

        from cherrypy.process.plugins import Daemonizer, DropPrivileges
        Daemonizer(cherrypy.engine).subscribe()
        DropPrivileges(cherrypy.engine, uid=args.user).subscribe()

    boot()

