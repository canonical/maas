# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~provisioningserver.rpc.osystems`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import sentinel
from provisioningserver.drivers.osystem import OperatingSystemRegistry
from provisioningserver.rpc import (
    exceptions,
    osystems,
    )


class TestValidateLicenseKeyErrors(MAASTestCase):

    def test_throws_exception_when_os_does_not_exist(self):
        self.assertRaises(
            exceptions.NoSuchOperatingSystem,
            osystems.validate_license_key,
            factory.make_name("no-such-os"),
            factory.make_name("bogus-release"),
            factory.make_name("key-to-not-much"))


class TestValidateLicenseKey(MAASTestCase):

    # Check for every OS and release.
    scenarios = [
        ("%s/%s" % (osystem.name, release),
         {"osystem": osystem, "release": release})
        for _, osystem in OperatingSystemRegistry
        for release in osystem.get_supported_releases()
    ]

    def test_validates_key(self):
        os_specific_validate_license_key = self.patch(
            self.osystem, "validate_license_key")
        osystems.validate_license_key(
            self.osystem.name, self.release, sentinel.key)
        self.assertThat(
            os_specific_validate_license_key,
            MockCalledOnceWith(self.release, sentinel.key))
