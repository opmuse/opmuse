[![Build Status](https://secure.travis-ci.org/inty/opmuse.png?branch=master)](http://travis-ci.org/inty/opmuse)
      ________________________________________________
     /\     _____ _____ __  ___ __  __ _____ _____    \
     \/    /    //    //  |/  // / / //  __// ___/    /
     /    /    //  __//      // /_/ //__  // ___/    /
    /    /____//__/  /__//__//_____//____//____/    /\
    \_______________________________________________\/

Software supposed to expose your media files and let you stream it anywhere
from the comfort of your web browser.

Get up and running...
---------------------

    $ git submodule init
    $ git submodule update
    $ virtualenv -p python3 ./virtualenv
    $ source virtualenv/bin/activate
    $ pip install -r requirements.txt
    $ cp config/opmuse.ini.dist config/opmuse.ini
    $ ./opmuse/boot.py

... get back to work...
-----------------------

    $ source virtualenv/bin/activate
    $ ./opmuse/boot.py
