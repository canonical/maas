# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the UbuntuOS module."""

__all__ = []

from itertools import product
import random

from distro_info import UbuntuDistroInfo
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.osystem import BOOT_IMAGE_PURPOSE
from provisioningserver.drivers.osystem.ubuntu import UbuntuOS


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
