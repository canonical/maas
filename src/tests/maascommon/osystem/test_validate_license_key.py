# Copyright 2014-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maascommon.osystem`."""

import random
from unittest.mock import Mock, sentinel

import pytest

import maascommon.osystem as osystems
from maastesting.factory import factory


class TestValidateLicenseKey:
    def test_validates_key(self, temporary_os):
        release = random.choice(temporary_os.get_supported_releases())

        os_specific_validate_license_key_mock = Mock()
        temporary_os.validate_license_key = (
            os_specific_validate_license_key_mock
        )
        osystems.validate_license_key(temporary_os.name, release, sentinel.key)
        os_specific_validate_license_key_mock.assert_called_once_with(
            release, sentinel.key
        )

    def test_throws_exception_when_os_does_not_exist(self):
        with pytest.raises(osystems.NoSuchOperatingSystem):
            osystems.validate_license_key(
                factory.make_name("no-such-os"),
                factory.make_name("bogus-release"),
                factory.make_name("key-to-not-much"),
            )
