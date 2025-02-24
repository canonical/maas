#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the RHEL module."""

from maascommon.osystem.rhel import (
    BOOT_IMAGE_PURPOSE,
    DISTRO_SERIES_DEFAULT,
    RHELOS,
)


class TestRHEL:
    def test_get_boot_image_purposes(self):
        osystem = RHELOS()
        expected = osystem.get_boot_image_purposes()
        assert isinstance(expected, list)
        assert expected == [BOOT_IMAGE_PURPOSE.XINSTALL]

    def test_get_default_release(self):
        osystem = RHELOS()
        expected = osystem.get_default_release()
        assert expected == DISTRO_SERIES_DEFAULT

    def test_get_release_title(self):
        name_titles = {
            "rhel6": "Redhat Enterprise Linux 6",
            "rhel65": "Redhat Enterprise Linux 6.5",
            "rhel7": "Redhat Enterprise Linux 7",
            "rhel71": "Redhat Enterprise Linux 7.1",
            "cent": "Redhat Enterprise Linux cent",
            "rhel711": "Redhat Enterprise Linux 7.1 1",
            "rhel71-custom": "Redhat Enterprise Linux 7.1 custom",
        }
        osystem = RHELOS()
        for name, title in name_titles.items():
            assert osystem.get_release_title(name) == title
