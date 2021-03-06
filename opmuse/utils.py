# Copyright 2012-2015 Mattias Fliesberg
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
import json
import sys
import threading
import cProfile
import tempfile
import builtins
import cherrypy
import cgitb


class ProfiledThread(threading.Thread):
    def run(self):
        profiler = cProfile.Profile()

        try:
            return profiler.runcall(threading.Thread.run, self)
        finally:
            from pyprof2calltree import convert

            filename = os.path.join(tempfile.gettempdir(), "opmuse.%s.%d" % (self.name, self.ident))

            profile_filename = '%s.profile' % filename
            kgrind_filename = '%s.kgrind' % filename

            profiler.dump_stats(profile_filename)

            convert(profile_filename, kgrind_filename)


def get_staticdir():
    staticdir = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'public_static')

    if not os.path.exists(staticdir):
        staticdir = '/usr/share/opmuse/public_static'

    return staticdir


class HTTPRedirect(cherrypy.HTTPRedirect):
    def set_response(self):
        if cherrypy.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response = cherrypy.serving.response
            response.headers['X-Opmuse-Location'] = json.dumps(self.urls)
        else:
            cherrypy.HTTPRedirect.set_response(self)


def get_pretty_errors(exc):
    import traceback

    try:
        text = cgitb.text(exc)
        html = cgitb.html(exc)
    except:
        # errors might be thrown when cgitb tries to inspect stuff,
        # in which case just get a regular stacktrace
        from cherrypy._cperror import format_exc
        text = format_exc(exc)
        html = None

    name = traceback.format_exception(*exc)[-1]

    return name, text, html


def mail_pretty_errors(name, text, html):
    config = cherrypy.tree.apps[''].config['opmuse']

    error_mail = config.get('error.mail')

    if error_mail is not None:
        from opmuse.mail import mailer

        mailer.send(error_mail, "opmuse caught error: %s" % name, text, html)


def error_handler_log():
    config = cherrypy.tree.apps[''].config['opmuse']
    debug = config.get('debug')

    exc = sys.exc_info()

    name, text, html = get_pretty_errors(exc)

    mail_pretty_errors(name, text, html)

    def _error_handler_log():
        if debug:
            if html is not None:
                cherrypy.response.body = html.encode('utf8')
            else:
                cherrypy.response.body = text.encode('utf8')
                cherrypy.response.headers['Content-Type'] = "text/plain; charset=utf8"

            cherrypy.response.headers['Content-Length'] = None

        cherrypy.log(text)

    cherrypy.request.hooks.attach('after_error_response', _error_handler_log)


def profile_pipeline(app):
    from repoze.profile import ProfileMiddleware

    cache_path = cherrypy.config['opmuse'].get('cache.path')
    profile_path = os.path.join(cache_path, 'profile')

    if not os.path.exists(profile_path):
        os.mkdir(profile_path)

    return ProfileMiddleware(
        app,
        log_filename=os.path.join(profile_path, 'profile.log'),
        # cachegrind_filename is broken in python 3 :(
        cachegrind_filename=None,
        discard_first_request=True,
        flush_at_shutdown=True,
        path='/__profile__',
        unwind=False,
    )


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


def memoize(func):
    """
        memoize decorator which memoizes on current request.
    """
    def wrapper(self, *args, **kwargs):
        # if stage is None we're running in a bgtask or something outside
        # a regular request so we just pass it along...
        #
        # TODO for bgtasks we could implement something similar to this using
        #      threading.local()...
        if cherrypy.request.stage is None:
            return func(self, *args, **kwargs)

        if not hasattr(cherrypy.request, 'memoize'):
            cherrypy.request.memoize = {}

        if len(kwargs) > 0:
            # to avoid different call signatures creating different keys, e.g. func(1)
            # and func(arg=1) might be the same call but will have different signatures.
            # also, dicts aren't hashable.
            raise Exception('memoize doesn\'t support keywords args.')

        key = (func, args)

        if key not in cherrypy.request.memoize:
            cherrypy.request.memoize[key] = func(self, *args)

        return cherrypy.request.memoize[key]

    return wrapper


multi_headers_tool = cherrypy.Tool('on_end_resource', multi_headers)
error_handler_tool = cherrypy.Tool('before_error_response', error_handler_log)
