# Copyright 2012-2014 Mattias Fliesberg
#
# This file is part of opmuse.
#
# opmuse is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# opmuse is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with opmuse.  If not, see <http://www.gnu.org/licenses/>.

import os
import logging
import cherrypy
import locale
import sys
from opmuse.database_events import DatabaseEventsTool
from os.path import join, abspath, dirname, exists
from opmuse.library import LibraryPlugin, LibraryWatchdogPlugin, LibraryTool
from opmuse.database import SqlAlchemyPlugin, SqlAlchemyTool
from opmuse.security import repozewho_pipeline, AuthenticatedTool, AuthorizeTool
from opmuse.transcoding import FFMPEGTranscoderSubprocessTool
from opmuse.jinja import Jinja, JinjaEnvTool, JinjaPlugin, JinjaAuthenticatedTool
from opmuse.search import WhooshPlugin
from opmuse.utils import error_handler_tool, multi_headers_tool, LessReloader, get_staticdir
from opmuse.ws import WebSocketPlugin, WebSocketHandler, WebSocketTool
from opmuse.bgtask import BackgroundTaskPlugin, BackgroundTaskTool
from opmuse.cache import CachePlugin


def configure(config_file=None, environment=None):
    cherrypy.tools.database = SqlAlchemyTool()
    cherrypy.tools.authenticated = AuthenticatedTool()
    cherrypy.tools.jinja = Jinja()
    cherrypy.tools.jinjaenv = JinjaEnvTool()
    cherrypy.tools.jinjaauthenticated = JinjaAuthenticatedTool()
    cherrypy.tools.authorize = AuthorizeTool()
    cherrypy.tools.library = LibraryTool()
    cherrypy.tools.backgroundtask = BackgroundTaskTool()
    cherrypy.tools.transcodingsubprocess = FFMPEGTranscoderSubprocessTool()
    cherrypy.tools.multiheaders = multi_headers_tool
    cherrypy.tools.error_handler = error_handler_tool
    cherrypy.tools.websocket = WebSocketTool()
    cherrypy.tools.database_events = DatabaseEventsTool()

    from opmuse.controllers.main import Root

    if config_file is None:
        config_file = join(abspath(dirname(__file__)), '..', 'config', 'opmuse.ini')

    if config_file is not False and not exists(config_file):
        config_file = '/etc/opmuse/opmuse.ini'

    if config_file and not exists(config_file):
        print('Configuration is missing!')
        sys.exit(1)

    app_config = {
        '/': {
            'tools.error_handler.on': True,
            'tools.autovary.on': True,
            'tools.encode.on': False,
            'tools.database.on': True,
            'tools.jinjaauthenticated.on': True,
            'tools.library.on': True,
            'tools.backgroundtask.on': True,
            'tools.jinjaenv.on': True,
            'tools.authenticated.on': True,
            'tools.database_events.on': True,
        }, '/ws': {
            'tools.websocket.on': True,
            'tools.websocket.handler_cls': WebSocketHandler
        }, '/static': {
            'tools.jinjaauthenticated.on': False,
            'tools.database.on': False,
            'tools.staticdir.on': True,
            'tools.staticdir.dir': get_staticdir(),
            'tools.expires.on': False,
            'tools.expires.secs': 3600 * 24 * 30
        },
        '/library/upload/add': {
            'response.timeout': 3600
        },
        '/library/edit/submit': {
            'response.timeout': 3600
        },
    }

    if environment == "production":
        app_config['/static']['tools.expires.on'] = True

    app = cherrypy.tree.mount(Root(), '/', app_config)

    if config_file:
        app.merge(config_file)

    app.wsgiapp.pipeline.append(('repoze.who', repozewho_pipeline))

    if config_file is False:
        config = cherrypy._cpconfig.Config()
    else:
        config = cherrypy._cpconfig.Config(file=config_file)

    # 5 gigabyte file upload limit
    config['server.max_request_body_size'] = 1024 ** 3 * 5
    config['engine.timeout_monitor.frequency'] = 60 * 5

    config['error_page.default'] = Root.handle_error

    config['opmuse'] = {}
    config['opmuse']['cache.path'] = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'cache'))

    cherrypy.config.update(config)

    cherrypy._cpconfig.environments['production']['opmuse'] = {}
    cherrypy._cpconfig.environments['production']['opmuse']['jinja.auto_reload'] = False
    cherrypy._cpconfig.environments['production']['opmuse']['less_reloader.enable'] = False
    cherrypy._cpconfig.environments['production']['opmuse']['cache.path'] = '/var/cache/opmuse'

    # dont use the default server
    cherrypy.server.unsubscribe()

    cherrypy.server = None
    cherrypy.ssl_server = None

    # setup ssl/https server if enabled
    if 'ssl_server.enabled' in cherrypy.config and cherrypy.config['ssl_server.enabled']:
        ssl_socket_host = cherrypy.config.get('ssl_server.socket_host')
        ssl_socket_port = cherrypy.config.get('ssl_server.socket_port')
        ssl_certificate = cherrypy.config['ssl_server.ssl_certificate']
        ssl_private_key = cherrypy.config['ssl_server.ssl_private_key']

        if ssl_socket_host is None:
            ssl_socket_host = '127.0.0.1'

        if ssl_socket_port is None:
            ssl_socket_port = 8443

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
        ssl_server.bind_addr = (ssl_socket_host, ssl_socket_port)
        ssl_server.ssl_certificate = ssl_certificate
        ssl_server.ssl_private_key = ssl_private_key
        ssl_server.ssl_certificate_chain = ssl_certificate_chain
        ssl_server.subscribe()

        cherrypy.ssl_server = ssl_server

    # setup regular http server
    socket_host = cherrypy.config.get('server.socket_host')
    socket_port = cherrypy.config.get('server.socket_port')

    if socket_host is None:
        socket_host = '127.0.0.1'

    if socket_port is None:
        socket_port = 8080

    server = cherrypy._cpserver.Server()
    server.bind_addr = (socket_host, socket_port)
    server.subscribe()

    cherrypy.server = server

    WebSocketPlugin.start.priority = 80
    WebSocketPlugin(cherrypy.engine).subscribe()

    LessReloader(cherrypy.engine).subscribe()

    cherrypy.engine.database = SqlAlchemyPlugin(cherrypy.engine)
    cherrypy.engine.database.subscribe()

    cherrypy.engine.jinja = JinjaPlugin(cherrypy.engine)
    cherrypy.engine.jinja.subscribe()

    cherrypy.engine.library = LibraryPlugin(cherrypy.engine)
    cherrypy.engine.library.subscribe()

    cherrypy.engine.library_watchdog = LibraryWatchdogPlugin(cherrypy.engine)
    cherrypy.engine.library_watchdog.subscribe()

    cherrypy.engine.whoosh = WhooshPlugin(cherrypy.engine)
    cherrypy.engine.whoosh.subscribe()

    cherrypy.engine.cache = CachePlugin(cherrypy.engine)
    cherrypy.engine.cache.subscribe()

    cherrypy.engine.bgtask = BackgroundTaskPlugin(cherrypy.engine)
    cherrypy.engine.bgtask.subscribe()

    return app


