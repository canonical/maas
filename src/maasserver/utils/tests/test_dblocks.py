# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.utils.dblocks`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from contextlib import closing

from django.db import (
    connection,
    transaction,
    )
from maasserver.utils import dblocks
from maastesting.testcase import MAASTestCase


def get_locks():
    """Return the set of locks held."""
    stmt = "SELECT objid FROM pg_locks WHERE classid = %s"
    with closing(connection.cursor()) as cursor:
        cursor.execute(stmt, [dblocks.classid])
        return {result[0] for result in cursor.fetchall()}


class TestDatabaseLock(MAASTestCase):

    def test_create_lock(self):
        objid = self.getUniqueInteger()
        lock = dblocks.DatabaseLock(objid)
        self.assertEqual(lock, (dblocks.classid, objid))

    def test_properties(self):
        lock = dblocks.DatabaseLock(self.getUniqueInteger())
        self.assertEqual(lock, (lock.classid, lock.objid))

    @transaction.atomic
    def test_lock_actually_locked(self):
        objid = self.getUniqueInteger()
        lock = dblocks.DatabaseLock(objid)

        locks_held_before = get_locks()
        with lock:
            locks_held = get_locks()
        locks_held_after = get_locks()

        locks_obtained = locks_held - locks_held_before
        self.assertEqual({objid}, locks_obtained)

        locks_released = locks_held - locks_held_after
        self.assertEqual({objid}, locks_released)

    @transaction.atomic
    def test_is_locked(self):
        objid = self.getUniqueInteger()
        lock = dblocks.DatabaseLock(objid)

        self.assertFalse(lock.is_locked())
        with lock:
            self.assertTrue(lock.is_locked())
        self.assertFalse(lock.is_locked())

    def test_obtaining_lock_fails_when_outside_of_transaction(self):
        objid = self.getUniqueInteger()
        lock = dblocks.DatabaseLock(objid)
        self.assertRaises(
            dblocks.DatabaseLockAttemptOutsideTransaction,
            lock.__enter__)

    def test_releasing_lock_fails_when_lock_not_held(self):
        objid = self.getUniqueInteger()
        lock = dblocks.DatabaseLock(objid)
        self.assertRaises(dblocks.DatabaseLockNotHeld, lock.__exit__)

    def test_repr(self):
        lock = dblocks.DatabaseLock(self.getUniqueInteger())
        self.assertEqual(
            "<DatabaseLock classid=%d objid=%d>" % lock,
            repr(lock))
