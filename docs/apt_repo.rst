Setup APT Repo
==============

These docs show you how to setup an APT repo for opmuse with reprepro and build
opmuse's .deb packages. It is done in the inty/opmuse-build docker image here but
can of course be done anywhere that has the right stuff.

.. code-block:: console

    $ cd /srv/opmuse
    $ git pull # or whatever to get the new code
    $ source virtualenv/bin/activate
    $ pip install -r requirements.txt
    $ deactivate
    $ yarn

Optionally set the lastfm key and secret.

.. code-block:: console

    $ python3 setup.py setopt --command global --option lastfm.key --set-value KEY
    $ python3 setup.py setopt --command global --option lastfm.secret --set-value SECRET

Start the build

.. code-block:: console

    $ ./scripts/build-debs.sh /srv/repo buster --debug

Using
-----

You can test it out like this

.. code-block:: console

    $ apt-get update --allow-insecure-repositories
    $ apt-get install opmuse --allow-unauthenticated
