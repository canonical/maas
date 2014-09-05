# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `LicenseKeyForm`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.forms import LicenseKeyForm
from maasserver.models import LicenseKey
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.drivers.osystem import OperatingSystemRegistry


class TestLicenseKeyForm(MAASServerTestCase):
    """Tests for `LicenseKeyForm`."""

    def make_os_with_license_key(self, osystem=None, has_key=True,
                                 key_is_valid=True, patch_registry=True):
        """Makes a fake operating system that requires a license key, and
        validates to key_is_valid."""
        if osystem is None:
            osystem = make_usable_osystem(self)
        self.patch(osystem, 'requires_license_key').return_value = has_key
        self.patch(osystem, 'validate_license_key').return_value = key_is_valid
        if patch_registry:
            self.patch(
                OperatingSystemRegistry, 'get_item').return_value = osystem
        return osystem

    def make_all_osystems_require_key(self, key_is_valid=True):
        """Patches all operating systems in the registry, to require a key."""
        for _, osystem in OperatingSystemRegistry:
            self.patch(
                osystem, 'requires_license_key').return_value = True
            self.patch(
                osystem, 'validate_license_key').return_value = key_is_valid

    def make_only_one_osystem_require_key(self, key_is_valid=True):
        """Patches a random operating system from the registry, to require a
        key. Patches the remaining operating systems to not require a key."""
        osystem = factory.pick_OS()
        self.patch(
            osystem, 'requires_license_key').return_value = True
        self.patch(
            osystem, 'validate_license_key').return_value = key_is_valid
        for _, other_osystem in OperatingSystemRegistry:
            if osystem == other_osystem:
                continue
            self.patch(
                other_osystem, 'requires_license_key').return_value = False
        return osystem

    def test_creates_license_key(self):
        osystem = self.make_os_with_license_key()
        series = factory.pick_release(osystem)
        key = factory.make_name('key')
        definition = {
            'osystem': osystem.name,
            'distro_series': series,
            'license_key': key,
            }
        data = definition.copy()
        data['distro_series'] = '%s/%s' % (osystem.name, series)
        form = LicenseKeyForm(data=data)
        form.save()
        license_key_obj = LicenseKey.objects.get(
            osystem=osystem.name, distro_series=series)
        self.assertAttributes(license_key_obj, definition)

    def test_updates_license_key(self):
        osystem = self.make_os_with_license_key()
        series = factory.pick_release(osystem)
        license_key = factory.make_LicenseKey(
            osystem=osystem.name, distro_series=series,
            license_key=factory.make_name('key'))
        new_key = factory.make_name('key')
        form = LicenseKeyForm(
            data={'license_key': new_key}, instance=license_key)
        form.save()
        license_key = reload_object(license_key)
        self.assertEqual(new_key, license_key.license_key)

    def test_validates_license_key(self):
        osystem = self.make_os_with_license_key(key_is_valid=False)
        series = factory.pick_release(osystem)
        license_key = factory.make_LicenseKey(
            osystem=osystem.name, distro_series=series,
            license_key=factory.make_name('key'))
        new_key = factory.make_name('key')
        form = LicenseKeyForm(
            data={'license_key': new_key}, instance=license_key)
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {'__all__': ['Invalid license key.']},
            form.errors)

    def test_handles_missing_osystem_in_distro_series(self):
        osystem = self.make_os_with_license_key()
        series = factory.pick_release(osystem)
        key = factory.make_name('key')
        definition = {
            'osystem': osystem.name,
            'distro_series': series,
            'license_key': key,
            }
        form = LicenseKeyForm(data=definition.copy())
        form.save()
        license_key_obj = LicenseKey.objects.get(
            osystem=osystem.name, distro_series=series)
        self.assertAttributes(license_key_obj, definition)

    def test_requires_all_fields(self):
        form = LicenseKeyForm(data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(
            ['osystem', 'distro_series', 'license_key'],
            form.errors.keys())

    def test_errors_on_not_unique(self):
        osystem = self.make_os_with_license_key()
        series = factory.pick_release(osystem)
        key = factory.make_name('key')
        factory.make_LicenseKey(
            osystem=osystem.name, distro_series=series, license_key=key)
        definition = {
            'osystem': osystem.name,
            'distro_series': series,
            'license_key': key,
            }
        form = LicenseKeyForm(data=definition)
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({
            '__all__': ['%s %s' % (
                "License key with this operating system and distro series",
                "already exists.")]},
            form.errors)

    def test_doesnt_include_default_osystem(self):
        form = LicenseKeyForm()
        self.assertNotIn(('', 'Default OS'), form.fields['osystem'].choices)

    def test_includes_all_osystems(self):
        self.make_all_osystems_require_key()
        osystems = [osystem for _, osystem in OperatingSystemRegistry]
        expected = [
            (osystem.name, osystem.title)
            for osystem in osystems
            ]
        form = LicenseKeyForm()
        self.assertItemsEqual(expected, form.fields['osystem'].choices)

    def test_includes_all_osystems_sorted(self):
        self.make_all_osystems_require_key()
        osystems = [osystem for _, osystem in OperatingSystemRegistry]
        osystems = sorted(osystems, key=lambda osystem: osystem.title)
        expected = [
            (osystem.name, osystem.title)
            for osystem in osystems
            ]
        form = LicenseKeyForm()
        self.assertEqual(expected, form.fields['osystem'].choices)

    def test_includes_only_osystems_that_require_license_keys(self):
        osystem = self.make_only_one_osystem_require_key()
        expected = [(osystem.name, osystem.title)]
        form = LicenseKeyForm()
        self.assertEquals(expected, form.fields['osystem'].choices)

    def test_doesnt_include_default_distro_series(self):
        form = LicenseKeyForm()
        self.assertNotIn(
            ('', 'Default OS Release'), form.fields['distro_series'].choices)

    def test_includes_all_distro_series(self):
        self.make_all_osystems_require_key()
        osystems = [osystem for _, osystem in OperatingSystemRegistry]
        expected = []
        for osystem in osystems:
            releases = osystem.get_supported_releases()
            for name, title in osystem.format_release_choices(releases):
                expected.append((
                    '%s/%s' % (osystem.name, name),
                    title
                    ))
        form = LicenseKeyForm()
        self.assertItemsEqual(expected, form.fields['distro_series'].choices)

    def test_includes_only_distro_series_that_require_license_keys(self):
        osystem = self.make_only_one_osystem_require_key()
        releases = osystem.get_supported_releases()
        expected = [
            ('%s/%s' % (osystem.name, name), title)
            for name, title in osystem.format_release_choices(releases)
            ]
        form = LicenseKeyForm()
        self.assertEquals(expected, form.fields['distro_series'].choices)
