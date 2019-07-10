Setup APT Repo
==============

These docs show you how to setup an APT repo for opmuse with reprepro and build
opmuse's .deb packages. It is done in the inty/opmuse-dev docker image here but
can of course be done anywhere that has the right stuff.

Create reprepro structure

.. code-block:: console

    $ cd /srv
    $ mkdir -p repo/conf

Add this to repo/conf/distributions

.. code-block:: conf

    Origin: opmuse
    Label: opmuse
    Suite: master
    Codename: master
    Architectures: i386 amd64
    Components: main
    Description: Apt repository for opmuse

Then install some stuff we need

.. code-block:: console

    $ apt-get install reprepro ruby ruby-dev
    $ gem install fpm

Clone and prepare the repo

.. code-block:: console

    $ git clone https://github.com/opmuse/opmuse.git
    $ cd opmuse
    $ cp config/opmuse.dist.ini config/opmuse.ini
    $ ./console jinja compile build/templates
    $ yarn

Set the lastfm key and secret.

.. code-block:: console

    $ python3 setup.py setopt --command global --option lastfm.key --set-value KEY
    $ python3 setup.py setopt --command global --option lastfm.secret --set-value SECRET

Start the build

.. code-block:: console

    $ ./scripts/build-debs.sh /srv/repo

Using
-----

You can test it out like this

.. code-block:: console

    $ echo "deb file:///srv/repo master main" >> /etc/apt/sources.list
    $ apt-get update
    $ apt-get install opmuse

Note though that this conflicts with the opmuse running in inty/opmuse-dev as both defaults to 8080.

Update / Rebuild
----------------

To start a rebuild do this

.. code-block:: console

    $ rm -rf build
    $ ./console jinja compile build/templates
    $ yarn
    $ ./scripts/build-debs.sh /srv/reprepro
