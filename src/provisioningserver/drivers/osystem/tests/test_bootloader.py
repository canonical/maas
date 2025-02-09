# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Bootloader module."""

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.osystem import BOOT_IMAGE_PURPOSE
from provisioningserver.drivers.osystem.bootloader import BootLoaderOS


class TestCustomOS(MAASTestCase):
    def test_get_default_release(self):
        osystem = BootLoaderOS()
        self.assertEqual("", osystem.get_default_release())

    def test_get_release_title(self):
        osystem = BootLoaderOS()
        release = factory.make_name("release")
        self.assertEqual(release, osystem.get_release_title(release))

    def test_get_boot_image_purposes(self):
        osystem = BootLoaderOS()
        self.assertEqual(
            [BOOT_IMAGE_PURPOSE.BOOTLOADER],
            osystem.get_boot_image_purposes(),
        )
