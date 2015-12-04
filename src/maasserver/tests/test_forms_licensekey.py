# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `LicenseKeyForm`."""

__all__ = []

from operator import itemgetter

from maasserver import forms
from maasserver.clusterrpc.testing.osystems import (
    make_rpc_osystem,
    make_rpc_release,
)
from maasserver.forms import LicenseKeyForm
from maasserver.models import LicenseKey
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.osystems import patch_usable_osystems
from maasserver.testing.testcase import MAASServerTestCase


class TestLicenseKeyForm(MAASServerTestCase):
    """Tests for `LicenseKeyForm`."""

    def make_os_with_license_key(self):
        """Makes a fake operating system that has a release that requires a
        license key."""
        release = make_rpc_release(requires_license_key=True)
        osystem = make_rpc_osystem(releases=[release])
        patch_usable_osystems(self, osystems=[osystem])
        return osystem, release

    def test_creates_license_key(self):
        osystem, release = self.make_os_with_license_key()
        key = factory.make_name('key')
        self.patch_autospec(forms, 'validate_license_key').return_value = True
        definition = {
            'osystem': osystem['name'],
            'distro_series': release['name'],
            'license_key': key,
            }
        data = definition.copy()
        data['distro_series'] = '%s/%s' % (osystem['name'], release['name'])
        form = LicenseKeyForm(data=data)
        form.save()
        license_key_obj = LicenseKey.objects.get(
            osystem=osystem['name'], distro_series=release['name'])
        self.assertAttributes(license_key_obj, definition)

    def test_updates_license_key(self):
        osystem, release = self.make_os_with_license_key()
        self.patch_autospec(forms, 'validate_license_key').return_value = True
        license_key = factory.make_LicenseKey(
            osystem=osystem['name'], distro_series=release['name'],
            license_key=factory.make_name('key'))
        new_key = factory.make_name('key')
        form = LicenseKeyForm(
            data={'license_key': new_key}, instance=license_key)
        form.save()
        license_key = reload_object(license_key)
        self.assertEqual(new_key, license_key.license_key)

    def test_validates_license_key(self):
        osystem, release = self.make_os_with_license_key()
        self.patch_autospec(forms, 'validate_license_key').return_value = False
        license_key = factory.make_LicenseKey(
            osystem=osystem['name'], distro_series=release['name'],
            license_key=factory.make_name('key'))
        new_key = factory.make_name('key')
        form = LicenseKeyForm(
            data={'license_key': new_key}, instance=license_key)
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {'__all__': ['Invalid license key.']},
            form.errors)

    def test_handles_missing_osystem_in_distro_series(self):
        osystem, release = self.make_os_with_license_key()
        self.patch_autospec(forms, 'validate_license_key').return_value = True
        key = factory.make_name('key')
        definition = {
            'osystem': osystem['name'],
            'distro_series': release['name'],
            'license_key': key,
            }
        form = LicenseKeyForm(data=definition.copy())
        form.save()
        license_key_obj = LicenseKey.objects.get(
            osystem=osystem['name'], distro_series=release['name'])
        self.assertAttributes(license_key_obj, definition)

    def test_requires_all_fields(self):
        form = LicenseKeyForm(data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(
            ['osystem', 'distro_series', 'license_key'],
            form.errors.keys())

    def test_errors_on_not_unique(self):
        osystem, release = self.make_os_with_license_key()
        self.patch_autospec(forms, 'validate_license_key').return_value = True
        key = factory.make_name('key')
        factory.make_LicenseKey(
            osystem=osystem['name'], distro_series=release['name'],
            license_key=key)
        definition = {
            'osystem': osystem['name'],
            'distro_series': release['name'],
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

    def test_includes_osystem_in_choices(self):
        osystems = []
        for _ in range(3):
            release = make_rpc_release(requires_license_key=True)
            osystems.append(make_rpc_osystem(releases=[release]))
        patch_usable_osystems(self, osystems=osystems)
        choices = [
            (osystem['name'], osystem['title'])
            for osystem in osystems
            ]
        form = LicenseKeyForm()
        self.assertItemsEqual(choices, form.fields['osystem'].choices)

    def test_includes_all_osystems_sorted(self):
        osystems = []
        for _ in range(3):
            release = make_rpc_release(requires_license_key=True)
            osystems.append(make_rpc_osystem(releases=[release]))
        patch_usable_osystems(self, osystems=osystems)
        choices = [
            (osystem['name'], osystem['title'])
            for osystem in sorted(osystems, key=itemgetter('title'))
            ]
        form = LicenseKeyForm()
        self.assertEqual(choices, form.fields['osystem'].choices)

    def test_includes_only_osystems_that_require_license_keys(self):
        osystems = []
        for _ in range(2):
            release = make_rpc_release(requires_license_key=True)
            osystems.append(make_rpc_osystem(releases=[release]))
        patch_usable_osystems(self, osystems=osystems + [make_rpc_osystem()])
        choices = [
            (osystem['name'], osystem['title'])
            for osystem in sorted(osystems, key=itemgetter('title'))
            ]
        form = LicenseKeyForm()
        self.assertEqual(choices, form.fields['osystem'].choices)

    def test_doesnt_include_default_distro_series(self):
        form = LicenseKeyForm()
        self.assertNotIn(
            ('', 'Default OS Release'), form.fields['distro_series'].choices)

    def test_includes_all_distro_series(self):
        releases = [
            make_rpc_release(requires_license_key=True) for _ in range(3)]
        osystem = make_rpc_osystem(releases=releases)
        patch_usable_osystems(self, osystems=[osystem])
        choices = [
            ('%s/%s' % (osystem['name'], release['name']), release['title'])
            for release in releases
            ]
        form = LicenseKeyForm()
        self.assertItemsEqual(choices, form.fields['distro_series'].choices)

    def test_includes_only_distro_series_that_require_license_keys(self):
        releases = [
            make_rpc_release(requires_license_key=True) for _ in range(3)]
        no_key_release = make_rpc_release()
        osystem = make_rpc_osystem(releases=releases + [no_key_release])
        patch_usable_osystems(self, osystems=[osystem])
        choices = [
            ('%s/%s' % (osystem['name'], release['name']), release['title'])
            for release in releases
            ]
        form = LicenseKeyForm()
        self.assertItemsEqual(choices, form.fields['distro_series'].choices)
