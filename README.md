      ________________________________________________
     /\     _____ _____ __  ___ __  __ _____ _____    \
     \/    /    //    //  |/  // / / //  __// ___/    /
     /    /    //  __//      // /_/ //__  // ___/    /
    /    /____//__/  /__//__//_____//____//____/    /\
    \_______________________________________________\/

Software supposed to expose your media files and let you stream it anywhere
from the comfort of your web browser.

Requirements
------------

  - Python 3.2
  - ffmpeg
  - ImageMagick

Get up and running...
---------------------

    $ git submodule init
    $ git submodule update
    $ virtualenv -p python3 ./virtualenv
    $ source virtualenv/bin/activate
    $ pip install -r requirements.txt
    $ pip install -r optional-requirements.txt
    $ cp config/opmuse.dist.ini config/opmuse.ini
    $ ./run.sh

You probably want fixtures for some default data.

    $ python opmuse/fixtures.py

... get back to work...
-----------------------

    $ ./run.sh

Upgrading
---------

One of these upgrade steps might be required upon fetching new changesets

    $ git submodule init
    $ git submodule update

    $ merge config/opmuse.dist.ini config/opmuse.ini

    $ pip install -r requirements.txt

    $ rm opmuse.db # e.g. drop database..

[![Build Status](https://secure.travis-ci.org/opmuse/opmuse.png?branch=master)](http://travis-ci.org/inty/opmuse)
