Getting Started
===============

Docker
------

You can use the opmuse-dev docker image for development.

This will get a copy of the repo from the docker image and mount it inside the container.

.. code-block:: console

    $ docker export $(docker run -d inty/opmuse-dev) | tar xf - root/opmuse --strip-components=1
    $ cd opmuse
    $ docker run -d -p 8080:8080 --name=opmuse-dev -v `pwd`:/root/opmuse inty/opmuse-dev

To get cherrypy's output do this

.. code-block:: console

    $ docker logs -f opmuse-dev

To get a shell

.. code-block:: console

    $ docker exec -it opmuse-dev /bin/bash

Requirements
------------

You need **Python 3.5**, **ffmpeg**, **ImageMagick**, **nodejs**, **npm**,
**yarn**, **rsync** and a Linux environment. This has only been tested on
Debian and Exherbo but most other Linux distros should do as well as other
similar \*nix OSes. If you're on Windows you're on your own.

Install
-------

.. code-block:: console

    $ git clone https://github.com/opmuse/opmuse.git
    $ cd opmuse
    $ virtualenv -p python3 ./virtualenv
    $ source virtualenv/bin/activate
    $ pip install -r requirements.txt
    $ cp config/opmuse.dist.ini config/opmuse.ini
    $ yarn
    $ yarn build:dev
    $ edit config/opmuse.ini # fix library.path

If you just want to use **SQLite**.

.. code-block:: console

    $ ./console database create

If you want to use **MySQL** instead of SQLite (MySQL is recommended).

.. code-block:: console

    $ pip install -r mysql-requirements.txt
    $ edit config/opmuse.ini # fix database.url
    $ ./console database create

If you want some additional dev tools and stuff (repoze.profile, colorlog), install 'em

.. code-block:: console

    $ source virtualenv/bin/activate
    $ pip install -r dev-requirements.txt
    $ ./console cherrypy -- -p # start with repoze.profile (access it at /__profile__)

You probably want fixtures for some default data (an admin account with password admin for one).

.. code-block:: console

    $ ./console database fixtures

Then you start the whole debacle with

.. code-block:: console

    $ ./console cherrypy

Upgrading
---------

When you do a git pull some of these might be required.

.. code-block:: console

    $ merge config/opmuse.dist.ini config/opmuse.ini

    $ source virtualenv/bin/activate
    $ pip install --upgrade -r requirements.txt
    $ pip install --upgrade -r mysql-requirements.txt
    $ pip install --upgrade -r dev-requirements.txt
    $ yarn
    $ yarn build:dev
    $ ./console database reset # will initiate rescan, might not be required
    $ ./console database update
