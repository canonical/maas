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

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.osystem.ubuntu import (
    BOOT_IMAGE_PURPOSE,
    COMMISIONING_DISTRO_SERIES,
    COMMISIONING_DISTRO_SERIES_DEFAULT,
    DISTRO_SERIES_CHOICES,
    DISTRO_SERIES_DEFAULT,
    UbuntuOS,
    )


class TestUbuntuOS(MAASTestCase):

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

    def test_get_supported_releases(self):
        osystem = UbuntuOS()
        expected = osystem.get_supported_releases()
        self.assertIsInstance(expected, list)
        self.assertEqual(expected, DISTRO_SERIES_CHOICES.keys())

    def test_get_default_release(self):
        osystem = UbuntuOS()
        expected = osystem.get_default_release()
        self.assertEqual(expected, DISTRO_SERIES_DEFAULT)

    def test_get_supported_commissioning_releases(self):
        osystem = UbuntuOS()
        expected = osystem.get_supported_commissioning_releases()
        self.assertIsInstance(expected, list)
        self.assertEqual(expected, COMMISIONING_DISTRO_SERIES)

    def test_default_commissioning_release(self):
        osystem = UbuntuOS()
        expected = osystem.get_default_commissioning_release()
        self.assertEqual(expected, COMMISIONING_DISTRO_SERIES_DEFAULT)

    def test_get_release_title(self):
        osystem = UbuntuOS()
        self.assertEqual(
            {release: osystem.get_release_title(release)
             for release in osystem.get_supported_releases()},
            DISTRO_SERIES_CHOICES)

    def test_format_release_choices(self):
        osystem = UbuntuOS()
        releases = osystem.get_supported_releases()
        formatted = osystem.format_release_choices(releases)
        for name, title in formatted:
            self.assertEqual(DISTRO_SERIES_CHOICES[name], title)
