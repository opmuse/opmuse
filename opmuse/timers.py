import logging
import cherrypy
import time
import traceback
import os
from sqlalchemy import event
from sqlalchemy.engine import Engine


def debug(msg):
    cherrypy.log.error(msg, context='timers', severity=logging.DEBUG)


def log(msg, include_stack=False):
    stack_msg = None

    if include_stack:
        stack = traceback.extract_stack()

        for filepath, lineno, func, text in reversed(stack):
            path, filename = os.path.split(filepath)
            dirname = os.path.basename(path)

            if dirname == "opmuse" and filename != 'timers.py':
                stack_msg = "%s/%s:%d %s" % (dirname, filename, lineno, text)
                break

    if hasattr(cherrypy.request, 'firepy'):
        cherrypy.request.firepy(msg)

        if stack_msg is not None:
            cherrypy.request.firepy(stack_msg)

    debug(msg)

    if stack_msg is not None:
        debug(stack_msg)

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()
    log("start query: %s" % statement, include_stack=True)


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - context._query_start_time

    if hasattr(cherrypy.request, '_timers_query_time'):
        cherrypy.request._timers_query_time += total

    if hasattr(cherrypy.request, '_timers_total_queries'):
        cherrypy.request._timers_total_queries += 1

    log("end query, time: %f" % total)


def timers_start():
    cherrypy.request._timers_query_time = 0
    cherrypy.request._timers_total_queries = 0
    cherrypy.request._timers_total_time = time.time()


def timers_end():
    total_time = time.time() - cherrypy.request._timers_total_time
    total_queries = cherrypy.request._timers_total_queries
    query_time = cherrypy.request._timers_query_time

    log("request ended: %f query time, %d queries, %f total time." %
          (query_time, total_queries, total_time))


timers_start_tool = cherrypy.Tool('on_start_resource', timers_start)
timers_end_tool = cherrypy.Tool('before_finalize', timers_end)