def boot():
    # signal_handler logs in its subscribe() so we initialize
    # it here so logging and everything is initialized before
    if hasattr(cherrypy.engine, 'signal_handler'):
        cherrypy.engine.signal_handler.subscribe()

    cherrypy.engine.start()
    cherrypy.engine.block()


def main():
    locale.setlocale(locale.LC_ALL, 'en_US.utf8')

    import argparse

    parser = argparse.ArgumentParser(description='opmuse')

    parser.add_argument('-d', '--daemon', action='store_true',
                        help='Run as daemon')
    parser.add_argument('-pf', '--pidfile', action='store',
                        help='Path to pid file.')
    parser.add_argument('-p', '--profile', action='store_true',
                        help='Run repoze.profile, access it at /__profile__')
    parser.add_argument('-l', '--log', action='store',
                        help='Log file location.')
    parser.add_argument('-le', '--errorlog', action='store',
                        help='Log error messages in this separate file.')
    parser.add_argument('-ncl', '--nocolorlog', action='store_true',
                        help='Don\'t use colorlog even if it\'s installed.')
    parser.add_argument('-u', '--user', action='store',
                        help='When running as daemon, what user to run as.', default='nobody')
    parser.add_argument('-g', '--group', action='store',
                        help='When running as daemon, what group to run as.', default='nogroup')
    parser.add_argument('-e', '--env', action='store',
                        help='cherrypy environment.')
    parser.add_argument('-t', '--timers', action='store_true',
                        help='log timing info for requests and queries.')
    parser.add_argument('-f', '--firepy', action='store_true',
                        help='enable firephp logging through cherrypy.request.firepy() or the fp() builtin.')

    args = parser.parse_args()

    app = configure(environment=args.env)

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
    elif not args.nocolorlog:
        # use colorlog if found, it's in dev-requirements.txt
        # outputs access_log messages as white and error_log messags as blue
        try:
            from colorlog import ColoredFormatter

            cherrypy.config.update({
                'log.screen': False,
                'log.error_file': "",
                'log.access_file': ""
            })

            access_formatter = ColoredFormatter(
                "%(log_color)s%(levelname)s%(reset)s:%(white)s%(message)s%(reset)s"
            )

            access_handler = logging.StreamHandler(sys.stderr)
            access_handler.setFormatter(access_formatter)

            error_formatter = ColoredFormatter(
                "%(log_color)s%(levelname)s%(reset)s:%(blue)s%(message)s%(reset)s"
            )

            error_handler = logging.StreamHandler(sys.stderr)
            error_handler.setFormatter(error_formatter)

            cherrypy.log.error_log.addHandler(error_handler)
            cherrypy.log.access_log.addHandler(access_handler)
        except ImportError:
            pass

    if args.log is None and args.errorlog is not None:
        parser.error('--log needs to be set if --errorlog is used.')
    elif args.errorlog is not None:
        cherrypy.config.update({
            'log.error_file': args.errorlog,
        })

    if 'opmuse' in app.config and 'debug' in app.config['opmuse'] and app.config['opmuse']['debug']:
        cherrypy.log.error_log.setLevel(logging.DEBUG)

    if args.daemon:
        if os.getuid() != 0:
            parser.error('Needs to run as root when running as daemon.')

        from cherrypy.process.plugins import Daemonizer, DropPrivileges
        Daemonizer(cherrypy.engine).subscribe()
        DropPrivileges(cherrypy.engine, uid=args.user, gid=args.group, umask=0o026).subscribe()

    if args.pidfile is not None:
        from cherrypy.process.plugins import PIDFile
        PIDFile(cherrypy.engine, args.pidfile).subscribe()

    if args.profile:
        from opmuse.utils import profile_pipeline
        app.wsgiapp.pipeline.append(('profile', profile_pipeline))

    boot()


if __name__ == '__main__':
    main()
