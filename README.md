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

... get back to work...
-----------------------

    $ ./run.sh

MySQL
-----

For MySQL support you'll have to [download and install oursql manually](https://launchpad.net/oursql/py3k/py3k-0.9.3).

[![Build Status](https://secure.travis-ci.org/opmuse/opmuse.png?branch=master)](http://travis-ci.org/inty/opmuse)
