Contributing
============

Here's some rules that should be followed and things to think about when
contributing code to opmuse.

Code style
----------

Coding styles for the different languages we use. One thing to keep in mind for
all of these is that readability is more important than convention and
convention is more important than performance.

Python
~~~~~~

We use `PEP8`_ but we have a max line length of 120 chars, though we try to keep
the lines at around 80 chars.

.. _`PEP8`: http://www.python.org/dev/peps/pep-0008

Javascript
~~~~~~~~~~

For Javascript we follow a style based on the `Crockford code conventions`_
with a few extra rules and exceptions.

- Lines shouldn't be longer than 120 chars but try to keep them at around 80 chars.
- Everything should be a requirejs module.
- Singleton requirejs modules should be lowercase.
- Class requirejs modules should start with uppercase.
- requirejs dependencies should be declared on seperate lines
- 'use strict' should be used.

Here's a simple example.

.. code-block:: javascript

    define([
            'module1',
            'module2',
        ], function (module1, module2) {

        'use strict';

        // code
    });

.. _`Crockford code conventions`: http://javascript.crockford.com/code.html

Jinja
~~~~~

As there really isn't any good Jinja style checkers or even style guides out
there just try to think like PEP8 when coding Jinja. Use 4 spaces for
indentation, maximum line length of 120 chars but try to keep them at around 80
chars. Also, indent both HTML tags and Jinja control structures.

Here's a simple example.

.. code-block:: jinja

    <ul>
        {% for item in items %}
            <li>
                {{ item.name }}
            </li>
        {% endfor %}
    </ul>

Less & CSS
~~~~~~~~~~

Here's some guidelines to follow for Less and CSS.

- 4 spaces for indentation
- Max line length of 120 chars but try to keep them at around 80 chars
- Curly brackets on same line as selector
- Seperate selectors with comma AND newline.

Here's a simple example.

.. code-block:: css

    ul li,
    dl dt {
        margin: 0;
        padding: 0;
    }

Shell script
~~~~~~~~~~~~

Use 4 spaces, max line length of 120 chars but try to keep them at around 80
chars.

Git
---

Try to follow `this style guide`_ when writing commit messages.

.. _`this style guide`: http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html


