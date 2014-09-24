# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the CentOS module."""

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
from provisioningserver.drivers.osystem.custom import (
    BOOT_IMAGE_PURPOSE,
    CustomOS,
    )


class TestCustomOS(MAASTestCase):

    def test_get_boot_image_purposes(self):
        osystem = CustomOS()
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
                BOOT_IMAGE_PURPOSE.XINSTALL,
                ])

    def test_is_release_supported(self):
        osystem = CustomOS()
        releases = [factory.make_name('release') for _ in range(3)]
        supported = [
            osystem.is_release_supported(release)
            for release in releases
            ]
        self.assertEqual([True, True, True], supported)

    def test_get_default_release(self):
        osystem = CustomOS()
        self.assertEqual("", osystem.get_default_release())

    def test_get_release_title(self):
        osystem = CustomOS()
        release = factory.make_name('release')
        self.assertEqual(release, osystem.get_release_title(release))
