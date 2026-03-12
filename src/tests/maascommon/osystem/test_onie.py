# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maascommon.osystem import BOOT_IMAGE_PURPOSE
from maascommon.osystem.onie import ONIEOS, parse_release


class TestONIEOS:
    def test_get_boot_image_purposes(self):
        onie = ONIEOS()
        purposes = onie.get_boot_image_purposes()
        assert purposes == [BOOT_IMAGE_PURPOSE.XINSTALL]

    @pytest.mark.parametrize(
        "release,expected_vendor,expected_version",
        [
            ("mellanox-3.8.0", "mellanox", "3.8.0"),
            ("dell-2023.05", "dell", "2023.05"),
            ("dellemc-1.0.0", "dellemc", "1.0.0"),
            ("edge-core-2023.02", "edge-core", "2023.02"),
            ("accton-2022.11", "accton", "2022.11"),
            ("nvidia-3.9.1", "nvidia", "3.9.1"),
            ("supermicro-1.0.0", "supermicro", "1.0.0"),
        ],
    )
    def test_parse_release_valid(
        self, release, expected_vendor, expected_version
    ):
        result = parse_release(release)
        assert result is not None
        vendor, version = result
        assert vendor == expected_vendor
        assert version == expected_version

    @pytest.mark.parametrize(
        "release",
        [
            "",
            "vendor",
            "vendor-",
            "-version",
            "vendor_underscore-1.0",
            "vendor-v1.0",
            "vendor--1.0",
        ],
    )
    def test_parse_release_invalid(self, release):
        assert parse_release(release) is None

    def test_parse_release_normalizes_uppercase(self):
        result = parse_release("VENDOR-1.0")
        assert result == ("vendor", "1.0")

    @pytest.mark.parametrize(
        "release,expected",
        [
            ("mellanox-3.8.0", True),
            ("dell-2023.05", True),
            ("custom-vendor-1.0", True),
            ("invalid", False),
            ("vendor-", False),
            ("", False),
        ],
    )
    def test_is_release_supported(self, release, expected):
        onie = ONIEOS()
        assert onie.is_release_supported(release) == expected

    @pytest.mark.parametrize(
        "release,expected_title",
        [
            ("mellanox-3.8.0", "Mellanox ONIE 3.8.0"),
            ("dell-2023.05", "Dell ONIE 2023.05"),
            ("dellemc-1.0.0", "Dell EMC ONIE 1.0.0"),
            ("nvidia-3.9.1", "NVIDIA ONIE 3.9.1"),
            ("edge-core-2023.02", "Edge-Core ONIE 2023.02"),
            ("accton-2022.11", "Accton ONIE 2022.11"),
        ],
    )
    def test_get_release_title(self, release, expected_title):
        onie = ONIEOS()
        assert onie.get_release_title(release) == expected_title

    def test_get_release_title_unknown_vendor(self):
        onie = ONIEOS()
        title = onie.get_release_title("unknown-vendor-1.0.0")
        assert "Unknown-Vendor" in title
        assert "1.0.0" in title

    def test_get_release_title_invalid(self):
        onie = ONIEOS()
        invalid_release = "invalid"
        assert onie.get_release_title(invalid_release) == invalid_release

    def test_get_vendor_from_release(self):
        onie = ONIEOS()
        assert onie.get_vendor_from_release("mellanox-3.8.0") == "mellanox"
        assert onie.get_vendor_from_release("dell-2023.05") == "dell"
        assert onie.get_vendor_from_release("invalid") is None

    def test_get_version_from_release(self):
        onie = ONIEOS()
        assert onie.get_version_from_release("mellanox-3.8.0") == "3.8.0"
        assert onie.get_version_from_release("dell-2023.05") == "2023.05"
        assert onie.get_version_from_release("invalid") is None

    @pytest.mark.parametrize(
        "vendor,version,expected",
        [
            ("mellanox", "3.8.0", "mellanox-3.8.0"),
            ("dell", "2023.05", "dell-2023.05"),
            ("edge-core", "2023.02", "edge-core-2023.02"),
            ("NVIDIA", "3.9.1", "nvidia-3.9.1"),
        ],
    )
    def test_format_release_name(self, vendor, version, expected):
        onie = ONIEOS()
        assert onie.format_release_name(vendor, version) == expected

    @pytest.mark.parametrize(
        "vendor,version",
        [
            ("", "3.8.0"),
            ("mellanox", ""),
            ("Mellanox Space", "3.8.0"),
            ("mellanox", "3.8.0-beta"),
            ("_mellanox", "3.8.0"),
        ],
    )
    def test_format_release_name_invalid(self, vendor, version):
        onie = ONIEOS()
        with pytest.raises(ValueError):
            onie.format_release_name(vendor, version)

    def test_get_image_filetypes(self):
        onie = ONIEOS()
        filetypes = onie.get_image_filetypes()

        assert "installer.bin" in filetypes
        assert filetypes["installer.bin"] == "self-extracting"
