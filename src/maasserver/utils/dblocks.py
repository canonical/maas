# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Region-wide advisory locking."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DatabaseLock",
    "DatabaseXactLock",

    "DatabaseLockAttemptOutsideTransaction",
    "DatabaseLockAttemptWithoutConnection",
    "DatabaseLockNotHeld",
]

from contextlib import closing
from operator import itemgetter

from django.db import connection

# The fixed classid used for all MAAS locks. See `DatabaseLock` for the
# rationale, and an explanation of this number's origin.
classid = 20120116


class DatabaseLockAttemptWithoutConnection(Exception):
    """A locking attempt was made without a preexisting connection.

    :class:`DatabaseLock` should only be used with a preexisting connection.
    While this restriction is not absolutely necessary, it's here to ensure
    that users of :class:`DatabaseLock` take care with the lifecycle of their
    database connection: a connection that is inadvertently closed (by Django,
    by MAAS, by anything) will release all locks too.
    """


class DatabaseLockAttemptOutsideTransaction(Exception):
    """A locking attempt was made outside of a transaction.

    :class:`DatabaseXactLock` should only be used within a transaction.
    """


class DatabaseLockNotHeld(Exception):
    """A particular lock was not held."""


class DatabaseLockBase(tuple):
    """An advisory lock held in the database.

    Implemented using PostgreSQL's advisory locking functions.

    PostgreSQL's advisory lock functions are all available with a choice
    of two call signatures: (64-bit integer) or (32-bit integer, 32-bit
    integer). Here we use the two-argument form.

    The first argument is fixed at 20120116. This makes it easy to
    identify locks belonging to the MAAS application in PostgreSQL's
    ``pg_locks`` table. For example::

      SELECT objid FROM pg_locks WHERE classid = 20120116;

    returns the second part of the lock key for all locks associated
    with the MAAS application.

    Fwiw, 20120116 is the date on which source history for MAAS began.
    It has no special significance to PostgreSQL, as far as I am aware.

    """

    __slots__ = ()

    classid = property(itemgetter(0))
    objid = property(itemgetter(1))

    def __new__(cls, objid):
        return super(DatabaseLockBase, cls).__new__(cls, (classid, objid))

    def __enter__(self):
        raise NotImplementedError()

    def __exit__(self, *exc_info):
        raise NotImplementedError()

    def __repr__(self):
        return b"<%s classid=%d objid=%d>" % (
            self.__class__.__name__, self[0], self[1])

    def is_locked(self):
        stmt = (
            "SELECT 1 FROM pg_locks, pg_database"
            " WHERE pg_locks.locktype = 'advisory'"
            "   AND pg_locks.classid = %s"
            "   AND pg_locks.objid = %s"
            # objsubid is 2 when using the 2-argument version of the
            # pg_advisory_* locking functions.
            "   AND pg_locks.objsubid = 2"
            "   AND pg_locks.granted"
            # Advisory locks are local to each database so we join to
            # pg_databases to discover the OID of the currrent database.
            "   AND pg_locks.database = pg_database.oid"
            "   AND pg_database.datname = current_database()"
        )
        with closing(connection.cursor()) as cursor:
            cursor.execute(stmt, self)
            return len(cursor.fetchall()) >= 1


def in_transaction():
    """Are we in a transaction?"""
    return (
        connection.in_atomic_block or
        len(connection.transaction_state) > 0)


class DatabaseLock(DatabaseLockBase):
    """An advisory lock obtained with ``pg_advisory_lock``.

    Use this to obtain an exclusive lock on an external, shared, resource.
    Avoid using this to obtain a lock for a database modification because this
    lock must be released before the transaction is committed.

    In most cases you should prefer :py:class:`DatabaseXactLock` instead.

    See :py:class:`DatabaseLockBase`.
    """

    __slots__ = ()

    def __enter__(self):
        if connection.connection is None:
            raise DatabaseLockAttemptWithoutConnection(self)
        with closing(connection.cursor()) as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s, %s)", self)

    def __exit__(self, *exc_info):
        with closing(connection.cursor()) as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s, %s)", self)
            if cursor.fetchone() != (True,):
                raise DatabaseLockNotHeld(self)


class DatabaseXactLock(DatabaseLockBase):
    """An advisory lock obtained with ``pg_advisory_xact_lock``.

    Use this to obtain an exclusive lock for a modification to the database.
    It can be used to synchronise access to an external resource too, but the
    point of release is less explicit because it's outside of the control of
    this class: the lock is only released when the transaction in which it was
    obtained is committed or aborted.

    See :py:class:`DatabaseLockBase`.
    """

    __slots__ = ()

    def __enter__(self):
        """Obtain lock using pg_advisory_xact_lock()."""
        if not in_transaction():
            raise DatabaseLockAttemptOutsideTransaction(self)
        with closing(connection.cursor()) as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", self)

    def __exit__(self, *exc_info):
        """Do nothing: this lock can only be released by the transaction."""
