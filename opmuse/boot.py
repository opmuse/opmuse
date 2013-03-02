import sys
import os
import logging
import subprocess
import cherrypy
import tempfile
import locale
from os.path import join, abspath, dirname
from opmuse.library import LibraryPlugin, LibraryTool
from opmuse.database import SqlAlchemyPlugin, SqlAlchemyTool
from opmuse.security import User, repozewho_pipeline, AuthenticatedTool, JinjaAuthenticatedTool
from opmuse.transcoding import FFMPEGTranscoderSubprocessTool
from opmuse.jinja import Jinja, JinjaGlobalsTool, JinjaEnvTool, JinjaPlugin
from opmuse.search import WhooshPlugin
from opmuse.utils import cgitb_log_err
from opmuse.ws import WebSocketPlugin, WebSocketHandler, WebSocketTool
from opmuse.lastfm import LastfmMonitor, LastfmTool
from opmuse.bgtask import BackgroundTaskQueue
import opmuse.cache

tempfile.tempdir = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'cache', 'upload'
))


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
    cherrypy.tools.library = LibraryTool()
    cherrypy.tools.jinjaenv = JinjaEnvTool()
    cherrypy.tools.transcodingsubprocess = FFMPEGTranscoderSubprocessTool()
    cherrypy.tools.multiheaders = cherrypy.Tool('on_end_resource', multi_headers)
    cherrypy.tools.cgitb_log_err = cherrypy.Tool('before_error_response', cgitb_log_err)
    cherrypy.tools.lastfm = LastfmTool()
    cherrypy.tools.websocket = WebSocketTool()
    import opmuse.controllers

    config_file = join(abspath(dirname(__file__)), '..', 'config', 'opmuse.ini')

    app_config = {
        '/': {
            'tools.cgitb_log_err.on': True,
            'tools.autovary.on': True,
            'tools.encode.on': False,
            'tools.database.on': True,
            'tools.jinjaauthenticated.on': True,
            'tools.jinjaglobals.on': True,
            'tools.library.on': True,
            'tools.jinjaenv.on': True,
            'tools.lastfm.on': True,
            'tools.sessions.storage_type': "file",
            'tools.sessions.storage_path': join(abspath(dirname(__file__)), '..', 'cache', 'session'),
            'tools.sessions.locking': "explicit",
            'tools.sessions.persistent': False,
            'tools.sessions.httponly': True,
        }, '/ws': {
            'tools.websocket.on': True,
            'tools.websocket.handler_cls': WebSocketHandler
        }, '/scripts': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': join(abspath(dirname(__file__)),
                                        '..', 'public', 'scripts'),
        }, '/users/you/lastfm': {
            'tools.sessions.on': True,
        }, '/font': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': join(abspath(dirname(__file__)),
                                        '..', 'public', 'font'),
        }, '/images': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': join(abspath(dirname(__file__)),
                                        '..', 'public', 'images'),
        },
        '/library/upload/add': {
            'response.timeout': 3600
        },
        '/library/edit/submit': {
            'response.timeout': 3600
        },
    }

    app = cherrypy.tree.mount(opmuse.controllers.Root(), '/', app_config)

    app.merge(config_file)

    app.wsgiapp.pipeline.append(('repoze.who', repozewho_pipeline))

    config = cherrypy._cpconfig.Config(file=config_file)

    # 5 gigabyte file upload limit
    config['server.max_request_body_size'] = 1024 ** 3 * 5
    config['engine.timeout_monitor.frequency'] = 60 * 5

    cherrypy.config.update(config)

    cherrypy._cpconfig.environments['production']['jinja.auto_reload'] = False

    if 'ssl_server.enabled' in cherrypy.config and cherrypy.config['ssl_server.enabled']:
        socket_host = cherrypy.config['ssl_server.socket_host']
        socket_port = cherrypy.config['ssl_server.socket_port']
        ssl_certificate = cherrypy.config['ssl_server.ssl_certificate']
        ssl_private_key = cherrypy.config['ssl_server.ssl_private_key']

        if 'ssl_server.ssl_certificate_chain' in cherrypy.config:
            ssl_certificate_chain = cherrypy.config['ssl_server.ssl_certificate_chain']
        else:
            ssl_certificate_chain = None

        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config')

        if not os.path.isabs(ssl_certificate):
            ssl_certificate = os.path.join(config_path, ssl_certificate)

        if not os.path.isabs(ssl_private_key):
            ssl_private_key = os.path.join(config_path, ssl_private_key)

        if ssl_certificate_chain is not None and not os.path.isabs(ssl_certificate_chain):
            ssl_certificate_chain = os.path.join(config_path, ssl_certificate_chain)

        ssl_server = cherrypy._cpserver.Server()
        ssl_server.bind_addr = (socket_host, socket_port)
        ssl_server.ssl_certificate = ssl_certificate
        ssl_server.ssl_private_key = ssl_private_key
        ssl_server.ssl_certificate_chain = ssl_certificate_chain
        ssl_server.subscribe()

    WebSocketPlugin(cherrypy.engine).subscribe()

    LastfmMonitor(cherrypy.engine).subscribe()

    cherrypy.engine.database = SqlAlchemyPlugin(cherrypy.engine)
    cherrypy.engine.database.subscribe()

    cherrypy.engine.jinja = JinjaPlugin(cherrypy.engine)
    cherrypy.engine.jinja.subscribe()

    cherrypy.engine.library = LibraryPlugin(cherrypy.engine)
    cherrypy.engine.library.subscribe()

    cherrypy.engine.whoosh = WhooshPlugin(cherrypy.engine)
    cherrypy.engine.whoosh.subscribe()

    cherrypy.engine.bgtask = BackgroundTaskQueue(cherrypy.engine)
    cherrypy.engine.bgtask.subscribe()

    if 'debug' in app.config['opmuse'] and app.config['opmuse']['debug']:
        cherrypy.log.error_log.setLevel(logging.DEBUG)

    return app


