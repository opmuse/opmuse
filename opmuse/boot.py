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
from opmuse.security import User, repozewho_pipeline, AuthenticatedTool, AuthorizeTool
from opmuse.transcoding import FFMPEGTranscoderSubprocessTool
from opmuse.jinja import Jinja, JinjaEnvTool, JinjaPlugin, JinjaAuthenticatedTool
from opmuse.search import WhooshPlugin
from opmuse.utils import cgitb_log_err_tool, multi_headers_tool, LessReloader
from opmuse.ws import WebSocketPlugin, WebSocketHandler, WebSocketTool
from opmuse.bgtask import BackgroundTaskQueue
import opmuse.cache

tempfile.tempdir = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'cache', 'upload'
))


def configure():
    cherrypy.tools.jinja = Jinja()
    cherrypy.tools.database = SqlAlchemyTool()
    cherrypy.tools.authenticated = AuthenticatedTool()
    cherrypy.tools.authorize = AuthorizeTool()
    cherrypy.tools.jinjaauthenticated = JinjaAuthenticatedTool()
    cherrypy.tools.library = LibraryTool()
    cherrypy.tools.jinjaenv = JinjaEnvTool()
    cherrypy.tools.transcodingsubprocess = FFMPEGTranscoderSubprocessTool()
    cherrypy.tools.multiheaders = multi_headers_tool
    cherrypy.tools.cgitb_log_err = cgitb_log_err_tool
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
            'tools.library.on': True,
            'tools.jinjaenv.on': True,
            'tools.authenticated.on': True,
        }, '/ws': {
            'tools.websocket.on': True,
            'tools.websocket.handler_cls': WebSocketHandler
        }, '/static': {
            'tools.jinjaauthenticated.on': False,
            'tools.database.on': False,
            'tools.staticdir.on': True,
            'tools.staticdir.dir': join(abspath(dirname(__file__)),
                                        '..', 'public_static'),
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

    config['error_page.default'] = opmuse.controllers.Root.handle_error

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
    LessReloader(cherrypy.engine).subscribe()

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


if __name__ == '__main__':
    locale.setlocale(locale.LC_ALL, 'en_US.utf8')

    import argparse

    parser = argparse.ArgumentParser(description='opmuse')
    parser.add_argument('-d', '--daemon', action='store_true', help='Run as daemon')
    parser.add_argument('-p', '--profile', action='store_true', help='Run repoze.profile, access it at /__profile__')
    parser.add_argument('-l', '--log', action='store', help='Log file location.')
    parser.add_argument('-le', '--errorlog', action='store', help='Log error messages in this separate file.')
    parser.add_argument('-u', '--user', action='store', help='When running as daemon, what user to run as.', default='nobody')
    parser.add_argument('-e', '--env', action='store', help='cherrypy environment.')
    parser.add_argument('-t', '--timers', action='store_true', help='log timing info for requests and queries.')
    parser.add_argument('-f', '--firepy', action='store_true', help='enable firephp logging through cherrypy.request.firepy().')

    args = parser.parse_args()

    app = configure()

    if args.timers:
        from opmuse.timers import timers_start_tool, timers_end_tool
        cherrypy.tools.timers_start = timers_start_tool
        cherrypy.tools.timers_end = timers_end_tool

        cherrypy.config.update({
            'tools.timers_start.on': True,
            'tools.timers_end.on': True,
        })

    if args.firepy:
        from opmuse.utils import firepy_start_tool, firepy_end_tool
        cherrypy.tools.firepy_start = firepy_start_tool
        cherrypy.tools.firepy_end = firepy_end_tool
        cherrypy.config.update({
            'tools.firepy_start.on': True,
            'tools.firepy_end.on': True,
        })

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
