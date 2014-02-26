What is opmuse?
---------------

<img align="right" src="https://github.com/opmuse/opmuse/raw/master/assets/opossum-readme.png" />

opmuse is a web application to play, organize and share your music library.

Our doctrine is that we don't exclusively store metdata about you library. We
never generate data exclusively in opmuse. We trust the data provided for us. We
care about structure.

What this means is that artist, album and title are always stored as tags on the
file (id3 or otherwise), album covers are stored in the album folder. We submit
a users played tracks to last.fm. Names are always case-sensitive, we don't try
to be smart and remove leading spaces or anything, if your collection isn't
tagged correctly it will be presented as such. We have a configurable structure
and if a files location doesn't correspond to its tags we mark it as invalid and
provide facilities for fixing this.

Using
-----

The only way we distribute right now is through our Apt repository. If this
isn't an option for you you'll have to set up everything yourself. Take a look
at *Developing* for some help with that. Also note that we only support MySQL in
the package right now. If you want SQLite support you'll also have to look at
*Developing*.

We've only tested this with **Debian Jessie** and **Ubuntu Saucy**. For other
Debian based distros you're on your own.

### Add Apt Repository

Add the key and the repository.

    $ wget http://apt.opmu.se/opmuse.pub
    $ apt-key add opmuse.pub
    $ echo "deb http://apt.opmu.se/debian/ master main" > /etc/apt/sources.list.d/opmuse.list
    $ apt-get update

### For Debian Jessie

The deb-multimedia repo is required for ffmpeg.

    $ echo "deb http://www.deb-multimedia.org jessie main non-free" > /etc/apt/sources.list.d/deb-multimedia.list
    $ apt-get update
    $ apt-get install deb-multimedia-keyring

Also, you need to add the non-free component in /etc/apt/sources.list for unrar.

### For Ubuntu Saucy

No additional actions required.

### Install opmuse

Finally, install opmuse

    $ apt-get install opmuse

Developing
----------

### Requirements

You need **python 3.3**, **ffmpeg**, **ImageMagick**, **nodejs** (for less.js)
and a Linux environment. This has only been tested on Debian and Exherbo but
most other Linux distros should do as well as other similar \*nix OSes. If
you're on Windows you're on your own.

### Install

    $ git clone https://github.com/opmuse/opmuse.git
    $ cd opmuse
    $ git submodule update --init --recursive
    $ virtualenv -p python3.3 ./virtualenv
    $ source virtualenv/bin/activate
    $ pip install -r requirements.txt
    $ cp config/opmuse.dist.ini config/opmuse.ini
    $ edit config/opmuse.ini # fix library.path

If you just want to use **SQLite**.

    $ ./console database create

If you want to use **MySQL** instead of SQLite (MySQL is recommended).

    $ pip install -r mysql-requirements.txt
    $ edit config/opmuse.ini # fix database.url
    $ ./console database create

If you want some additional dev tools (firepy, repoze.profile).

    $ source virtualenv/bin/activate
    $ pip install -r dev-requirements.txt
    $ ./console cherrypy -- -f # start with firepy (use with cherrypy.request.firepy())
    $ ./console cherrypy -- -p # start with repoze.profile (access it at /__profile__)

You probably want fixtures for some default data (an admin account with password admin for one).

    $ ./console database fixtures

Then you start the whole debacle with

    $ ./console cherrypy

### Upgrading

When you do a git pull some of these might be required.

    $ git submodule update --init --recursive

    $ merge config/opmuse.dist.ini config/opmuse.ini

    $ pip install --upgrade -r requirements.txt
    $ pip install --upgrade -r mysql-requirements.txt
    $ pip install --upgrade -r dev-requirements.txt

    $ ./console database reset # will initiate rescan, might not be required
    $ ./console database update

Here's opmuse
-------------

This is a taste of what it looks like, hopefully it's not too outdated at time of viewing.

![A screenshot.](https://github.com/opmuse/opmuse/raw/master/screen1.png)
