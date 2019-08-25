What is opmuse?
---------------

<img align="right" src="https://github.com/opmuse/opmuse/raw/master/assets/images/opossum-readme.png" />

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

### Docker

You can use our docker image to test things out.

    # docker pull inty/opmuse
    # docker run -d -p 8080:8080 inty/opmuse

You'll reach opmuse at http://localhost:8080/ and you can login with admin and no password.

### Debian Repo

We provide a Debian Buster repo which you can configure like this.

    # echo "deb https://apt.opmu.se/debian/ buster main" > /etc/apt/sources.list.d/opmuse.list
    # curl -s https://apt.opmu.se/opmuse.pub | apt-key add -
    # apt-get update
    # apt-get install opmuse

Then you can access opmuse with the details you provided during installation.

Here is opmuse
--------------

![A screenshot](https://github.com/opmuse/opmuse/raw/master/screen1.png)

Developing
----------

For documentation on development please go to [opmuse.readthedocs.org](http://opmuse.readthedocs.org/en/latest/).
