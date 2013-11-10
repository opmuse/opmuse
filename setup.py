import os.path
import re
import subprocess
from setuptools import setup
from pip.req import parse_requirements

project_root = os.path.dirname(os.path.abspath(__file__))
git_version = subprocess.check_output(['git', 'describe', 'HEAD', '--tags']).strip().decode('utf8')
git_url = 'https://raw.github.com/opmuse/opmuse/%s/%%s' % git_version

install_requires = []
dependency_links = []

for install_require in parse_requirements('requirements.txt'):
    if install_require.req is not None:
        install_requires.append(str(install_require.req))
    elif install_require.url is not None:
        dependency_links.append(git_url % re.sub(r'^file://%s/' % project_root, '', install_require.url))
    else:
        raise Exception("Couldn't parse requirement from requirements.txt")

setup(
    name="opmuse",
    version=git_version,
    packages=['opmuse'],
    description="A web application to play, organize and share your music library.",
    long_description=open('README.md', 'r').read(),
    author="Mattias Fliesberg",
    author_email="mattias.fliesberg@gmail.com",
    url="http://opmu.se/",
    license="GPLv3",
    install_requires=install_requires,
    dependency_links=dependency_links,
    entry_points={
        'console_scripts': [
            'opmuse = opmuse.boot'
        ]
    }
)
