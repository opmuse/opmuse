
    ,adPPYba,  8b,dPPYba,  88,dPYba,,adPYba,  88       88 ,adPPYba,  ,adPPYba,
    a8"     "8a 88P'    "8a 88P'   "88"    "8a 88       88 I8[    "" a8P_____88
    8b       d8 88       d8 88      88      88 88       88  `"Y8ba,  8PP"""""""
    "8a,   ,a8" 88b,   ,a8" 88      88      88 "8a,   ,a88 aa    ]8I "8b,   ,aa
     `"YbbdP"'  88`YbbdP"'  88      88      88  `"YbbdP'Y8 `"YbbdP"'  `"Ybbd8"'
                88
                88

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

[![Build Status](https://secure.travis-ci.org/opmuse/opmuse.png?branch=master)](http://travis-ci.org/inty/opmuse)

