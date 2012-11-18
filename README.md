[![Build Status](https://secure.travis-ci.org/opmuse/opmuse.png?branch=master)](http://travis-ci.org/inty/opmuse)

       ________________________________________________
      /\     _____ _____ __  ___ __  __ _____ _____    \
      \/    /    //    //  |/  // / / //  __// ___/    /
      /    /    //  __//      // /_/ //__  // ___/    /
     /    /____//__/  /__//__//_____//____//____/    /\
     \_______________________________________________\/

What is opmuse?
---------------

A web application to play, organize and share your music library.

Requirements
------------

You need *python 3.2*, *ffmpeg* (the executable), *ImageMagick* (convert and
identify executables) and a Linux environment. This has only been tested on
Debian and Exherbo but most other Linux distros should do as well as other \*nix
OSes. If you're on Windows you're on your own.

Setup
-----

    $ git submodule init
    $ git submodule update
    $ virtualenv -p python3 ./virtualenv
    $ source virtualenv/bin/activate
    $ pip install -r requirements.txt
    $ pip install -r optional-requirements.txt # needed for mysql
    $ cp config/opmuse.dist.ini config/opmuse.ini
    $ edit config/opmuse.ini
    $ ./run.sh

You probably want fixtures for some default data (an admin account with password
admin for one).

    $ python opmuse/fixtures.py

This script is the only way to add accounts at the moment, so just modify it
appropriately and run to add accounts.

Upgrading
---------

    $ git submodule init
    $ git submodule update

    $ merge config/opmuse.dist.ini config/opmuse.ini

    $ pip install -r requirements.txt

    $ rm opmuse.db # e.g. drop database..

    $ rm -rf cache/index/* # remove whoosh index

Our Doctrine
------------

This is what we recite to ourselves while we code.

  - *We* don't *exclusively* store metadata about your library.

    i.e. artist, album, title are always stored as actual tags on the file. Album covers are stored on the filesystem etc.

  - Data generated exclusively in opmuse is worthless.

    i.e. A users played tracks are submitted to last.fm

  - We use the metadata we recieve verbatim.

    i.e. Names are always case-sensitive. We don't try to be smart and remove leading spaces or anything, if your collection isn't tagged correctly you will suffer.

