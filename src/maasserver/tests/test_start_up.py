# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the start up utility."""

__all__ = []

import random
from unittest.mock import call

from maasserver import eventloop, locks, start_up
from maasserver.models.config import Config
from maasserver.models.node import RegionController
from maasserver.models.notification import Notification
from maasserver.models.signals import bootsources
from maasserver.testing.eventloop import RegionEventLoopFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import post_commit_hooks
from maastesting.matchers import (
    DocTestMatches,
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.twisted import extract_result, TwistedLoggerFixture
from provisioningserver.drivers.osystem.ubuntu import UbuntuOS
from provisioningserver.utils.env import get_maas_id
from provisioningserver.utils.testing import MAASIDFixture
from testtools.matchers import HasLength, Is, IsInstance, Not
from twisted.internet import reactor
from twisted.internet.defer import Deferred


class TestStartUp(MAASTransactionServerTestCase):

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

        locked = factory.make_exception("locked")
        unlocked = factory.make_exception("unlocked")

        def check_lock(_):
            raise locked if locks.startup.is_locked() else unlocked

        self.patch(start_up, "register_mac_type").side_effect = check_lock
        self.assertRaises(type(locked), start_up.inner_start_up, master=False)

    def test_start_up_retries_with_wait_on_exception(self):
        inner_start_up = self.patch(start_up, "inner_start_up")
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
        self.expectThat(
            inner_start_up,
            MockCallsMatch(call(master=False), call(master=False)),
        )
        # It also slept once, for 3 seconds, between those attempts.
        self.expectThat(start_up.pause, MockCalledOnceWith(3.0))


class TestInnerStartUp(MAASServerTestCase):
    """Tests for the actual work done in `inner_start_up`."""

    def setUp(self):
        super(TestInnerStartUp, self).setUp()
        self.useFixture(MAASIDFixture(None))
        self.patch_autospec(start_up, "dns_kms_setting_changed")
        self.patch_autospec(start_up, "load_builtin_scripts")
        self.patch_autospec(start_up, "post_commit_do")
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

    def test__calls_dns_kms_setting_changed_if_master(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=True)
        self.assertThat(start_up.dns_kms_setting_changed, MockCalledOnceWith())

    def test__does_not_call_dns_kms_setting_changed_if_not_master(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertThat(start_up.dns_kms_setting_changed, MockNotCalled())

    def test__calls_load_builtin_scripts_if_master(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=True)
        self.assertThat(start_up.load_builtin_scripts, MockCalledOnceWith())

    def test__does_not_call_load_builtin_scripts_if_not_master(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertThat(start_up.load_builtin_scripts, MockNotCalled())

    def test__resets_deprecated_commissioning_release_if_master(self):
        Config.objects.set_config(
            "commissioning_distro_series", random.choice(["precise", "trusty"])
        )
        with post_commit_hooks:
            start_up.inner_start_up(master=True)
        ubuntu = UbuntuOS()
        self.assertEquals(
            Config.objects.get_config("commissioning_distro_series"),
            ubuntu.get_default_commissioning_release(),
        )
        self.assertTrue(
            Notification.objects.filter(
                ident="commissioning_release_deprecated"
            ).exists()
        )

    def test__doesnt_reset_deprecated_commissioning_release_if_notmaster(self):
        release = random.choice(["precise", "trusty"])
        Config.objects.set_config("commissioning_distro_series", release)
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertEquals(
            Config.objects.get_config("commissioning_distro_series"), release
        )
        self.assertFalse(
            Notification.objects.filter(
                ident="commissioning_release_deprecated"
            ).exists()
        )

    def test__refreshes_if_master(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=True)
        region = RegionController.objects.first()
        self.assertThat(
            start_up.post_commit_do,
            MockCalledOnceWith(
                reactor.callLater, 0, start_up.refreshRegion, region
            ),
        )

    def test__does_refresh_if_not_master(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertThat(start_up.post_commit_do, MockNotCalled())

    def test__doesnt_call_dns_kms_setting_changed_if_not_master(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertThat(start_up.dns_kms_setting_changed, MockNotCalled())

    def test__creates_region_controller(self):
        self.assertThat(RegionController.objects.all(), HasLength(0))
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertThat(RegionController.objects.all(), HasLength(1))

    def test__creates_maas_id_file(self):
        self.assertThat(get_maas_id(), Is(None))
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertThat(get_maas_id(), Not(Is(None)))

    def test__creates_maas_uuid(self):
        self.assertThat(get_maas_id(), Is(None))
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        uuid = Config.objects.get_config("uuid")
        self.assertThat(uuid, Not(Is(None)))


class TestFunctions(MAASServerTestCase):
    """Tests for other functions in the `start_up` module."""

    def test_regionRefresh_refreshes_a_region(self):
        region = factory.make_RegionController()
        self.patch(region, "refresh").return_value = Deferred()
        d = start_up.refreshRegion(region)
        self.assertThat(d, IsInstance(Deferred))
        exception = factory.make_exception_type()
        with TwistedLoggerFixture() as logger:
            d.errback(exception("boom"))
            # The exception is suppressed ...
            self.assertThat(extract_result(d), Is(None))
        # ... but it has been logged.
        self.assertThat(
            logger.output,
            DocTestMatches(
                """
                Failure when refreshing region.
                Traceback (most recent call last):...
                Failure: maastesting.factory.TestException#...: boom
                """
            ),
        )
