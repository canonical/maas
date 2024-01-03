# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the CentOS module."""

from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.osystem.centos import (
    BOOT_IMAGE_PURPOSE,
    CentOS,
    DISTRO_SERIES_DEFAULT,
)


class TestCentOS(MAASTestCase):
    def test_get_boot_image_purposes(self):
        osystem = CentOS()
        expected = osystem.get_boot_image_purposes()
        self.assertIsInstance(expected, list)
        self.assertEqual(expected, [BOOT_IMAGE_PURPOSE.XINSTALL])

    def test_get_default_release(self):
        osystem = CentOS()
        expected = osystem.get_default_release()
        self.assertEqual(expected, DISTRO_SERIES_DEFAULT)

    def test_get_release_title(self):
        name_titles = {
            "centos6": "CentOS 6",
            "centos65": "CentOS 6.5",
            "centos66": "CentOS 6",  # See LP: #1654063
            "centos7": "CentOS 7",
            "centos70": "CentOS 7",  # See LP: #1654063
            "centos71": "CentOS 7.1",
            "centos65": "CentOS 6.5",
            "cent": "CentOS cent",
            "centos711": "CentOS 7.1 1",
            "centos71-custom": "CentOS 7.1 custom",
        }
        osystem = CentOS()
        for name, title in name_titles.items():
            self.assertEqual(osystem.get_release_title(name), title)
