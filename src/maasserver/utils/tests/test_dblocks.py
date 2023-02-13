# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.utils.dblocks`."""


from contextlib import closing, contextmanager
import sys

from django.db import connection, reset_queries, transaction

from maasserver.testing.dblocks import lock_held_in_other_thread
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils import dblocks

# Use "high" objid numbers to avoid conflicts with predeclared locks.
objid_min = 2 << 10


def get_locks():
    """Return the set of locks held that's greater than `objid_min`"""
    with closing(connection.cursor()) as cursor:
        cursor.execute(
            "SELECT objid FROM pg_locks, pg_database "
            "WHERE classid = %s AND objid >= %s"
            "   AND pg_locks.database = pg_database.oid"
            "   AND pg_database.datname = current_database()",
            [dblocks.classid, objid_min],
        )
        return {result[0] for result in cursor.fetchall()}


def get_objid():
    """Return a 'high' objid that's won't coincide with predeclared locks.

    It makes use of a DB sequence to ensure that all tests have unique objids.
    """
    with closing(connection.cursor()) as cursor:
        cursor.execute("CREATE SEQUENCE IF NOT EXISTS dblocks_test_seq")
        cursor.execute("select nextval('dblocks_test_seq')")
        [next_value] = cursor.fetchone()
    return objid_min + next_value


@transaction.atomic
def divide_by_zero():
    """Do something stupid in a transaction."""
    0 / 0


@contextmanager
def force_debug_cursor():
    """Set `force_debug_cursor` on Django's default connection."""
    force_debug_cursor = connection.force_debug_cursor
    connection.force_debug_cursor = True
    try:
        yield
    finally:
        connection.force_debug_cursor = force_debug_cursor


def capture_queries_while_holding_lock(lock):
    """Capture SQL being issued to the database.

    Return as a single string with each statement separated by new-line "--"
    new-line.
    """
    with force_debug_cursor():
        reset_queries()
        with lock:
            pass  # Just being here is enough.
    return "\n--\n".join(query["sql"] for query in connection.queries)


class TestDatabaseLock(MAASTransactionServerTestCase):
    scenarios = tuple(
        ("%s/%s" % mode, {"mode": mode})
        for mode in dblocks.DatabaseLock.MODE_CHOICES
    )

    def make_lock(self, objid):
        return dblocks.DatabaseLock(objid, mode=self.mode)

    def tearDown(self):
        super().tearDown()

    def test_create_lock(self):
        objid = get_objid()
        lock = self.make_lock(objid)
        self.assertEqual(lock, (dblocks.classid, objid))

    def test_properties(self):
        lock = self.make_lock(get_objid())
        self.assertEqual(lock, (lock.classid, lock.objid))

    @transaction.atomic
    def test_lock_actually_locked(self):
        objid = get_objid()
        lock = self.make_lock(objid)

        locks_held_before = get_locks()
        with lock:
            locks_held = get_locks()
        locks_held_after = get_locks()

        locks_obtained = locks_held - locks_held_before
        self.assertIn(objid, locks_obtained)

        locks_released = locks_held - locks_held_after
        self.assertIn(objid, locks_released)

    @transaction.atomic
    def test_is_locked(self):
        objid = get_objid()
        lock = self.make_lock(objid)

        self.assertFalse(lock.is_locked())
        with lock:
            self.assertTrue(lock.is_locked())
        self.assertFalse(lock.is_locked())

    def test_lock_remains_held_when_committing_transaction(self):
        objid = get_objid()
        lock = self.make_lock(objid)
        txn = transaction.atomic()

        self.assertFalse(lock.is_locked())
        txn.__enter__()
        self.assertFalse(lock.is_locked())
        lock.__enter__()
        self.assertTrue(lock.is_locked())
        txn.__exit__(None, None, None)
        self.assertTrue(lock.is_locked())
        lock.__exit__(None, None, None)
        self.assertFalse(lock.is_locked())

    def test_lock_remains_held_when_aborting_transaction(self):
        objid = get_objid()
        lock = self.make_lock(objid)
        txn = transaction.atomic()

        self.assertFalse(lock.is_locked())
        txn.__enter__()
        self.assertFalse(lock.is_locked())
        lock.__enter__()
        self.assertTrue(lock.is_locked())

        self.assertRaises(ZeroDivisionError, divide_by_zero)
        exc_info = sys.exc_info()

        txn.__exit__(*exc_info)
        self.assertTrue(lock.is_locked())
        lock.__exit__(None, None, None)
        self.assertFalse(lock.is_locked())

    def test_lock_is_held_around_transaction(self):
        objid = get_objid()
        lock = self.make_lock(objid)

        self.assertFalse(lock.is_locked())
        with lock:
            self.assertTrue(lock.is_locked())
            with transaction.atomic():
                self.assertTrue(lock.is_locked())
            self.assertTrue(lock.is_locked())
        self.assertFalse(lock.is_locked())

    def test_lock_is_held_around_breaking_transaction(self):
        objid = get_objid()
        lock = self.make_lock(objid)

        self.assertFalse(lock.is_locked())
        with lock:
            self.assertTrue(lock.is_locked())
            self.assertRaises(ZeroDivisionError, divide_by_zero)
            self.assertTrue(lock.is_locked())
        self.assertFalse(lock.is_locked())

    def test_lock_requires_preexisting_connection(self):
        objid = get_objid()
        connection.close()
        lock = self.make_lock(objid)
        self.assertRaises(
            dblocks.DatabaseLockAttemptWithoutConnection, lock.__enter__
        )

    def test_releasing_lock_fails_when_lock_not_held(self):
        objid = get_objid()
        lock = self.make_lock(objid)
        self.assertRaises(dblocks.DatabaseLockNotHeld, lock.__exit__)

    def test_repr(self):
        lock = self.make_lock(get_objid())
        self.assertEqual(
            "<DatabaseLock classid=%d objid=%d lock=%s unlock=%s>"
            % (lock[0], lock[1], self.mode[0], self.mode[1]),
            repr(lock),
        )


