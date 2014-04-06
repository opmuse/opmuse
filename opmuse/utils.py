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
import cherrypy
import json
import sys
from opmuse.less_compiler import less_compiler
from cherrypy.process.plugins import Monitor


def get_staticdir():
    staticdir = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'public_static')

    if not os.path.exists(staticdir):
        staticdir = '/usr/share/opmuse/public_static'

    return staticdir


class LessReloader(Monitor):
    def __init__(self, bus):
        Monitor.__init__(self, bus, self.run, frequency = .5)

        self._files = {}
        self.enable = False

    def start(self):
        Monitor.start(self)

        self.enable = cherrypy.config['opmuse'].get('less_reloader.enable')

        if self.enable is None:
            self.enable = True

        if not self.enable:
            return

        less_compiler.compile()
        cherrypy.log('compiled main.css')

    start.priority = 80

    def run(self):
        if not self.enable:
            return

        from opmuse.boot import get_staticdir

        for path, dirnames, filenames in os.walk(os.path.join(get_staticdir(), 'styles')):
            for filename in filenames:
                if filename[-4:] != 'less':
                    continue

                filepath = os.path.join(path, filename)
                mtime = os.stat(filepath).st_mtime

                if filepath in self._files:
                    old_mtime = self._files[filepath]

                    if mtime > old_mtime:
                        cherrypy.log('%s changed, recompiling main.css' % filename)
                        less_compiler.compile()

                self._files[filepath] = mtime


class HTTPRedirect(cherrypy.HTTPRedirect):
    def set_response(self):
        if cherrypy.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response = cherrypy.serving.response
            response.headers['X-Opmuse-Location'] = json.dumps(self.urls)
        else:
            cherrypy.HTTPRedirect.set_response(self)


# http://tools.cherrypy.org/wiki/CGITB
def cgitb_log_err():
    import cgitb

    tb = cgitb.text(sys.exc_info())

    def set_tb():
        cherrypy.log(tb)

    cherrypy.request.hooks.attach('after_error_response', set_tb)


def profile_pipeline(app):
    from repoze.profile import ProfileMiddleware

    cache_path = cherrypy.config['opmuse'].get('cache.path')
    profile_path = os.path.join(cache_path, 'profile')

    if not os.path.exists(profile_path):
        os.mkdir(profile_path)

    return ProfileMiddleware(
        app,
        log_filename=os.path.join(profile_path, 'profile.log'),
        cachegrind_filename=os.path.join(profile_path, 'cachegrind.out'),
        discard_first_request=True,
        flush_at_shutdown=True,
        path='/__profile__',
        unwind=False,
    )


def firepy(message):
    cherrypy.request._firepy_logs.append([{"Type": 'LOG'}, message])


def firepy_start():
    cherrypy.request._firepy_logs = []
    cherrypy.request.firepy = firepy


def firepy_end():
    if not hasattr(cherrypy.request, '_firepy_logs'):
        return

    from firepy.firephp import FirePHP

    headers = FirePHP.base_headers()

    for key, value in headers:
        cherrypy.response.headers[key] = value

    for key, value in FirePHP.generate_headers(cherrypy.request._firepy_logs):
        cherrypy.response.headers[key] = value


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


firepy_tool = cherrypy.Tool('on_start_resource', firepy)
firepy_start_tool = cherrypy.Tool('on_start_resource', firepy_start)
firepy_end_tool = cherrypy.Tool('before_finalize', firepy_end, priority=100)

multi_headers_tool = cherrypy.Tool('on_end_resource', multi_headers)
cgitb_log_err_tool = cherrypy.Tool('before_error_response', cgitb_log_err)
