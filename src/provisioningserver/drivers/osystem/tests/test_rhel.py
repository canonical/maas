# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the RHEL module."""

from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.osystem.rhel import (
    BOOT_IMAGE_PURPOSE,
    DISTRO_SERIES_DEFAULT,
    RHELOS,
)


class TestRHEL(MAASTestCase):
    def test_get_boot_image_purposes(self):
        osystem = RHELOS()
        expected = osystem.get_boot_image_purposes()
        self.assertIsInstance(expected, list)
        self.assertEqual(expected, [BOOT_IMAGE_PURPOSE.XINSTALL])

    def test_get_default_release(self):
        osystem = RHELOS()
        expected = osystem.get_default_release()
        self.assertEqual(expected, DISTRO_SERIES_DEFAULT)

    def test_get_release_title(self):
        name_titles = {
            "rhel6": "Redhat Enterprise Linux 6",
            "rhel65": "Redhat Enterprise Linux 6.5",
            "rhel7": "Redhat Enterprise Linux 7",
            "rhel71": "Redhat Enterprise Linux 7.1",
            "rhel65": "Redhat Enterprise Linux 6.5",
            "cent": "Redhat Enterprise Linux cent",
            "rhel711": "Redhat Enterprise Linux 7.1 1",
            "rhel71-custom": "Redhat Enterprise Linux 7.1 custom",
        }
        osystem = RHELOS()
        for name, title in name_titles.items():
            self.assertEqual(osystem.get_release_title(name), title)