class TestDatabaseLockVariations(MAASServerTestCase):
    def test_plain_variation(self):
        lock = dblocks.DatabaseLock(get_objid())
        self.assertDocTestMatches(
            """\
            SELECT pg_advisory_lock(...)
            --
            SELECT pg_advisory_unlock(...)
            """,
            capture_queries_while_holding_lock(lock),
        )

    def test_try_variation(self):
        lock = dblocks.DatabaseLock(get_objid())
        self.assertEqual(lock, lock.TRY)
        self.assertDocTestMatches(
            """\
            SELECT pg_try_advisory_lock(...)
            --
            SELECT pg_advisory_unlock(...)
            """,
            capture_queries_while_holding_lock(lock.TRY),
        )

    def test_shared_variation(self):
        lock = dblocks.DatabaseLock(get_objid())
        self.assertEqual(lock, lock.SHARED)
        self.assertDocTestMatches(
            """\
            SELECT pg_advisory_lock_shared(...)
            --
            SELECT pg_advisory_unlock_shared(...)
            """,
            capture_queries_while_holding_lock(lock.SHARED),
        )

    def test_try_shared_variation(self):
        lock = dblocks.DatabaseLock(get_objid())
        self.assertEqual(lock, lock.TRY.SHARED)
        self.assertDocTestMatches(
            """\
            SELECT pg_try_advisory_lock_shared(...)
            --
            SELECT pg_advisory_unlock_shared(...)
            """,
            capture_queries_while_holding_lock(lock.TRY.SHARED),
        )


