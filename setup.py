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

import sys
import os
import re
import subprocess
import shutil
import fileinput
from configparser import ConfigParser
from itertools import chain
from setuptools import setup
from setuptools.command.build_py import build_py
from pip.req import parse_requirements
from pip.download import PipSession
from opmuse.compilers import js_compiler, less_compiler

project_root = os.path.dirname(os.path.abspath(__file__))
git_version = subprocess.check_output(['git', 'describe', 'HEAD', '--tags']).strip().decode('utf8')
git_url = 'https://raw.github.com/opmuse/opmuse/%s/%%s' % git_version
on_readthedocs = os.environ.get('READTHEDOCS', None) == 'True'


def copy(src, dst):
    shutil.copyfile(src, dst)
    shutil.copymode(src, dst)


def get_datafiles(src, dest, exclude_exts=[], followlinks=False):
    datafiles = []

    src_comps = len([comp for comp in os.path.split(src) if comp != ""])

    for root, dirs, files in os.walk(src, followlinks=followlinks):
        if len(files) == 0:
            continue

        included_files = []

        for f in files:
            path, ext = os.path.splitext(f)

            if ext in exclude_exts:
                continue

            included_files.append(os.path.join(root, f))

        if len(included_files) == 0:
            continue

        datafiles.append((
            os.path.join(dest, os.path.join(*(root.split('/')[src_comps - 1:]))),
            included_files
        ))

    return datafiles


if not on_readthedocs and not os.path.exists("build/templates"):
    print('You need to run "console jinja compile" before you build.')
    sys.exit(1)


install_requires = []

for install_require in chain(parse_requirements('requirements.txt', session=PipSession()),
                             parse_requirements('mysql-requirements.txt', session=PipSession())):
    if install_require.req is not None:
        install_requires.append(str(install_require.req))
    else:
        raise Exception("Couldn't parse requirement from requirements.txt")


def build_opmuse():
    config = ConfigParser()
    config.read('setup.cfg')

    if not os.path.exists('build'):
        os.mkdir('build')

    copy('config/opmuse.dist.ini', 'build/opmuse.ini')

    for line in fileinput.input("opmuse/__init__.py", inplace=True):
        if re.match(r'^__version__\s*=', line):
            sys.stdout.write("__version__ = '%s'\n" % git_version)
        else:
            sys.stdout.write(line)

    for line in fileinput.input("build/opmuse.ini", inplace=True):
        if re.match(r'[#]*lastfm\.key\s*=', line):
            sys.stdout.write("lastfm.key = '%s'\n" % config['global']['lastfm.key'])
        elif re.match(r'[#]*lastfm\.secret\s*=', line):
            sys.stdout.write("lastfm.secret = '%s'\n" % config['global']['lastfm.secret'])
        else:
            sys.stdout.write(line)

    less_compiler.compile(path='build/main.css')
    js_compiler.compile(path='build/javascript/scripts')

    shutil.copytree('public_static/lib', 'build/javascript/lib')

    subprocess.check_call(['node', 'public_static/lib/r.js/dist/r.js', '-o', 'scripts/build-requirejs.js'])

    if not os.path.exists('build/debian-dbconfig-install'):
        os.mkdir('build/debian-dbconfig-install')

    copy('scripts/debian-dbconfig-install-mysql', 'build/debian-dbconfig-install/mysql')

    if not os.path.exists('build/debian-dbconfig-upgrade-mysql'):
        os.mkdir('build/debian-dbconfig-upgrade-mysql')

    copy('scripts/debian-dbconfig-upgrade-mysql', 'build/debian-dbconfig-upgrade-mysql/all')

if on_readthedocs:
    data_files = []
else:
    data_files = ([
        # debian specific
        ('/usr/share/dbconfig-common/scripts/opmuse/install/', ['build/debian-dbconfig-install/mysql']),
        ('/usr/share/dbconfig-common/scripts/opmuse/upgrade/mysql/', ['build/debian-dbconfig-upgrade-mysql/all']),
        # global
        ('/var/cache/opmuse', ['cache/.keep']),
        ('/var/log/opmuse', ['log/.keep']),
        ('/etc/opmuse', ['build/opmuse.ini']),
        ('/usr/share/opmuse', ['alembic.ini']),
        ('/usr/share/opmuse/public_static/styles', ['build/main.css']),
        ('/usr/share/opmuse/public_static/scripts', ['build/main.js', 'build/javascript/scripts/init.js']),
        ('/usr/share/opmuse/public_static/lib/requirejs', ['public_static/lib/requirejs/require.js']) +
        ('/usr/share/opmuse/public_static/lib/traceur', ['public_static/lib/traceur/traceur.js'])] +
        get_datafiles('public_static/fonts', '/usr/share/opmuse/public_static') +
        get_datafiles('public_static/lib/Font-Awesome/fonts', '/usr/share/opmuse/public_static/') +
        get_datafiles('public_static/images', '/usr/share/opmuse/public_static') +
        get_datafiles('database', '/usr/share/opmuse', exclude_exts=['.pyc']) +
        get_datafiles('build/templates', '/usr/share/opmuse'))

class OpmuseBuild(build_py):
    def run(self):
        if not on_readthedocs:
            build_opmuse()

        build_py.run(self)

cmdclass = {}
cmdclass['build_py'] = OpmuseBuild

setup(
    name="opmuse",
    version=git_version,
    packages=['opmuse', 'opmuse.controllers'],
    description="A web application to play, organize, share and make your music library social.",
    long_description=open('README.md', 'r').read(),
    author="Mattias Fliesberg",
    author_email="mattias@fliesberg.email",
    url="http://opmu.se/",
    license="AGPLv3+",
    install_requires=install_requires,
    cmdclass=cmdclass,
    entry_points={
        'console_scripts': [
            'opmuse-console = opmuse.commands:main',
            'opmuse-boot = opmuse.boot:main'
        ]
    },
    data_files=data_files,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Web Environment",
        "Intended Audience :: End Users/Desktop",
        "Framework :: CherryPy",
        "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: JavaScript",
        "Topic :: Internet",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Multimedia :: Sound/Audio :: Players"
    ],
)
