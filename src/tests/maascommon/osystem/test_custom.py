#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Custom module."""

from maascommon.osystem.custom import BOOT_IMAGE_PURPOSE, CustomOS
from maastesting.factory import factory


class TestCustomOS:
    def test_get_boot_image_purposes(self):
        osystem = CustomOS()
        expected = osystem.get_boot_image_purposes()
        assert isinstance(expected, list)
        assert expected == [BOOT_IMAGE_PURPOSE.XINSTALL]

    def test_get_default_release(self):
        osystem = CustomOS()
        assert "" == osystem.get_default_release()

    def test_get_release_title(self):
        osystem = CustomOS()
        release = factory.make_name("release")
        assert release == osystem.get_release_title(release)
