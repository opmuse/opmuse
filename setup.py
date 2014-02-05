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

import sys
import os.path
import re
import subprocess
import shutil
from setuptools import setup
from pip.req import parse_requirements
from opmuse.utils import less_compiler

project_root = os.path.dirname(os.path.abspath(__file__))
git_version = subprocess.check_output(['git', 'describe', 'HEAD', '--tags']).strip().decode('utf8')
git_url = 'https://raw.github.com/opmuse/opmuse/%s/%%s' % git_version

def get_datafiles(src, dest, exclude_exts=[]):
    datafiles = []

    src_comps = len([comp for comp in os.path.split(src) if comp != ""])

    for root, dirs, files in os.walk(src):
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
            os.path.join(dest, os.path.join(*(os.path.split(root)[src_comps - 1:]))),
            included_files
        ))

    return datafiles


if not os.path.exists("build/templates"):
    print('You need to run "console jinja compile" before you build.')
    sys.exit(1)


install_requires = []
dependency_links = []

for install_require in parse_requirements('requirements.txt'):
    if install_require.req is not None:
        install_requires.append(str(install_require.req))
    elif install_require.url is not None:
        dependency_links.append(git_url % re.sub(r'^file://%s/' % project_root, '', install_require.url))
    else:
        raise Exception("Couldn't parse requirement from requirements.txt")

if not os.path.exists('build'):
    os.mkdir('build')

shutil.copyfile('config/opmuse.dist.ini', 'build/opmuse.ini')

less_compiler.compile()

setup(
    name="opmuse",
    version=git_version,
    packages=['opmuse'],
    description="A web application to play, organize and share your music library.",
    long_description=open('README.md', 'r').read(),
    author="Mattias Fliesberg",
    author_email="mattias.fliesberg@gmail.com",
    url="http://opmu.se/",
    license="AGPLv3+",
    install_requires=install_requires,
    dependency_links=dependency_links,
    entry_points={
        'console_scripts': [
            'opmuse-console = opmuse.commands:main',
            'opmuse-boot = opmuse.boot:main'
        ]
    },
    data_files=[
        ('/etc/opmuse', ['build/opmuse.ini']),
        ('/usr/share/opmuse', ['alembic.ini']),
    ] + get_datafiles('public_static', '/usr/share/opmuse', exclude_exts=['.less']) +
        get_datafiles('database', '/usr/share/opmuse', exclude_exts=['.pyc']) +
        get_datafiles('build/templates', '/usr/share/opmuse'),
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
