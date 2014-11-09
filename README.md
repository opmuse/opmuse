What is opmuse?
---------------

<img align="right" src="https://github.com/opmuse/opmuse/raw/master/assets/opossum-readme.png" />

opmuse is a web application to play, organize, share and make your music library social.

We go by a couple of words. We don't exclusively store metadata about your
library or generate data in our database. We trust the data provided for us. We
care about structure.

What this means is that artist, album and title are always stored as tags on the
file (id3 or otherwise) and only indexed in the database. Album covers are
stored in the track's folder. Additional metadata that does not fit in the
file's tags we store in opmuse.txt in the track's folder. We submit users'
played tracks to last.fm and then fetch this data from there. Names are always
case-sensitive and we don't try to be smart and remove leading spaces or
anything, if your collection isn't tagged correctly it will be presented as
such. We have a configurable structure and if a file's location doesn't
correspond to its tags we mark it as invalid and provide facilities for fixing
this.

Note that opmuse is under development and is **not considered stable**.

Using
-----

The only way we distribute right now is through our Apt repository. If this
isn't an option for you you'll have to set up everything yourself. Take a look
at *Developing* for some help with that. Also note that we only support MySQL in
the package right now. If you want SQLite support you'll also have to look at
*Developing*.

We've only tested this with **Debian Jessie**. Other Debian based distros should
work as long as they have all the required dependencies that arent provided in
our apt repo.

### Add repo

Add the key and the repository.

    $ wget http://apt.opmu.se/opmuse.pub
    $ apt-key add opmuse.pub
    $ echo "deb http://apt.opmu.se/debian/ master main" > /etc/apt/sources.list.d/opmuse.list
    $ apt-get update

#### For Debian Jessie

The deb-multimedia repo is required for ffmpeg.

    $ echo "deb http://www.deb-multimedia.org jessie main non-free" > /etc/apt/sources.list.d/deb-multimedia.list
    $ apt-get update
    $ apt-get install deb-multimedia-keyring

You need to add the non-free component in /etc/apt/sources.list for unrar.
There's also a bug in whoosh versions >2.4.1 right now so you need to pin
python3-whoosh like so.

    $ cat /etc/apt/preferences.d/opmuse
    Package: python3-whoosh
    Pin: version 2.4.1
    Pin-Priority: 1000

### Install opmuse

Finally, install opmuse

    $ apt-get install opmuse

Here is opmuse
--------------

![A screenshot](https://github.com/opmuse/opmuse/raw/master/screen1.png)

Developing
----------

For documentation on development please go to [opmuse.readthedocs.org](http://opmuse.readthedocs.org/en/latest/).
