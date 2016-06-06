# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the start up utility."""

__all__ = []

from unittest.mock import call

from maasserver import (
    eventloop,
    locks,
    start_up,
)
from maasserver.models.signals import bootsources
from maasserver.testing.eventloop import RegionEventLoopFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)


class LockChecker:

    """Callable.  Records calls, and whether the startup lock was held."""

    def __init__(self, lock_file=None):
        self.call_count = 0
        self.lock_was_held = None

    def __call__(self, *args, **kwargs):
        self.call_count += 1
        self.lock_was_held = locks.startup.is_locked()


class TestStartUp(MAASServerTestCase):

    """Tests for the `start_up` function.

    The actual work happens in `inner_start_up` and `test_start_up`; the tests
    you see here are for the locking wrapper only.
    """

    def setUp(self):
        super(TestStartUp, self).setUp()
        self.useFixture(RegionEventLoopFixture())

    def tearDown(self):
        super(TestStartUp, self).tearDown()
        # start_up starts the Twisted event loop, so we need to stop it.
        eventloop.reset().wait(5)

    def test_inner_start_up_runs_in_exclusion(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

        lock_checker = LockChecker()
        self.patch(start_up, 'register_mac_type', lock_checker)
        start_up.inner_start_up()
        self.assertEqual(1, lock_checker.call_count)
        self.assertEqual(True, lock_checker.lock_was_held)

    def test_start_up_retries_with_wait_on_exception(self):
        inner_start_up = self.patch(start_up, 'inner_start_up')
        inner_start_up.side_effect = [
            factory.make_exception("Boom!"),
            None,  # Success.
        ]
        # We don't want to really sleep.
        self.patch(start_up, "pause")
        # start_up() returns without error.
        start_up.start_up()
        # However, it did call inner_start_up() twice; the first call resulted
        # in the "Boom!" exception so it tried again.
        self.expectThat(inner_start_up, MockCallsMatch(call(), call()))
        # It also slept once, for 3 seconds, between those attempts.
        self.expectThat(start_up.pause, MockCalledOnceWith(3.0))


class TestInnerStartUp(MAASServerTestCase):

    """Tests for the actual work done in `inner_start_up`."""

    def setUp(self):
        super(TestInnerStartUp, self).setUp()
        self.patch_autospec(start_up, 'dns_kms_setting_changed')
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

    def test__calls_dns_kms_setting_changed_if_master(self):
        self.patch(start_up, "is_master_process").return_value = True
        start_up.inner_start_up()
        self.assertThat(start_up.dns_kms_setting_changed, MockCalledOnceWith())

    def test__doesnt_call_dns_kms_setting_changed_if_not_master(self):
        self.patch(start_up, "is_master_process").return_value = False
        start_up.inner_start_up()
        self.assertThat(start_up.dns_kms_setting_changed, MockNotCalled())
