# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :class:`LicenseKey`."""

from django.db import IntegrityError

from maasserver.models import LicenseKey
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestLicenseKeyManager(MAASServerTestCase):
    def test_get_by_osystem_series(self):
        key = factory.make_LicenseKey()
        expected = LicenseKey.objects.get_by_osystem_series(
            key.osystem, key.distro_series
        )
        self.assertEqual(key, expected)

    def test_get_license_key(self):
        key = factory.make_LicenseKey()
        license_key = LicenseKey.objects.get_license_key(
            key.osystem, key.distro_series
        )
        self.assertEqual(key.license_key, license_key)

    def test_has_license_key_True(self):
        key = factory.make_LicenseKey()
        self.assertTrue(
            LicenseKey.objects.has_license_key(key.osystem, key.distro_series)
        )

    def test_has_license_key_False(self):
        factory.make_LicenseKey()
        osystem = factory.make_name("osystem")
        series = factory.make_name("distro_series")
        self.assertFalse(LicenseKey.objects.has_license_key(osystem, series))

    def test_errors_on_not_unique(self):
        key = factory.make_LicenseKey()
        new_key = factory.make_name("key")
        self.assertRaises(
            IntegrityError,
            LicenseKey.objects.create,
            osystem=key.osystem,
            distro_series=key.distro_series,
            license_key=new_key,
        )
