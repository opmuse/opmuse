Testing
=======

We use `nose`_ to run and write our tests. This is how we run the tests,
assuming you've setup a dev environment according to :doc:`gettingstarted`
first.

.. _`nose`: https://nose.readthedocs.org/

.. code-block:: console

    $ source virtualenv/bin/activate
    $ pip install -r dev-requirements.txt
    $ nosetests -w opmuse/test/

Regular tests
-------------

First we have regular tests for services and utilities. They're just plain test
classes optionally with some setup and teardown methods for the database and
such.

Controller tests
----------------

Second we have controller tests that utilizes cherrypy's test framework to test
controllers.
