# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the UbuntuOS module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from itertools import product
import random

from distro_info import UbuntuDistroInfo
from maastesting.factory import factory
from maastesting.matchers import MockAnyCall
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.osystem import BOOT_IMAGE_PURPOSE
from provisioningserver.drivers.osystem.debian_networking import (
    compose_network_interfaces,
)
from provisioningserver.drivers.osystem.ubuntu import UbuntuOS
import provisioningserver.drivers.osystem.ubuntu as ubuntu_module
from provisioningserver.udev import compose_network_interfaces_udev_rules
from provisioningserver.utils.curtin import compose_recursive_copy
from testtools.matchers import (
    AllMatch,
    HasLength,
    IsInstance,
)


class TestUbuntuOS(MAASTestCase):

    def get_lts_release(self):
        return UbuntuDistroInfo().lts()

    def get_release_title(self, release):
        info = UbuntuDistroInfo()
        for row in info._avail(info._date):
            if row['series'] == release:
                return info._format("fullname", row)
        return None

    def test_get_boot_image_purposes(self):
        osystem = UbuntuOS()
        archs = [factory.make_name('arch') for _ in range(2)]
        subarchs = [factory.make_name('subarch') for _ in range(2)]
        releases = [factory.make_name('release') for _ in range(2)]
        labels = [factory.make_name('label') for _ in range(2)]
        for arch, subarch, release, label in product(
                archs, subarchs, releases, labels):
            expected = osystem.get_boot_image_purposes(
                arch, subarchs, release, label)
            self.assertIsInstance(expected, list)
            self.assertEqual(expected, [
                BOOT_IMAGE_PURPOSE.COMMISSIONING,
                BOOT_IMAGE_PURPOSE.INSTALL,
                BOOT_IMAGE_PURPOSE.XINSTALL,
                BOOT_IMAGE_PURPOSE.DISKLESS,
                ])

    def test_get_default_release(self):
        osystem = UbuntuOS()
        expected = osystem.get_default_release()
        self.assertEqual(expected, self.get_lts_release())

    def test_get_supported_commissioning_releases(self):
        osystem = UbuntuOS()
        expected = osystem.get_supported_commissioning_releases()
        self.assertIsInstance(expected, list)
        self.assertEqual(expected, [self.get_lts_release()])

    def test_default_commissioning_release(self):
        osystem = UbuntuOS()
        expected = osystem.get_default_commissioning_release()
        self.assertEqual(expected, self.get_lts_release())

    def test_get_release_title(self):
        osystem = UbuntuOS()
        info = UbuntuDistroInfo()
        release = random.choice(info.all)
        self.assertEqual(
            osystem.get_release_title(release),
            self.get_release_title(release))


class TestComposeCurtinNetworkPreseed(MAASTestCase):

    def find_preseed(self, preseeds, key):
        """Extract from list of `preseeds` the first one containing `key`."""
        for preseed in preseeds:
            if key in preseed:
                return preseed
        return None

    def test__returns_list_of_dicts(self):
        preseed = UbuntuOS().compose_curtin_network_preseed([], [], {}, {})
        self.assertIsInstance(preseed, list)
        self.assertThat(preseed, HasLength(2))
        [write_files, late_commands] = preseed

        self.assertIsInstance(write_files, dict)
        self.assertIn('write_files', write_files)
        self.assertIsInstance(write_files['write_files'], dict)
        self.assertThat(
            write_files['write_files'].values(),
            AllMatch(IsInstance(dict)))

        self.assertIsInstance(late_commands, dict)
        self.assertIn('late_commands', late_commands)
        self.assertIsInstance(late_commands['late_commands'], dict)
        self.assertThat(
            late_commands['late_commands'].values(),
            AllMatch(IsInstance(list)))

    def test__writes_network_interfaces_file(self):
        interfaces_file = compose_network_interfaces([], [], {}, {})
        write_text_file = self.patch_autospec(
            ubuntu_module, 'compose_write_text_file')

        UbuntuOS().compose_curtin_network_preseed([], [], {}, {})

        temp_path = '/tmp/maas/etc/network/interfaces'
        self.expectThat(
            write_text_file,
            MockAnyCall(temp_path, interfaces_file, permissions=0644))

    def test__writes_udev_rules_file(self):
        udev_file = compose_network_interfaces_udev_rules([])
        write_text_file = self.patch_autospec(
            ubuntu_module, 'compose_write_text_file')

        UbuntuOS().compose_curtin_network_preseed([], [], {}, {})

        temp_path = '/tmp/maas/etc/udev/rules.d/70-persistent-net.rules'
        self.expectThat(
            write_text_file,
            MockAnyCall(temp_path, udev_file, permissions=0644))

    def test__copies_temp_etc_to_real_etc(self):
        preseed = UbuntuOS().compose_curtin_network_preseed([], [], {}, {})
        late_commands = self.find_preseed(preseed, 'late_commands')
        self.assertEqual(
            {'copy_etc': compose_recursive_copy('/tmp/maas/etc', '/')},
            late_commands['late_commands'])
