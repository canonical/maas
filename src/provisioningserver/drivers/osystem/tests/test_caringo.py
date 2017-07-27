# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the UbuntuOS module."""

__all__ = []

from itertools import product
import os

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.osystem import BOOT_IMAGE_PURPOSE
from provisioningserver.drivers.osystem.caringo import CaringoOS


class TestCaringoOS(MAASTestCase):

    def test_get_boot_image_purposes(self):
        osystem = CaringoOS()
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
                BOOT_IMAGE_PURPOSE.EPHEMERAL,
                ])

    def test_get_default_release(self):
        osystem = CaringoOS()
        expected = osystem.get_default_release()
        self.assertEqual(expected, "")

    def test_get_release_title(self):
        osystem = CaringoOS()
        self.assertEqual(
            osystem.get_release_title("9.0"),
            "9.0")

    def test_get_xinstall_parameters_returns_squashfs(self):
        osystem = CaringoOS()
        self.patch(os.path, 'exists').return_value = True
        self.assertItemsEqual(
            ('root-tgz', 'tgz'),
            osystem.get_xinstall_parameters(
                factory.make_name('arch'), factory.make_name('subarch'),
                factory.make_name('release'), factory.make_name('label')))
