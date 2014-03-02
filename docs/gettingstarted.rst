Getting Started
===============

Requirements
------------

You need **python 3.3**, **ffmpeg**, **ImageMagick**, **nodejs** (for less.js)
and a Linux environment. This has only been tested on Debian and Exherbo but
most other Linux distros should do as well as other similar \*nix OSes. If
you're on Windows you're on your own.

Install
-------

::

    $ git clone https://github.com/opmuse/opmuse.git
    $ cd opmuse
    $ git submodule update --init --recursive
    $ virtualenv -p python3.3 ./virtualenv
    $ source virtualenv/bin/activate
    $ pip install -r requirements.txt
    $ cp config/opmuse.dist.ini config/opmuse.ini
    $ edit config/opmuse.ini # fix library.path

If you just want to use **SQLite**.::

    $ ./console database create

If you want to use **MySQL** instead of SQLite (MySQL is recommended).::

    $ pip install -r mysql-requirements.txt
    $ edit config/opmuse.ini # fix database.url
    $ ./console database create

If you want some additional dev tools (firepy, repoze.profile).::

    $ source virtualenv/bin/activate
    $ pip install -r dev-requirements.txt
    $ ./console cherrypy -- -f # start with firepy (use with cherrypy.request.firepy())
    $ ./console cherrypy -- -p # start with repoze.profile (access it at /__profile__)

You probably want fixtures for some default data (an admin account with password admin for one).::

    $ ./console database fixtures

Then you start the whole debacle with::

    $ ./console cherrypy

Upgrading
---------

When you do a git pull some of these might be required.::

    $ git submodule update --init --recursive

    $ merge config/opmuse.dist.ini config/opmuse.ini

    $ pip install --upgrade -r requirements.txt
    $ pip install --upgrade -r mysql-requirements.txt
    $ pip install --upgrade -r dev-requirements.txt

    $ ./console database reset # will initiate rescan, might not be required
    $ ./console database update
