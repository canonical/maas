# Copyright 2017-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the UbuntuCore module."""

from maascommon.osystem import BOOT_IMAGE_PURPOSE, UbuntuCoreOS
from maastesting.factory import factory


class TestUbuntuCoreOS:
    def test_get_boot_image_purposes(self):
        osystem = UbuntuCoreOS()
        expected = osystem.get_boot_image_purposes()
        assert isinstance(expected, list)
        assert expected == [BOOT_IMAGE_PURPOSE.XINSTALL]

    def test_get_default_release(self):
        osystem = UbuntuCoreOS()
        assert "16" == osystem.get_default_release()

    def test_get_release_title(self):
        osystem = UbuntuCoreOS()
        release = factory.make_name("release")
        assert release == osystem.get_release_title(release)
