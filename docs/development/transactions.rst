.. -*- mode: rst -*-

------------
Transactions
------------


How we roll(back) in MAAS
-------------------------

MAAS runs almost all transactions using `serializable isolation`_. This
is very strict and PostgreSQL can and does reject transactions because
of conflicts with other transactions; this are business-as-usual.

.. _serializable isolation:
   http://www.postgresql.org/docs/9.4/static/transaction-iso.html

MAAS is prepared for this, and will retry transactions that have failed
because of these specific types of conflicts. MAAS has two tools to deal
with serialisation failures:

* :py:class:`~maasserver.utils.views.WebApplicationHandler` deals with
  failures in MAAS's Django application (the web UI and API). This is
  the shim between Twisted's web server and Django's WSGI application.
  It's not designed for any other purpose.

* :py:func:`~maasserver.utils.orm.transactional` is used to decorate
  functions and methods such that they're run within transactions. This
  is general purpose, and can be used almost everywhere in the MAAS
  region controller.

Slightly different strategies are employed in each, but they share a lot
of their implementations.

.. note::

  Only MAAS's region — a.k.a. ``regiond`` — connects to the PostgreSQL
  database. MAAS's clusters — ``clusterd`` — are not directly relevant
  here.


Always prefer @transactional
----------------------------

MAAS's :py:func:`~maasserver.utils.orm.transactional` decorator, in
almost all situations, should be used to ensure that a piece of code
runs within a transaction.

It has very similar behaviour to Django's ``transaction.atomic`` — for
good reason; it is based around it — so has savepoint-commit/rollback
semantics when encountered within an existing transaction. In fact, when
called from within a web or API request — i.e. within a transaction —
it'll behave *exactly* like ``transaction.atomic``.

However, if it's ever called from outside of a transaction, via
``deferToThread`` for example, it'll also ensure that transactions are
retried after serialisation failures, that post-commit hooks are run,
and that connections are cleared up at the end.

Even where we know that code cannot be reached from outside of a
transaction, it's a good habit to always use ``transactional`` in
preference to ``transaction.atomic``. It's an easier rule to follow.
Uses of ``transaction.atomic`` should also be exceptions and thus few in
number, rendering them easy to audit.

If you find that ``transactional`` doesn't Do The Right Thing for you,
treat it first as a bug to be fixed before reaching for another tool.


Except that…
------------

* ``transactional`` cannot be used as a context manager — and it can't
  be adapted into one, because of its retry behaviour — so::

    with transaction.atomic():
        do_stuff()

  can be okay. *However*, this should typically be inside a function
  that is decorated with ``transactional``, or in a private function
  that's only ever called from within a transaction that's being wrapped
  by ``transactional``.

  In other words, you would only do this if you want to run a block of
  code with savepoint-commit/rollback behaviour, and a context manager
  is more convenient or appropriate than defining a new function
  decorated with ``transactional``.

* ``transaction.atomic`` is also okay as a context manager in **tests**,
  because you shouldn't run into serialisation failures there, and you
  may want more control over how post-commit hooks are handled anyway.

  Don't stress about this too much though: as long as your test inherits
  ``PostCommitHooksTestMixin`` *as most region tests already do* then
  your tests will fail if post-commit hooks are left dangling.
