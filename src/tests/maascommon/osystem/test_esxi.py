# Copyright 2018-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the ESXi module."""

from maascommon.osystem import BOOT_IMAGE_PURPOSE
from maascommon.osystem.esxi import ESXi


class TestESXi:
    def test_get_boot_image_purposes(self):
        osystem = ESXi()
        expected = osystem.get_boot_image_purposes()
        assert isinstance(expected, list)
        assert expected == [BOOT_IMAGE_PURPOSE.XINSTALL]

    def test_get_default_release(self):
        osystem = ESXi()
        expected = osystem.get_default_release()
        assert expected == "6.7"

    def test_get_release_title(self):
        name_titles = {
            "6": "VMware ESXi 6",
            "6.7": "VMware ESXi 6.7",
            "6.7.0": "VMware ESXi 6.7.0",
            "6-custom": "VMware ESXi 6 custom",
            "6.7-custom": "VMware ESXi 6.7 custom",
            "6.7.0-custom": "VMware ESXi 6.7.0 custom",
            "custom": "VMware ESXi custom",
        }
        osystem = ESXi()
        for name, title in name_titles.items():
            assert osystem.get_release_title(name) == title
