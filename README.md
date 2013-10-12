What is opmuse?
---------------

A web application to play, organize and share your music library.

Setup
-----

### Requirements

You need **python 3.3**, **ffmpeg**, **ImageMagick**, **nodejs** (for less) and
a Linux environment. This has only been tested on Debian and Exherbo but most
other Linux distros should do as well as other similar \*nix OSes. If you're on
Windows you're on your own.

### Install

```Shell
$ git clone https://github.com/opmuse/opmuse.git
$ cd opmuse
$ git submodule init
$ git submodule update
$ virtualenv -p python3.3 ./virtualenv
$ source virtualenv/bin/activate
$ pip install -r requirements.txt
$ cp config/opmuse.dist.ini config/opmuse.ini
$ edit config/opmuse.ini
$ ./run.sh
```

If you want MySQL support and some additional dev-tools you should do this.

```Shell
$ source virtualenv/bin/activate
$ pip install -r optional-requirements.txt
```

You probably want fixtures for some default data (an admin account with password
admin for one).

```Shell
$ source virtualenv/bin/activate
$ python opmuse/fixtures.py
```

### Upgrading

When you do a git pull some of these might be required.

```Shell
$ git submodule init
$ git submodule update

$ merge config/opmuse.dist.ini config/opmuse.ini

$ pip install -r requirements.txt

$ pip install -r optional-requirements.txt

$ rm opmuse.db # e.g. drop database..
$ rm -rf cache/index/* # remove whoosh index
```

Our Doctrine
------------

  - We don't exclusively store metadata about your library.

    i.e. artist, album, title are always stored as actual tags on the file. Album covers are stored on the filesystem etc.

  - Data generated exclusively in opmuse is worthless.

    i.e. A users played tracks are submitted to last.fm

  - We trust the data provided for us.

    i.e. Names are always case-sensitive. We don't try to be smart and remove leading spaces or anything, if your collection isn't tagged correctly you will suffer.

  - We care about structure.

    i.e. If a file's location doesn't correspond to its tags we mark it as invalid and provide facilities for fixing this.

Here's opmuse
-------------

This is a taste of what it looks like, hopefully it's not too outdated at time of viewing.

![A screenshot.](https://github.com/opmuse/opmuse/raw/master/screen1.png)
