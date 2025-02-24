#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Bootloader module."""

from maascommon.osystem import BOOT_IMAGE_PURPOSE
from maascommon.osystem.bootloader import BootLoaderOS
from maastesting.factory import factory


class TestCustomOS:
    def test_get_default_release(self):
        osystem = BootLoaderOS()
        assert "" == osystem.get_default_release()

    def test_get_release_title(self):
        osystem = BootLoaderOS()
        release = factory.make_name("release")
        assert release == osystem.get_release_title(release)

    def test_get_boot_image_purposes(self):
        osystem = BootLoaderOS()
        assert [
            BOOT_IMAGE_PURPOSE.BOOTLOADER
        ] == osystem.get_boot_image_purposes()
