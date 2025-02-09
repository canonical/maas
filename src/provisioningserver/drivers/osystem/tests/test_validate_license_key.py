# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.osystem`."""

import random
from unittest.mock import sentinel

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
import provisioningserver.drivers.osystem as osystems
from provisioningserver.drivers.osystem import BOOT_IMAGE_PURPOSE
from provisioningserver.rpc import exceptions
from provisioningserver.testing.os import make_osystem


class TestValidateLicenseKey(MAASTestCase):
    def test_validates_key(self):
        os_name = factory.make_name("os")
        purposes = [BOOT_IMAGE_PURPOSE.XINSTALL]
        osystem = make_osystem(self, os_name, purposes)
        release = random.choice(osystem.get_supported_releases())
        os_specific_validate_license_key = self.patch(
            osystem, "validate_license_key"
        )
        osystems.validate_license_key(osystem.name, release, sentinel.key)
        os_specific_validate_license_key.assert_called_once_with(
            release, sentinel.key
        )

    def test_throws_exception_when_os_does_not_exist(self):
        self.assertRaises(
            exceptions.NoSuchOperatingSystem,
            osystems.validate_license_key,
            factory.make_name("no-such-os"),
            factory.make_name("bogus-release"),
            factory.make_name("key-to-not-much"),
        )
