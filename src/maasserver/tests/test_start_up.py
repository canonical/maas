# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the start up utility."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from multiprocessing import (
    Process,
    Value,
    )

from lockfile import (
    FileLock,
    LockTimeout,
    )
from maasserver import start_up
from maasserver.models.nodegroup import NodeGroup
from maastesting.fakemethod import FakeMethod
from maastesting.testcase import TestCase


class TestStartUp(TestCase):
    """Testing for the method `start_up`."""

    def setUp(self):
        super(TestStartUp, self).setUp()
        self.patch(start_up, 'LOCK_FILE_NAME', self.make_file())

    def test_start_up_calls_setup_maas_avahi_service(self):
        recorder = FakeMethod()
        self.patch(start_up, 'setup_maas_avahi_service', recorder)
        start_up.start_up()
        self.assertEqual(
            (1, [()]),
            (recorder.call_count, recorder.extract_args()))

    def test_start_up_calls_write_full_dns_config(self):
        recorder = FakeMethod()
        self.patch(start_up, 'write_full_dns_config', recorder)
        start_up.start_up()
        self.assertEqual(
            (1, [()]),
            (recorder.call_count, recorder.extract_args()))

    def test_start_up_creates_master_nodegroup(self):
        start_up.start_up()
        self.assertEqual(1, NodeGroup.objects.all().count())

    def test_start_up_runs_in_exclusion(self):
        called = Value('b', False)

        def check_lock():
            called.value = True
            lock = FileLock(start_up.LOCK_FILE_NAME)
            self.assertRaises(LockTimeout, lock.acquire, timeout=0.1)

        def check_lock_in_subprocess():
             proc = Process(target=check_lock)
             proc.start()
             proc.join()

        self.patch(start_up, 'inner_start_up', check_lock_in_subprocess)
        start_up.start_up()
        self.assertTrue(called.value)

    def test_start_up_respects_timeout_to_acquire_lock(self):
        recorder = FakeMethod()
        self.patch(start_up, 'inner_start_up', recorder)
        # Use a timeout more suitable for automated testing.
        self.patch(start_up, 'LOCK_TIMEOUT', 0.1)
        # Manually create a lock.
        self.make_file(FileLock(start_up.LOCK_FILE_NAME).lock_file)

        self.assertRaises(LockTimeout, start_up.start_up)
        self.assertEqual(0, recorder.call_count)
