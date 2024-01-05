# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `LicenseKeyForm`."""


from operator import itemgetter
import random

from maasserver import forms
from maasserver.enum import BOOT_RESOURCE_TYPE
from maasserver.forms import LicenseKeyForm
from maasserver.models import LicenseKey
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from provisioningserver.drivers.osystem import (
    OperatingSystemRegistry,
    WindowsOS,
)
from provisioningserver.drivers.osystem.windows import REQUIRE_LICENSE_KEY


class TestLicenseKeyForm(MAASServerTestCase):
    """Tests for `LicenseKeyForm`."""

    def make_os_with_license_key(
        self, osystem=None, osystem_title=None, release=None
    ):
        """Makes a fake operating system that has a release that requires a
        license key."""
        if osystem is None:
            osystem = factory.make_name("osystem")
        if osystem_title is None:
            osystem_title = osystem + "_title"
        if release is None:
            release = random.choice(REQUIRE_LICENSE_KEY)
        distro_series = f"{osystem}/{release}"
        drv = WindowsOS()
        drv.title = osystem_title
        if osystem not in OperatingSystemRegistry:
            OperatingSystemRegistry.register_item(osystem, drv)
        factory.make_BootResource(
            name=distro_series,
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            extra={"title": drv.get_release_title(release)},
        )
        self.addCleanup(OperatingSystemRegistry.unregister_item, osystem)
        return (
            {"name": osystem, "title": osystem_title},
            {"name": release, "title": drv.get_release_title(release)},
        )

    def test_creates_license_key(self):
        osystem, release = self.make_os_with_license_key()
        key = factory.make_name("key")
        self.patch_autospec(forms, "validate_license_key").return_value = True
        definition = {
            "osystem": osystem["name"],
            "distro_series": release["name"],
            "license_key": key,
        }
        data = definition.copy()
        data["distro_series"] = "{}/{}".format(
            osystem["name"], release["name"]
        )
        form = LicenseKeyForm(data=data)
        form.save()
        license_key_obj = LicenseKey.objects.get(
            osystem=osystem["name"], distro_series=release["name"]
        )
        self.assertEqual(license_key_obj.osystem, osystem["name"])
        self.assertEqual(license_key_obj.distro_series, release["name"])
        self.assertEqual(license_key_obj.license_key, key)

    def test_updates_license_key(self):
        osystem, release = self.make_os_with_license_key()
        self.patch_autospec(forms, "validate_license_key").return_value = True
        license_key = factory.make_LicenseKey(
            osystem=osystem["name"],
            distro_series=release["name"],
            license_key=factory.make_name("key"),
        )
        new_key = factory.make_name("key")
        form = LicenseKeyForm(
            data={"license_key": new_key}, instance=license_key
        )
        form.save()
        license_key = reload_object(license_key)
        self.assertEqual(new_key, license_key.license_key)

    def test_validates_license_key(self):
        osystem, release = self.make_os_with_license_key()
        self.patch_autospec(forms, "validate_license_key").return_value = False
        license_key = factory.make_LicenseKey(
            osystem=osystem["name"],
            distro_series=release["name"],
            license_key=factory.make_name("key"),
        )
        new_key = factory.make_name("key")
        form = LicenseKeyForm(
            data={"license_key": new_key}, instance=license_key
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({"__all__": ["Invalid license key."]}, form.errors)

    def test_requires_all_fields(self):
        form = LicenseKeyForm(data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {"osystem", "distro_series", "license_key"}, form.errors.keys()
        )

    def test_errors_on_not_unique(self):
        osystem, release = self.make_os_with_license_key()
        self.patch_autospec(forms, "validate_license_key").return_value = True
        key = factory.make_name("key")
        factory.make_LicenseKey(
            osystem=osystem["name"],
            distro_series=release["name"],
            license_key=key,
        )
        definition = {
            "osystem": osystem["name"],
            "distro_series": "{}/{}".format(osystem["name"], release["name"]),
            "license_key": key,
        }
        form = LicenseKeyForm(data=definition)
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {
                "__all__": [
                    "%s %s"
                    % (
                        "License key with this operating system and distro series",
                        "already exists.",
                    )
                ]
            },
            form.errors,
        )

    def test_doesnt_include_default_osystem(self):
        form = LicenseKeyForm()
        self.assertNotIn(("", "Default OS"), form.fields["osystem"].choices)

    def test_includes_all_osystems_sorted(self):
        osystems = [self.make_os_with_license_key()[0] for _ in range(3)]
        choices = [
            (osystem["name"], osystem["title"])
            for osystem in sorted(osystems, key=itemgetter("title"))
        ]
        form = LicenseKeyForm()
        self.assertEqual(choices, form.fields["osystem"].choices)

    def test_includes_only_osystems_that_require_license_keys(self):
        osystems = [self.make_os_with_license_key()[0] for _ in range(2)]
        factory.make_BootResource()
        choices = [
            (osystem["name"], osystem["title"])
            for osystem in sorted(osystems, key=itemgetter("title"))
        ]
        form = LicenseKeyForm()
        self.assertEqual(choices, form.fields["osystem"].choices)

    def test_doesnt_include_default_distro_series(self):
        form = LicenseKeyForm()
        self.assertNotIn(
            ("", "Default OS Release"), form.fields["distro_series"].choices
        )

    def test_includes_only_distro_series_that_require_license_keys(self):
        osystem = factory.make_name("osystem")
        osystem_title = factory.make_name("osystem_title")
        releases = [
            self.make_os_with_license_key(osystem, osystem_title, release)[1]
            for release in REQUIRE_LICENSE_KEY
        ]
        factory.make_BootResource()
        choices = [
            ("{}/{}".format(osystem, release["name"]), release["title"])
            for release in releases
        ]
        form = LicenseKeyForm()
        self.assertCountEqual(choices, form.fields["distro_series"].choices)
