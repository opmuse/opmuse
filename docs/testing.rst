Testing
=======

We use `nose`_ to run and write our tests. This is how we do, assuming you've
setup a dev environment according to :doc:`gettingstarted` first.

.. _`nose`: https://nose.readthedocs.org/

.. code-block:: console

    $ source virtualenv/bin/activate
    $ pip install -r dev-requirements.txt
    $ nosetests -w tests/
