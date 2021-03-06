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
import cherrypy
import re
import random
import locale
import pycountry
import datetime
from json import dumps as json_dumps
from cherrypy.process.plugins import SimplePlugin
from cherrypy._cptools import HandlerWrapperTool
from cherrypy._cpdispatch import PageHandler
from jinja2 import Environment, FileSystemLoader, ModuleLoader, StrictUndefined
from jinja2_webpack import Environment as WebpackEnvironment
from jinja2_webpack.filter import WebpackFilter
import opmuse
from opmuse.security import is_granted as _is_granted
from opmuse.pretty import pretty_date as _pretty_date
from opmuse.library import TrackStructureParser, Library, Album, Track, Artist

VISIBLE_WS = "\u2423"


def _max(items):
    return max(items)


def ordinal(num):
    # stolen from http://codegolf.stackexchange.com/a/4712
    k = num % 10
    return "%d%s" % (num, "tsnrhtdd"[(num / 10 % 10 != 1) * (k < 4) * k::4])


def date(value, date_format='%Y-%m-%d'):
    if type(value) is str:
        date = datetime.datetime.fromtimestamp(int(value))
    elif type(value) is int:
        date = datetime.datetime.fromtimestamp(value)
    else:
        date = value

    return date.strftime(date_format)


def get_jinja_env():
    auto_reload = cherrypy.config['opmuse'].get('jinja.auto_reload')

    if auto_reload is None:
        auto_reload = True

    template_path = os.path.join(os.path.dirname(__file__), '..', 'templates')

    if os.path.exists(template_path):
        loader = FileSystemLoader(template_path)
    else:
        loader = ModuleLoader('/usr/share/opmuse/templates/')

    env = Environment(
        loader=loader,
        extensions=['jinja2.ext.loopcontrols', 'jinja2.ext.do', 'jinja2.ext.autoescape'],
        autoescape=guess_autoescape,
        undefined=StrictUndefined,
        auto_reload=auto_reload,
        cache_size=-1
    )

    cache_path = cherrypy.config['opmuse'].get('cache.path')
    webpack_manifest_path = os.path.join(cache_path, 'webpack-manifest.json')

    if os.path.exists(webpack_manifest_path):
        webpack_env = WebpackEnvironment(manifest=webpack_manifest_path, publicRoot='')
        env.filters['webpack'] = WebpackFilter(webpack_env)
    else:
        def webpack_filter(*args):
            raise Exception("webpack-manifest.json is missing, please run `yarn build:dev` and restart opmuse")

        env.filters['webpack'] = webpack_filter

    env.filters['nl2p'] = nl2p
    env.filters['format_seconds'] = format_seconds
    env.filters['format_seconds_alt'] = format_seconds_alt
    env.filters['pretty_date'] = pretty_date
    env.filters['format_number'] = format_number
    env.filters['show_ws'] = show_ws
    env.filters['format_bytes'] = format_bytes
    env.filters['json'] = json
    env.filters['startswith'] = startswith
    env.filters['track_path'] = track_path
    env.filters['round'] = round
    env.filters['pretty_format'] = pretty_format
    env.filters['country'] = country
    env.filters['date'] = date
    env.filters['ordinal'] = ordinal
    env.filters['max'] = _max

    env.globals['pagination_pages'] = pagination_pages
    env.globals['rand_id'] = rand_id
    env.globals['is_granted'] = is_granted
    env.globals['is_track'] = is_track
    env.globals['is_artist'] = is_artist
    env.globals['is_album'] = is_album
    env.globals['render'] = render
    env.globals['opmuse_version'] = opmuse.__version__

    return env


def country(code):
    try:
        data = pycountry.countries.get(alpha_2=code)
        return data.name
    except KeyError:
        return code


# implemented with the help of http://codereview.stackexchange.com/a/15239
def pagination_pages(page, pages, size):
    if pages <= 10:
        return list(range(1, pages + 1))
    else:
        return sorted(list(set(range(1, 2)) |
                      set(range(max(1, page - size + 1), min(page + size, pages + 1))) |
                      set(range(pages, pages + 1))))


def pretty_format(format):
    return Library.pretty_format(format)


def is_track(object):
    return isinstance(object, Track)


def is_artist(object):
    return isinstance(object, Artist)


def is_album(object):
    return isinstance(object, Album)


def is_granted(role):
    return _is_granted([role])


def rand_id():
    return str(random.randrange(1, 99999))


def replace_ws(string):
    match = re.search(r'\S', string)

    if match is not None:
        index = match.start()
        return "%s%s" % (index * VISIBLE_WS, string[index:])
    else:
        return len(string) * VISIBLE_WS


