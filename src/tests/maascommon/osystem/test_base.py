#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maascommon.osystem`."""

from unittest.mock import sentinel

from maascommon.osystem import OperatingSystemRegistry
from maastesting.factory import factory
from tests.utils.assertions import assert_unordered_items_equal


class TestOperatingSystem:
    def test_is_release_supported(self, temporary_os):
        releases = [factory.make_name("release") for _ in range(3)]
        supported = [
            temporary_os.is_release_supported(release) for release in releases
        ]
        assert [True, True, True] == supported

    def test_format_release_choices(self, temporary_os):
        releases = temporary_os.get_supported_releases()
        assert_unordered_items_equal(
            [(release, release) for release in releases],
            temporary_os.format_release_choices(releases),
        )


class TestOperatingSystemRegistry:
    def test_operating_system_registry(self, osystem_registry):
        assert [] == list(OperatingSystemRegistry)
        OperatingSystemRegistry.register_item("resource", sentinel.resource)
        assert sentinel.resource in (
            item for name, item in OperatingSystemRegistry
        )
