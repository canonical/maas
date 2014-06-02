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
    "DatabaseLockAttemptOutsideTransaction",
    "DatabaseLockNotHeld",
]

from contextlib import closing
from operator import itemgetter

from django.db import connection

# The fixed classid used for all MAAS locks. See `DatabaseLock` for the
# rationale, and an explanation of this number's origin.
classid = 20120116


class DatabaseLockAttemptOutsideTransaction(Exception):
    """A locking attempt was made outside of a transaction.

    :class:`DatabaseLock` should only be used within a transaction.
    Django agressively closes connections outside of atomic blocks to
    the extent that session-level locks are rendered unreliable at best.
    """


class DatabaseLockNotHeld(Exception):
    """A particular lock was not held."""


class DatabaseLock(tuple):
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
        return super(cls, DatabaseLock).__new__(cls, (classid, objid))

    def __enter__(self):
        if not connection.in_atomic_block:
            raise DatabaseLockAttemptOutsideTransaction(self)
        with closing(connection.cursor()) as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s, %s)", self)

    def __exit__(self, *exc_info):
        with closing(connection.cursor()) as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s, %s)", self)
            if cursor.fetchone() != (True,):
                raise DatabaseLockNotHeld(self)

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
