# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Celery tasks."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os

from maasserver.enum import ARCHITECTURE
from maastesting.celery import CeleryFixture
from maastesting.factory import factory
from maastesting.matchers import ContainsAll
from maastesting.testcase import TestCase
from provisioningserver.enum import POWER_TYPE
from provisioningserver.power.poweraction import PowerActionFail
from provisioningserver.tasks import (
    power_off,
    power_on,
    write_tftp_config_for_node,
    )
from testresources import FixtureResource
from testtools.matchers import FileContains

# An arbitrary MAC address.  Not using a properly random one here since
# we might accidentally affect real machines on the network.
arbitrary_mac = "AA:BB:CC:DD:EE:FF"


class TestPowerTasks(TestCase):

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def test_ether_wake_power_on_with_not_enough_template_args(self):
        # In eager test mode the assertion is raised immediately rather
        # than being stored in the AsyncResult, so we need to test for
        # that instead of using result.get().
        self.assertRaises(
            PowerActionFail, power_on.delay, POWER_TYPE.WAKE_ON_LAN)

    def test_ether_wake_power_on(self):
        result = power_on.delay(POWER_TYPE.WAKE_ON_LAN, mac=arbitrary_mac)
        self.assertTrue(result.successful())

    def test_ether_wake_does_not_support_power_off(self):
        self.assertRaises(
            PowerActionFail, power_off.delay,
            POWER_TYPE.WAKE_ON_LAN, mac=arbitrary_mac)


class TestTFTPTasks(TestCase):

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def test_write_tftp_config_for_node_writes_files(self):
        arch = ARCHITECTURE.i386
        mac = factory.getRandomMACAddress()
        mac2 = factory.getRandomMACAddress()
        target_dir = self.make_dir()
        kernel = factory.getRandomString()
        menutitle = factory.getRandomString()
        append = factory.getRandomString()

        result = write_tftp_config_for_node.delay(
            arch, (mac, mac2), pxe_target_dir=target_dir, menutitle=menutitle,
            kernelimage=kernel, append=append)

        self.assertTrue(result.successful(), result)
        expected_file1 = os.path.join(
            target_dir, arch, "generic", "pxelinux.cfg", mac.replace(":", "-"))
        expected_file2 = os.path.join(
            target_dir, arch, "generic", "pxelinux.cfg",
            mac2.replace(":", "-"))
        self.assertThat(
            expected_file1,
            FileContains(matcher=ContainsAll((kernel, menutitle, append))))
        self.assertThat(
            expected_file2,
            FileContains(matcher=ContainsAll((kernel, menutitle, append))))
