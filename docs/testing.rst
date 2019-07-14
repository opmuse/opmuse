Testing
=======

We use `pytest`_ to run and write our tests. This is how we run the tests,
assuming you've setup a dev environment according to :doc:`gettingstarted`
first.

.. _`pytest`: https://pytest.readthedocs.io/

.. code-block:: console

    $ pip install -r dev-requirements.txt
    $ pytest opmuse/test/

Regular tests
-------------

First we have regular tests for services and utilities. They're just plain test
classes optionally with some setup and teardown methods for the database and
such.

Controller tests
----------------

Second we have controller tests that utilizes cherrypy's test framework to test
controllers.
