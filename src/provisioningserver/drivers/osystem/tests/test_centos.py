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
from provisioningserver.drivers.osystem.centos import (
    BOOT_IMAGE_PURPOSE,
    CentOS,
    DISTRO_SERIES_DEFAULT,
)
from testtools.matchers import Equals


class TestCentOS(MAASTestCase):

    def test_get_boot_image_purposes(self):
        osystem = CentOS()
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
        name_supported = {
            "centos6": True,
            "centos65": True,
            "centos7": True,
            "centos71": True,
            "cent65": False,
            "cent": False,
            "centos711": False,
            }
        osystem = CentOS()
        for name, supported in name_supported.items():
            self.expectThat(
                osystem.is_release_supported(name), Equals(supported))

    def test_get_default_release(self):
        osystem = CentOS()
        expected = osystem.get_default_release()
        self.assertEqual(expected, DISTRO_SERIES_DEFAULT)

    def test_get_release_title(self):
        name_titles = {
            "centos6": "CentOS 6.0",
            "centos65": "CentOS 6.5",
            "centos7": "CentOS 7.0",
            "centos71": "CentOS 7.1",
            "cent65": None,
            "cent": None,
            "centos711": None,
            }
        osystem = CentOS()
        for name, title in name_titles.items():
            self.expectThat(
                osystem.get_release_title(name), Equals(title))