class TestDatabaseXactLock(MAASTransactionServerTestCase):
    scenarios = tuple(
        ("%s/%s" % mode, {"mode": mode})
        for mode in dblocks.DatabaseXactLock.MODE_CHOICES
    )

    def make_lock(self, objid):
        return dblocks.DatabaseXactLock(objid, mode=self.mode)

    def test_create_lock(self):
        objid = get_objid()
        lock = self.make_lock(objid)
        self.assertEqual(lock, (dblocks.classid, objid))

    def test_properties(self):
        lock = self.make_lock(get_objid())
        self.assertEqual(lock, (lock.classid, lock.objid))

    def test_lock_actually_locked(self):
        objid = get_objid()
        lock = self.make_lock(objid)

        with transaction.atomic():
            locks_held_before = get_locks()
            with lock:
                locks_held = get_locks()
            locks_held_after = get_locks()
        locks_held_after_txn = get_locks()

        locks_obtained = locks_held - locks_held_before
        self.assertIn(objid, locks_obtained)

        locks_released = locks_held - locks_held_after
        self.assertNotIn(objid, locks_released)

        locks_released_with_txn = locks_held - locks_held_after_txn
        self.assertIn(objid, locks_released_with_txn)

    def test_is_locked(self):
        objid = get_objid()
        lock = self.make_lock(objid)

        with transaction.atomic():
            self.assertFalse(lock.is_locked())
            with lock:
                self.assertTrue(lock.is_locked())
            self.assertTrue(lock.is_locked())

        # The lock is released with the end of the transaction.
        self.assertFalse(lock.is_locked())

    def test_obtaining_lock_fails_when_outside_of_transaction(self):
        objid = get_objid()
        lock = self.make_lock(objid)
        self.assertRaises(
            dblocks.DatabaseLockAttemptOutsideTransaction, lock.__enter__
        )

    def test_releasing_lock_does_nothing(self):
        objid = get_objid()
        lock = self.make_lock(objid)
        self.assertIsNone(lock.__exit__())

    def test_repr(self):
        lock = self.make_lock(get_objid())
        self.assertEqual(
            "<DatabaseXactLock classid=%d objid=%d lock=%s unlock=%s>"
            % (lock[0], lock[1], self.mode[0], self.mode[1]),
            repr(lock),
        )


class TestDatabaseXactLockVariations(MAASServerTestCase):
    def test_plain_variation(self):
        lock = dblocks.DatabaseXactLock(get_objid())
        self.assertDocTestMatches(
            "SELECT pg_advisory_xact_lock(...)",
            capture_queries_while_holding_lock(lock),
        )

    def test_try_variation(self):
        lock = dblocks.DatabaseXactLock(get_objid())
        self.assertEqual(lock, lock.TRY)
        self.assertDocTestMatches(
            "SELECT pg_try_advisory_xact_lock(...)",
            capture_queries_while_holding_lock(lock.TRY),
        )

    def test_shared_variation(self):
        lock = dblocks.DatabaseXactLock(get_objid())
        self.assertEqual(lock, lock.SHARED)
        self.assertDocTestMatches(
            "SELECT pg_advisory_xact_lock_shared(...)",
            capture_queries_while_holding_lock(lock.SHARED),
        )

    def test_try_shared_variation(self):
        lock = dblocks.DatabaseXactLock(get_objid())
        self.assertEqual(lock, lock.TRY.SHARED)
        self.assertDocTestMatches(
            "SELECT pg_try_advisory_xact_lock_shared(...)",
            capture_queries_while_holding_lock(lock.TRY.SHARED),
        )


class TestTryingToAcquireLockedLock(MAASServerTestCase):
    """Test what happens when trying to acquire a lock that's already taken."""

    scenarios = (
        ("DatabaseLock", dict(make_lock=dblocks.DatabaseLock)),
        ("DatabaseXactLock", dict(make_lock=dblocks.DatabaseXactLock)),
    )

    def test_try_variation_when_already_exclusively_locked(self):
        lock = self.make_lock(get_objid())
        with lock_held_in_other_thread(lock):
            self.assertRaises(dblocks.DatabaseLockNotHeld, lock.TRY.__enter__)

    def test_try_variation_when_already_share_locked(self):
        lock = self.make_lock(get_objid())
        with lock_held_in_other_thread(lock.SHARED):
            self.assertRaises(dblocks.DatabaseLockNotHeld, lock.TRY.__enter__)

    def test_try_shared_variation_when_already_exclusively_locked(self):
        lock = self.make_lock(get_objid())
        with lock_held_in_other_thread(lock):
            self.assertRaises(
                dblocks.DatabaseLockNotHeld, lock.TRY.SHARED.__enter__
            )

    def test_try_shared_variation_when_already_share_locked(self):
        lock = self.make_lock(get_objid())
        with lock_held_in_other_thread(lock.SHARED):
            with lock.SHARED:
                pass  # No exception.
