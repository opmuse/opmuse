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

import logging
import cherrypy
import time
import traceback
import os
import threading
from sqlalchemy import event
from sqlalchemy.engine import Engine


# TODO we don't do any closing of these fds.
log_fds = {}


def debug(msg):
    cherrypy.log.error(msg, context='timers', severity=logging.DEBUG)


def log_timers(msg):
    if hasattr(cherrypy.request, 'firepy'):
        cherrypy.request.firepy(msg)

    thread = threading.current_thread()
    logname = "%s.%d.timers.log" % (thread.name, thread.ident)

    if logname not in log_fds:
        logpath = os.path.join(os.path.dirname(__file__), '..', logname)
        log_fds[logname] = open(logpath, "w+")

    log_fds[logname].write(msg)
    log_fds[logname].write("\n")


@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()
    context._query_path = None

    log_timers("start query: %s" % statement)
    log_timers("%r" % (parameters, ))

    stack = traceback.extract_stack()

    for filepath, lineno, func, text in reversed(stack):
        path, filename = os.path.split(filepath)
        dirname = os.path.basename(path)

        if dirname == "opmuse" and filename != 'timers.py':
            path = os.path.join(dirname, filename)

            log_timers("%s:%d %s" % (path, lineno, text))

            context._query_path = path
            break


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - context._query_start_time

    if hasattr(cherrypy.request, '_timers_query_time'):
        cherrypy.request._timers_query_time += total

    if hasattr(cherrypy.request, '_timers_total_queries'):
        cherrypy.request._timers_total_queries += 1

    if context._query_path is not None and hasattr(cherrypy.request, '_timers_modules'):
        path = context._query_path

        if path not in cherrypy.request._timers_modules:
            cherrypy.request._timers_modules[path] = 0

        cherrypy.request._timers_modules[path] += total

    log_timers("end query, time: %f" % total)


def timers_start():
    cherrypy.request._timers_modules = {}
    cherrypy.request._timers_query_time = 0
    cherrypy.request._timers_total_queries = 0
    cherrypy.request._timers_total_time = time.time()


def timers_end():
    total_time = time.time() - cherrypy.request._timers_total_time
    total_queries = cherrypy.request._timers_total_queries
    query_time = cherrypy.request._timers_query_time

    log_timers("request ended: %f query time, %d queries, %f total time." %
               (query_time, total_queries, total_time))

    log_timers("modules' query times:")

    for path, path_time in cherrypy.request._timers_modules.items():
        log_timers("%s: %f" % (path, path_time))


timers_start_tool = cherrypy.Tool('on_start_resource', timers_start)
timers_end_tool = cherrypy.Tool('before_finalize', timers_end)
