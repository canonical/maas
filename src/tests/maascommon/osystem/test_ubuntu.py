# Copyright 2014-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the UbuntuOS module."""

import random
from unittest.mock import Mock

from distro_info import UbuntuDistroInfo

from maascommon.osystem import BOOT_IMAGE_PURPOSE
from maascommon.osystem.ubuntu import UbuntuOS


class TestUbuntuOS:
    def get_lts_release(self):
        # return UbuntuDistroInfo().lts()
        return "noble"

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
        assert isinstance(expected, list)
        assert expected == [
            BOOT_IMAGE_PURPOSE.COMMISSIONING,
            BOOT_IMAGE_PURPOSE.INSTALL,
            BOOT_IMAGE_PURPOSE.XINSTALL,
            BOOT_IMAGE_PURPOSE.DISKLESS,
        ]

    def test_is_release_supported(self):
        osystem = UbuntuOS()
        info = UbuntuDistroInfo()
        assert osystem.is_release_supported(random.choice(info.all)) is True

    def test_get_lts_release(self):
        # Canary so we know when the lts changes
        osystem = UbuntuOS()
        assert "noble" == osystem.get_lts_release()

    def test_get_default_release(self):
        osystem = UbuntuOS()
        expected = osystem.get_default_release()
        assert expected == self.get_lts_release()

    def test_get_supported_commissioning_releases(self):
        ubuntu_distro_info_mock = Mock(UbuntuDistroInfo)
        ubuntu_distro_info_mock.is_lts.return_value = True
        ubuntu_distro_info_mock.is_lts.supported.return_value = [
            "xenial",
            "bionic",
            "focal",
            "jammy",
            "noble",
        ]
        osystem = UbuntuOS()
        releases = osystem.get_supported_commissioning_releases()
        assert isinstance(releases, list)
        assert ["bionic", "focal", "jammy", "noble"] == releases

    def test_get_supported_commissioning_releases_excludes_non_lts(self):
        supported = ["bionic", "focal", "jammy", "noble"]
        ubuntu_distro_info_mock = Mock(UbuntuDistroInfo)
        ubuntu_distro_info_mock.supported.return_value = supported
        osystem = UbuntuOS()
        releases = osystem.get_supported_commissioning_releases()
        assert isinstance(releases, list)
        udi = UbuntuDistroInfo()
        non_lts_releases = [name for name in supported if not udi.is_lts(name)]
        for release in non_lts_releases:
            assert release not in releases

    def test_get_supported_commissioning_releases_excludes_deprecated(self):
        """Make sure we remove 'precise' from the list."""
        ubuntu_distro_info_mock = Mock(UbuntuDistroInfo)
        ubuntu_distro_info_mock.supported.return_value = [
            "precise",
            "trusty",
            "vivid",
            "wily",
            "xenial",
        ]
        osystem = UbuntuOS()
        releases = osystem.get_supported_commissioning_releases()
        assert isinstance(releases, list)
        assert "precise" not in releases
        assert "trusty" not in releases

    def test_get_supported_commissioning_releases_excludes_unsupported_lts(
        self,
    ):
        ubuntu_distro_info_mock = Mock(UbuntuDistroInfo)
        ubuntu_distro_info_mock.supported.return_value = [
            "precise",
            "trusty",
            "vivid",
            "wily",
            "xenial",
        ]
        unsupported = [
            "warty",
            "hoary",
            "breezy",
            "dapper",
            "edgy",
            "feisty",
            "gutsy",
            "hardy",
            "intrepid",
            "jaunty",
            "karmic",
            "lucid",
            "maverick",
            "natty",
            "oneiric",
            "quantal",
            "raring",
            "saucy",
            "utopic",
        ]
        ubuntu_distro_info_mock.unsupported.return_value = unsupported
        osystem = UbuntuOS()
        releases = osystem.get_supported_commissioning_releases()
        assert isinstance(releases, list)
        for release in unsupported:
            assert release not in releases

    def test_default_commissioning_release(self):
        osystem = UbuntuOS()
        expected = osystem.get_default_commissioning_release()
        assert expected == self.get_lts_release()

    def test_get_release_title(self):
        osystem = UbuntuOS()
        info = UbuntuDistroInfo()
        release = random.choice(info.all)
        assert osystem.get_release_title(release) == self.get_release_title(
            release
        )

    def test_get_release_version(self):
        osystem = UbuntuOS()
        tests = [
            ("warty", "4.10"),
            ("xenial", "16.04"),
            ("bionic", "18.04"),
            ("mantic", "23.10"),
        ]
        for release, expected_version in tests:
            assert osystem.get_release_version(release) == expected_version
