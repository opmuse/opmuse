import os
import cherrypy
import json
import sys
import subprocess
from cherrypy.process.plugins import Monitor


class LessReloader(Monitor):
    def __init__(self, bus):
        Monitor.__init__(self, bus, self.run, frequency = .5)

        self._files = {}
        self._stylespath = os.path.join(os.path.dirname(__file__), '..', 'public_static', 'styles')

    def start(self):
        Monitor.start(self)
        self.compile()

    def run(self):
        for path, dirnames, filenames in os.walk(self._stylespath):
            for filename in filenames:
                if filename[-4:] != 'less':
                    continue

                filepath = os.path.join(path, filename)
                mtime = os.stat(filepath).st_mtime

                if filepath in self._files:
                    old_mtime = self._files[filepath]

                    if mtime > old_mtime:
                        cherrypy.log('%s changed, recompiling main.css' % filename)
                        self.compile()

                self._files[filepath] = mtime

    def compile(self):
        lesspath = os.path.join(os.path.dirname(__file__), '..', 'vendor', 'less.js')

        subprocess.call([
            os.path.join(lesspath, 'bin', 'lessc'),
            os.path.join(self._stylespath, 'main.less'),
            os.path.join(self._stylespath, 'main.css')
        ], cwd=self._stylespath)


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

    profile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cache', 'profile')

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


firepy_tool = cherrypy.Tool('on_start_resource', firepy)
firepy_start_tool = cherrypy.Tool('on_start_resource', firepy_start)
firepy_end_tool = cherrypy.Tool('before_finalize', firepy_end, priority=100)

multi_headers_tool = cherrypy.Tool('on_end_resource', multi_headers)
cgitb_log_err_tool = cherrypy.Tool('before_error_response', cgitb_log_err)
