import logging
import cherrypy
import time
import traceback
import os
from sqlalchemy import event
from sqlalchemy.engine import Engine


def debug(msg):
    cherrypy.log.error(msg, context='timers', severity=logging.DEBUG)


def log(msg):
    if hasattr(cherrypy.request, 'firepy'):
        cherrypy.request.firepy(msg)

    debug(msg)


@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()
    context._query_path = None

    log("start query: %s" % statement)
    log("%r" % (parameters, ))

    stack = traceback.extract_stack()

    for filepath, lineno, func, text in reversed(stack):
        path, filename = os.path.split(filepath)
        dirname = os.path.basename(path)

        if dirname == "opmuse" and filename != 'timers.py':
            path = os.path.join(dirname, filename)

            log("%s:%d %s" % (path, lineno, text))

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

    log("end query, time: %f" % total)


def timers_start():
    cherrypy.request._timers_modules = {}
    cherrypy.request._timers_query_time = 0
    cherrypy.request._timers_total_queries = 0
    cherrypy.request._timers_total_time = time.time()


def timers_end():
    total_time = time.time() - cherrypy.request._timers_total_time
    total_queries = cherrypy.request._timers_total_queries
    query_time = cherrypy.request._timers_query_time

    log("request ended: %f query time, %d queries, %f total time." %
        (query_time, total_queries, total_time))

    log("modules' query times:")

    for path, path_time in cherrypy.request._timers_modules.items():
        log("%s: %f" % (path, path_time))


timers_start_tool = cherrypy.Tool('on_start_resource', timers_start)
timers_end_tool = cherrypy.Tool('before_finalize', timers_end)
