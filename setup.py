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
from distutils.command.install_data import install_data

try:
    from pip._internal.req import parse_requirements
    from pip._internal.download import PipSession
except ImportError:
    from pip.req import parse_requirements
    from pip.download import PipSession

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

    if os.path.exists('build'):
        shutil.rmtree('build')

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

    virtualenv_bin = os.path.join(project_root, 'virtualenv', 'bin', 'python')
    commands_path = os.path.join(project_root, 'opmuse', 'commands.py')

    if not os.path.exists(virtualenv_bin):
        raise Exception("virtualenv is required for building")

    subprocess.check_call([virtualenv_bin, commands_path, 'jinja', 'compile', 'build/templates'],
        env={'PYTHONPATH': project_root}
    )

    subprocess.check_call([virtualenv_bin, commands_path, 'jinja', 'webpack_scan'],
        env={'PYTHONPATH': project_root}
    )

    subprocess.check_call(["npx", "webpack", '--config', 'webpack.prod.js'],
        env={'NODE_ENV': "production"}
    )

    os.mkdir('build/debian-dbconfig-install')

    copy('scripts/debian-dbconfig-install-mysql', 'build/debian-dbconfig-install/mysql')

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
        ('/var/cache/opmuse', ['cache/.keep', 'cache/webpack-manifest.json']),
        ('/var/log/opmuse', ['log/.keep']),
        ('/etc/opmuse', ['build/opmuse.ini']),
        ('/usr/share/opmuse', ['alembic.ini'])])


class OpmuseBuildPy(build_py):
    def run(self):
        if not on_readthedocs:
            build_opmuse()

        build_py.run(self)

class OpmuseInstallData(install_data):
    def initialize_options(self):
        install_data.initialize_options(self)

        if not on_readthedocs:
            self.data_files += (
                get_datafiles('build/public_static/build', '/usr/share/opmuse') +
                get_datafiles('public_static/images', '/usr/share/opmuse/public_static') +
                get_datafiles('assets', '/usr/share/opmuse') +
                get_datafiles('database', '/usr/share/opmuse', exclude_exts=['.pyc']) +
                get_datafiles('build/templates', '/usr/share/opmuse'))

cmdclass = {}
cmdclass['build_py'] = OpmuseBuildPy
cmdclass['install_data'] = OpmuseInstallData

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
        "Programming Language :: Python :: 3.5",
        "Programming Language :: JavaScript",
        "Topic :: Internet",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Multimedia :: Sound/Audio :: Players"
    ],
)
