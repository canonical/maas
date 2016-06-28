# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the start up utility."""

__all__ = []

import os
from unittest.mock import call

from maasserver import (
    eventloop,
    locks,
    start_up,
)
from maasserver.enum import (
    NODE_TYPE,
    NODE_TYPE_CHOICES,
)
from maasserver.models.node import RegionController
from maasserver.models.signals import bootsources
from maasserver.testing.eventloop import RegionEventLoopFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks
from maasserver.worker_user import get_worker_user
from maastesting.matchers import (
    MockCalledOnce,
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from provisioningserver.path import get_path
from provisioningserver.utils.env import set_maas_id
from provisioningserver.utils.testing import MAASIDFixture


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

    def test_refresh_on_master(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

        self.patch(start_up, 'is_master_process').return_value = True
        self.patch(start_up, 'register_mac_type')
        mock_refresh = self.patch_autospec(RegionController, 'refresh')
        start_up.start_up()
        self.assertThat(mock_refresh, MockCalledOnce())

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
        self.patch(start_up, "post_commit_do")
        with post_commit_hooks:
            start_up.inner_start_up()
        self.assertThat(start_up.dns_kms_setting_changed, MockCalledOnceWith())

    def test__doesnt_call_dns_kms_setting_changed_if_not_master(self):
        self.patch(start_up, "is_master_process").return_value = False
        with post_commit_hooks:
            start_up.inner_start_up()
        self.assertThat(start_up.dns_kms_setting_changed, MockNotCalled())

    def test__creates_region_obj_if_master(self):
        self.patch(start_up, "is_master_process").return_value = True
        self.patch(start_up, "set_maas_id")
        mock_create_region_obj = self.patch_autospec(
            start_up, "create_region_obj")
        with post_commit_hooks:
            start_up.inner_start_up()
        self.assertThat(mock_create_region_obj, MockCalledOnce())

    def test__doesnt_create_region_obj_if_not_master(self):
        self.patch(start_up, "is_master_process").return_value = False
        mock_create_region_obj = self.patch_autospec(
            start_up, "create_region_obj")
        with post_commit_hooks:
            start_up.inner_start_up()
        self.assertThat(mock_create_region_obj, MockNotCalled())

    def test__creates_maas_id_file(self):
        self.patch(start_up, "is_master_process").return_value = True
        mock_set_maas_id = self.patch_autospec(start_up, "set_maas_id")
        self.patch(start_up.RegionController, 'refresh')
        with post_commit_hooks:
            start_up.inner_start_up()
        self.assertThat(mock_set_maas_id, MockCalledOnce())

    def test__doesnt_create_maas_id_file_if_not_master(self):
        self.patch(start_up, "is_master_process").return_value = False
        mock_set_maas_id = self.patch_autospec(start_up, "set_maas_id")
        with post_commit_hooks:
            start_up.inner_start_up()
        self.assertThat(mock_set_maas_id, MockNotCalled())


class TestCreateRegionObj(MAASServerTestCase):

    """Tests for the actual work done in `create_region_obj`."""

    def test__creates_obj(self):
        region = start_up.create_region_obj()
        self.assertIsNotNone(region)
        self.assertIsNotNone(
            RegionController.objects.get(system_id=region.system_id))

    def test__doesnt_read_maas_id_from_cache(self):
        set_maas_id(factory.make_string())
        os.unlink(get_path('/var/lib/maas/maas_id'))
        region = start_up.create_region_obj()
        self.assertIsNotNone(region)
        self.assertIsNotNone(
            RegionController.objects.get(system_id=region.system_id))

    def test__finds_region_by_maas_id(self):
        region = factory.make_RegionController()
        self.useFixture(MAASIDFixture(region.system_id))
        self.assertEquals(region, start_up.create_region_obj())

    def test__finds_region_by_hostname(self):
        region = factory.make_RegionController()
        mock_gethostname = self.patch_autospec(start_up, "gethostname")
        mock_gethostname.return_value = region.hostname
        self.assertEquals(region, start_up.create_region_obj())

    def test__finds_region_by_mac(self):
        region = factory.make_RegionController()
        factory.make_Interface(node=region)
        mock_get_mac_addresses = self.patch_autospec(
            start_up, "get_mac_addresses")
        mock_get_mac_addresses.return_value = [
            nic.mac_address.raw
            for nic in region.interface_set.all()
        ]
        self.assertEquals(region, start_up.create_region_obj())

    def test__converts_rack_to_region_rack(self):
        rack = factory.make_RackController()
        self.useFixture(MAASIDFixture(rack.system_id))
        region_rack = start_up.create_region_obj()
        self.assertEquals(rack, region_rack)
        self.assertEquals(
            region_rack.node_type, NODE_TYPE.REGION_AND_RACK_CONTROLLER)

    def test__converts_node_to_region_rack(self):
        node = factory.make_Node(
            node_type=factory.pick_choice(
                NODE_TYPE_CHOICES,
                but_not=[
                    NODE_TYPE.REGION_CONTROLLER,
                    NODE_TYPE.RACK_CONTROLLER,
                    NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                ]))
        self.useFixture(MAASIDFixture(node.system_id))
        region = start_up.create_region_obj()
        self.assertEquals(node, region)
        self.assertEquals(region.node_type, NODE_TYPE.REGION_CONTROLLER)

    def test__sets_owner_if_none(self):
        region = factory.make_RegionController()
        self.useFixture(MAASIDFixture(region.system_id))
        self.assertEquals(
            get_worker_user(), start_up.create_region_obj().owner)

    def test__leaves_owner_if_set(self):
        region = factory.make_RegionController()
        self.useFixture(MAASIDFixture(region.system_id))
        user = factory.make_User()
        region.owner = user
        region.save()
        self.assertEquals(user, start_up.create_region_obj().owner)