def boot():
    cherrypy.engine.start()
    cherrypy.engine.block()


def boot_lesswatch():
    lesswatch = join(abspath(dirname(__file__)), '..', 'lesswatch.sh')
    subprocess.Popen(lesswatch)

if __name__ == '__main__':
    locale.setlocale(locale.LC_ALL, 'en_US.utf8')

    import argparse

    boot_lesswatch()

    parser = argparse.ArgumentParser(description='opmuse')
    parser.add_argument('-d', '--daemon', action='store_true', help='Run as daemon')
    parser.add_argument('-p', '--profile', action='store_true', help='Run repoze.profile, access it at /__profile__')
    parser.add_argument('-l', '--log', action='store', help='Log file location.')
    parser.add_argument('-le', '--errorlog', action='store', help='Log error messages in this separate file.')
    parser.add_argument('-u', '--user', action='store', help='When running as daemon, what user to run as.', default='nobody')
    parser.add_argument('-e', '--env', action='store', help='cherrypy environment.')

    args = parser.parse_args()

    app = configure()

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

    if args.log is None and args.errorlog is not None:
        parser.error('--log needs to be set if --errorlog is used.')
    elif args.errorlog is not None:
        cherrypy.config.update({
            'log.error_file': args.errorlog,
        })

    if args.daemon:
        if os.getuid() != 0:
            parser.error('Needs to run as root when running as daemon.')

        from cherrypy.process.plugins import Daemonizer, DropPrivileges
        Daemonizer(cherrypy.engine).subscribe()
        DropPrivileges(cherrypy.engine, uid=args.user, umask=0o022).subscribe()

    if args.profile:
        from opmuse.utils import profile_pipeline
        app.wsgiapp.pipeline.append(('profile', profile_pipeline))

    boot()
