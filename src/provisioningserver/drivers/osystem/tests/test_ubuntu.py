# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the UbuntuOS module."""


import random
from unittest.mock import Mock, patch

from distro_info import UbuntuDistroInfo

from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.osystem import BOOT_IMAGE_PURPOSE, ubuntu
from provisioningserver.drivers.osystem.ubuntu import UbuntuOS


class TestUbuntuOS(MAASTestCase):
    def get_lts_release(self):
        # return UbuntuDistroInfo().lts()
        return "jammy"

    def get_release_title(self, release):
        info = UbuntuDistroInfo()
        for row in info._avail(info._date):
            row_dict = row
            if not isinstance(row, dict):
                row_dict = row.__dict__
            if row_dict["series"] == release:
                return info._format("fullname", row)
        return None

    def test_get_boot_image_purposes(self):
        osystem = UbuntuOS()
        expected = osystem.get_boot_image_purposes()
        self.assertIsInstance(expected, list)
        self.assertEqual(
            expected,
            [
                BOOT_IMAGE_PURPOSE.COMMISSIONING,
                BOOT_IMAGE_PURPOSE.INSTALL,
                BOOT_IMAGE_PURPOSE.XINSTALL,
                BOOT_IMAGE_PURPOSE.DISKLESS,
            ],
        )

    def test_is_release_supported(self):
        osystem = UbuntuOS()
        info = UbuntuDistroInfo()
        self.assertTrue(osystem.is_release_supported(random.choice(info.all)))

    def test_get_lts_release(self):
        # Canary so we know when the lts changes
        osystem = UbuntuOS()
        self.assertEqual("jammy", osystem.get_lts_release())

    def test_get_default_release(self):
        osystem = UbuntuOS()
        expected = osystem.get_default_release()
        self.assertEqual(expected, self.get_lts_release())

    def test_get_supported_commissioning_releases(self):
        ubuntu_distro_info_mock = Mock()
        ubuntu_distro_info_mock.is_lts.return_value = True
        ubuntu_distro_info_mock.supported_esm.return_value = [
            "xenial",
            "bionic",
            "focal",
            "jammy",
            "noble",
            "resolute",
        ]
        with patch.object(
            ubuntu,
            "UbuntuDistroInfo",
            Mock(return_value=ubuntu_distro_info_mock),
        ):
            osystem = UbuntuOS()
            releases = osystem.get_supported_commissioning_releases()
        self.assertIsInstance(releases, list)
        self.assertSequenceEqual(
            ["bionic", "focal", "jammy", "noble", "resolute"], releases
        )

    def test_get_supported_commissioning_releases_excludes_non_lts(self):
        supported = ["bionic", "focal", "jammy", "noble"]
        ubuntu_distro_info_mock = Mock()
        ubuntu_distro_info_mock.supported_esm.return_value = supported
        with patch.object(
            ubuntu,
            "UbuntuDistroInfo",
            Mock(return_value=ubuntu_distro_info_mock),
        ):
            osystem = UbuntuOS()
            releases = osystem.get_supported_commissioning_releases()
        self.assertIsInstance(releases, list)
        udi = UbuntuDistroInfo()
        non_lts_releases = [name for name in supported if not udi.is_lts(name)]
        for release in non_lts_releases:
            self.assertNotIn(release, releases)

    def test_default_commissioning_release(self):
        osystem = UbuntuOS()
        expected = osystem.get_default_commissioning_release()
        self.assertEqual(expected, self.get_lts_release())

    def test_get_release_title(self):
        osystem = UbuntuOS()
        info = UbuntuDistroInfo()
        release = random.choice(info.all)
        self.assertEqual(
            osystem.get_release_title(release), self.get_release_title(release)
        )
