# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random
from unittest.mock import call

from testtools.matchers import HasLength, Is, Not

from maasserver import eventloop, locks, start_up
from maasserver.models.config import Config
from maasserver.models.node import RegionController
from maasserver.models.notification import Notification
from maasserver.models.signals import bootsources
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.eventloop import RegionEventLoopFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import post_commit_hooks
from maastesting import get_testing_timeout
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from provisioningserver.drivers.osystem.ubuntu import UbuntuOS
from provisioningserver.utils import ipaddr
from provisioningserver.utils.deb import DebVersionsInfo
from provisioningserver.utils.env import get_maas_id
from provisioningserver.utils.testing import MAASIDFixture


class TestStartUp(MAASTransactionServerTestCase):

    """Tests for the `start_up` function.

    The actual work happens in `inner_start_up` and `test_start_up`; the tests
    you see here are for the locking wrapper only.
    """

    def setUp(self):
        super().setUp()
        self.useFixture(RegionEventLoopFixture())
        self.patch(ipaddr, "get_ip_addr").return_value = {}

    def tearDown(self):
        super().tearDown()
        # start_up starts the Twisted event loop, so we need to stop it.
        eventloop.reset().wait(get_testing_timeout())

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
    def setUp(self):
        super().setUp()
        self.useFixture(MAASIDFixture(None))
        self.patch_autospec(start_up, "dns_kms_setting_changed")
        self.patch(ipaddr, "get_ip_addr").return_value = {}
        self.versions_info = DebVersionsInfo(
            current={"version": "1:3.1.0-1234-g.deadbeef"}
        )
        self.patch(
            start_up, "get_versions_info"
        ).return_value = self.versions_info

    def test_calls_dns_kms_setting_changed_if_master(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=True)
        self.assertThat(start_up.dns_kms_setting_changed, MockCalledOnceWith())

    def test_does_not_call_dns_kms_setting_changed_if_not_master(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertThat(start_up.dns_kms_setting_changed, MockNotCalled())

    def test_calls_load_builtin_scripts_if_master(self):
        self.patch_autospec(start_up, "load_builtin_scripts")
        with post_commit_hooks:
            start_up.inner_start_up(master=True)
        self.assertThat(start_up.load_builtin_scripts, MockCalledOnceWith())

    def test_does_not_call_load_builtin_scripts_if_not_master(self):
        self.patch_autospec(start_up, "load_builtin_scripts")
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertThat(start_up.load_builtin_scripts, MockNotCalled())

    def test_resets_deprecated_commissioning_release_if_master(self):
        Config.objects.set_config(
            "commissioning_distro_series", random.choice(["precise", "trusty"])
        )
        with post_commit_hooks:
            start_up.inner_start_up(master=True)
        ubuntu = UbuntuOS()
        self.assertEqual(
            Config.objects.get_config("commissioning_distro_series"),
            ubuntu.get_default_commissioning_release(),
        )
        self.assertTrue(
            Notification.objects.filter(
                ident="commissioning_release_deprecated"
            ).exists()
        )

    def test_doesnt_reset_deprecated_commissioning_release_if_notmaster(self):
        release = random.choice(["precise", "trusty"])
        Config.objects.set_config("commissioning_distro_series", release)
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertEqual(
            Config.objects.get_config("commissioning_distro_series"), release
        )
        self.assertFalse(
            Notification.objects.filter(
                ident="commissioning_release_deprecated"
            ).exists()
        )

    def test_sets_maas_url_master(self):
        Config.objects.set_config("maas_url", "http://default.example.com/")
        self.useFixture(
            RegionConfigurationFixture(maas_url="http://custom.example.com/")
        )
        with post_commit_hooks:
            start_up.inner_start_up(master=True)

        self.assertEqual(
            "http://custom.example.com/", Config.objects.get_config("maas_url")
        )

    def test_sets_maas_url_not_master(self):
        Config.objects.set_config("maas_url", "http://default.example.com/")
        self.useFixture(
            RegionConfigurationFixture(maas_url="http://my.example.com/")
        )
        with post_commit_hooks:
            start_up.inner_start_up(master=False)

        self.assertEqual(
            "http://default.example.com/",
            Config.objects.get_config("maas_url"),
        )

    def test_doesnt_call_dns_kms_setting_changed_if_not_master(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertThat(start_up.dns_kms_setting_changed, MockNotCalled())

    def test_creates_region_controller(self):
        self.assertThat(RegionController.objects.all(), HasLength(0))
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertThat(RegionController.objects.all(), HasLength(1))

    def test_creates_maas_id_file(self):
        self.assertThat(get_maas_id(), Is(None))
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertThat(get_maas_id(), Not(Is(None)))

    def test_creates_maas_uuid(self):
        self.assertThat(get_maas_id(), Is(None))
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        uuid = Config.objects.get_config("uuid")
        self.assertThat(uuid, Not(Is(None)))

    def test_syncs_deprecation_notifications(self):
        Notification(ident="deprecation_test", message="some text").save()
        with post_commit_hooks:
            start_up.inner_start_up(master=True)
        # existing deprecations are removed since none is active
        self.assertEqual(
            Notification.objects.filter(
                ident__startswith="deprecation_"
            ).count(),
            0,
        )

    def test_updates_version(self):
        with post_commit_hooks:
            start_up.inner_start_up()
        region = RegionController.objects.first()
        self.assertEqual(region.version, "1:3.1.0-1234-g.deadbeef")
        self.assertEqual(region.info.install_type, "deb")