def show_ws(string):
    """
    Helper for replacing trailing whitespace with the unicode visible space
    character
    """
    if string is None or isinstance(string, StrictUndefined) or len(string) == 0:
        return "[MISSING]"

    return replace_ws(replace_ws(string)[::-1])[::-1]


def format_bytes(bytes, precision=2):
    if bytes is None:
        bytes = 0

    bytes = int(bytes)

    suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
    suffixIndex = 0

    while bytes > 1024:
        suffixIndex += 1
        bytes = bytes / 1024.0

    return "%.*f %s" % (precision, bytes, suffixes[suffixIndex])


def track_path(track, artist=None):
    track_structure = TrackStructureParser(track, data_override={'artist': artist})
    path = track_structure.get_path()

    if path is not None:
        return path.decode('utf8', 'replace')
    else:
        return ''


def startswith(value, start):
    return value.startswith(start)


def json(value):
    return json_dumps(value)


def format_number(number):
    if number is None:
        return None

    return locale.format('%d', number, grouping=True)


def pretty_date(date, ago="ago"):
    return _pretty_date(date, ago=ago)


def nl2p(string):
    paragraphs = []

    for line in string.split('\n'):
        if line == "":
            continue

        paragraphs.append("<p>%s</p>" % line)

    return ''.join(paragraphs)


def format_seconds_alt(seconds):
    if seconds is None:
        seconds = 0

    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if minutes > 0:
        minute_str = "%dm " % minutes
    else:
        minute_str = ""

    if hours > 0:
        hour_str = "%dh " % hours
    else:
        hour_str = ""

    if hours == 0 and minutes == 0 and seconds == 0 or seconds > 0:
        second_str = "%ds" % seconds
    else:
        second_str = ""

    return "%s%s%s" % (hour_str, minute_str, second_str)


def format_seconds(seconds):
    if seconds is None:
        seconds = 0

    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours > 0:
        string = "%02d:" % (hours, )
    else:
        string = ""

    return "%s%02d:%02d" % (string, minutes, seconds)


def guess_autoescape(template_name):
    if template_name is None or '.' not in template_name:
        return False

    ext = template_name.rsplit('.', 1)[1]

    return ext in ('html', )


class JinjaPlugin(SimplePlugin):

    def __init__(self, bus):
        SimplePlugin.__init__(self, bus)
        self.env = None
        self.bus.subscribe("bind_jinja", self.bind_jinja)

    def start(self):
        self.env = get_jinja_env()

    start.priority = 130

    def bind_jinja(self):
        return self.env

    def stop(self):
        self.env = None


def render(path, params=[]):
    # this one fucks with cherrypy.request and stuff, but seeing as this should
    # only be run in a template after all that jazz is done, it should be safe.
    # i guess we'll notice if it doesn't though :/
    func, vpath = cherrypy.request.dispatch.find_handler(path)
    config = cherrypy.request.config

    if func:
        handler = PageHandler(func, *params)
        filename = config['tools.jinja.filename']
        response_dict = handler()
        html = render_template(filename, response_dict)
        return html
    else:
        return ''


def render_template(filename, dictionary):
    template = cherrypy.request.jinja.get_template(filename)

    template.globals['request'] = cherrypy.request
    template.globals['xhr'] = cherrypy.request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    template.globals['current_url'] = cherrypy.url()

    return template.render(dictionary)


class Jinja(HandlerWrapperTool):

    def __init__(self):
        HandlerWrapperTool.__init__(self, self.jinja)

    def callable(self, filename=None, *args, **kwargs):
        HandlerWrapperTool.callable(self)

    def jinja(self, next_handler, *args, **kwargs):
        if cherrypy.request.jinja is None:
            return

        response_dict = next_handler(*args, **kwargs)
        conf = self._merged_args()

        if 'filename' not in conf:
            raise Exception('No template filename specified!')

        html = render_template(conf['filename'], response_dict)

        if 'text/html' == cherrypy.response.headers['Content-Type']:
            cherrypy.response.headers['Content-Type'] = 'text/html; charset=utf8'

        return html.encode('utf8', 'replace')


class JinjaEnvTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.bind_jinja, priority=10)

    def bind_jinja(self):
        binds = cherrypy.engine.publish('bind_jinja')
        cherrypy.request.jinja = binds[0]


class JinjaAuthenticatedTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'before_handler',
                               self.start, priority=20)

    def start(self):
        if cherrypy.request.jinja is None:
            return

        cherrypy.request.jinja.globals['authenticated'] = False
        cherrypy.request.jinja.globals['user'] = None

        if hasattr(cherrypy.request, 'user') and cherrypy.request.user is not None:
            cherrypy.request.jinja.globals['user'] = cherrypy.request.user
            cherrypy.request.jinja.globals['authenticated'] = True
