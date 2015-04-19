=====================
sphinxcontrib-actdiag
=====================

.. image:: https://travis-ci.org/tk0miya/sphinxcontrib-actdiag.svg?branch=master
   :target: https://travis-ci.org/tk0miya/sphinxcontrib-actdiag

.. image:: https://coveralls.io/repos/tk0miya/sphinxcontrib-actdiag/badge.png?branch=master
   :target: https://coveralls.io/r/tk0miya/sphinxcontrib-actdiag?branch=master

.. image:: https://codeclimate.com/github/tk0miya/sphinxcontrib-actdiag/badges/gpa.svg
   :target: https://codeclimate.com/github/tk0miya/sphinxcontrib-actdiag

A sphinx extension for embedding activity diagram using actdiag_.

This extension enables you to insert activity diagrams into your document.
Following code is an example::

   .. actdiag::

      actdiag {
        A -> B -> C -> D;

        lane {
          A; B;
        }
        lane {
          C; D;
        }
      }

.. _actdiag: http://bitbucket.org/blockdiag/actdiag/


For more details, see `online documentation`_ at http://blockdiag.com/.

.. _online documentation: http://blockdiag.com/en/actdiag/sphinxcontrib.html
