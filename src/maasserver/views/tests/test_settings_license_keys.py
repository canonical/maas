# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver license key settings views."""

__all__ = []

import http.client
import random

from django.conf import settings
from lxml.html import fromstring
from maasserver import forms
from maasserver.enum import BOOT_RESOURCE_TYPE
from maasserver.models import LicenseKey
from maasserver.testing import extract_redirect, get_content_links
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.django_urls import reverse
from maasserver.utils.orm import reload_object
from maasserver.views import settings as settings_view
from maasserver.views.settings_license_keys import LICENSE_KEY_ANCHOR
from provisioningserver.drivers.osystem import (
    OperatingSystemRegistry,
    WindowsOS,
)
from provisioningserver.drivers.osystem.windows import REQUIRE_LICENSE_KEY
from testtools.matchers import ContainsAll


def make_osystem_requiring_license_key(testcase, osystem=None, release=None):
    if osystem is None:
        osystem = factory.make_name("osystem")
    if release is None:
        release = random.choice(REQUIRE_LICENSE_KEY)
    distro_series = "%s/%s" % (osystem, release)
    drv = WindowsOS()
    drv.title = osystem
    OperatingSystemRegistry.register_item(osystem, drv)
    factory.make_BootResource(
        name=distro_series,
        rtype=BOOT_RESOURCE_TYPE.UPLOADED,
        extra={"title": drv.get_release_title(release)},
    )
    testcase.addCleanup(OperatingSystemRegistry.unregister_item, osystem)
    return {
        "name": osystem,
        "title": osystem,
        "default_release": release,
        "default_commissioning_release": None,
        "releases": [
            {
                "name": distro_series,
                "title": drv.get_release_title(release),
                "requires_license_key": True,
                "can_commission": False,
            }
        ],
    }


class LicenseKeyListingTest(MAASServerTestCase):
    def make_license_key_with_os(
        self, osystem=None, release=None, license_key=None
    ):
        if release is None:
            release = random.choice(REQUIRE_LICENSE_KEY)
        license_key = factory.make_LicenseKey(
            osystem=osystem, distro_series=release, license_key=license_key
        )
        osystem = make_osystem_requiring_license_key(
            self, license_key.osystem, license_key.distro_series
        )
        return license_key, osystem

    def make_license_keys(self, count):
        keys = []
        osystems = []
        for _ in range(count):
            key, osystem = self.make_license_key_with_os()
            keys.append(key)
            osystems.append(osystem)
        self.patch(
            settings_view, "gen_all_known_operating_systems"
        ).return_value = osystems
        return keys, osystems

    def test_settings_contains_osystem_and_distro_series(self):
        self.client.login(user=factory.make_admin())
        keys, _ = self.make_license_keys(3)
        response = self.client.get(reverse("settings_license_keys"))
        os_titles = [key.osystem for key in keys]
        series_titles = [key.distro_series for key in keys]
        self.assertThat(
            response.content.decode(settings.DEFAULT_CHARSET),
            ContainsAll([title for title in os_titles + series_titles]),
        )

    def test_settings_link_to_add_license_key(self):
        self.client.login(user=factory.make_admin())
        self.make_license_keys(3)
        links = get_content_links(
            self.client.get(reverse("settings_license_keys"))
        )
        script_add_link = reverse("license-key-add")
        self.assertIn(script_add_link, links)

    def test_settings_contains_links_to_delete(self):
        self.client.login(user=factory.make_admin())
        keys, _ = self.make_license_keys(3)
        links = get_content_links(
            self.client.get(reverse("settings_license_keys"))
        )
        license_key_delete_links = [
            reverse(
                "license-key-delete", args=[key.osystem, key.distro_series]
            )
            for key in keys
        ]
        self.assertThat(links, ContainsAll(license_key_delete_links))

    def test_settings_contains_links_to_edit(self):
        self.client.login(user=factory.make_admin())
        keys, _ = self.make_license_keys(3)
        links = get_content_links(
            self.client.get(reverse("settings_license_keys"))
        )
        license_key_delete_links = [
            reverse("license-key-edit", args=[key.osystem, key.distro_series])
            for key in keys
        ]
        self.assertThat(links, ContainsAll(license_key_delete_links))

    def test_settings_contains_commissioning_scripts_slot_anchor(self):
        self.client.login(user=factory.make_admin())
        self.make_license_keys(3)
        response = self.client.get(reverse("settings_license_keys"))
        document = fromstring(response.content)
        slots = document.xpath("//div[@id='%s']" % LICENSE_KEY_ANCHOR)
        self.assertEqual(
            1, len(slots), "Missing anchor '%s'" % LICENSE_KEY_ANCHOR
        )


class LicenseKeyAddTest(MAASServerTestCase):
    def test_can_create_license_key(self):
        self.client.login(user=factory.make_admin())
        osystem = make_osystem_requiring_license_key(self)
        self.patch(forms, "validate_license_key").return_value = True
        series = osystem["default_release"]
        key = factory.make_name("key")
        add_link = reverse("license-key-add")
        definition = {
            "osystem": osystem["name"],
            "distro_series": "%s/%s" % (osystem["name"], series),
            "license_key": key,
        }
        response = self.client.post(add_link, definition)
        self.assertEqual(
            (http.client.FOUND, reverse("settings_license_keys")),
            (response.status_code, extract_redirect(response)),
        )
        new_license_key = LicenseKey.objects.get(
            osystem=osystem["name"], distro_series=series
        )
        expected_result = {
            "osystem": osystem["name"],
            "distro_series": series,
            "license_key": key,
        }
        self.assertAttributes(new_license_key, expected_result)


class LicenseKeyEditTest(MAASServerTestCase):
    def test_can_update_license_key(self):
        self.client.login(user=factory.make_admin())
        key = factory.make_LicenseKey(
            distro_series=random.choice(REQUIRE_LICENSE_KEY)
        )
        make_osystem_requiring_license_key(
            self, key.osystem, key.distro_series
        )
        self.patch(forms, "validate_license_key").return_value = True
        new_key = factory.make_name("key")
        edit_link = reverse(
            "license-key-edit", args=[key.osystem, key.distro_series]
        )
        definition = {
            "osystem": key.osystem,
            "distro_series": "%s/%s" % (key.osystem, key.distro_series),
            "license_key": new_key,
        }
        response = self.client.post(edit_link, definition)
        self.assertEqual(
            (http.client.FOUND, reverse("settings_license_keys")),
            (response.status_code, extract_redirect(response)),
        )
        expected_result = {
            "osystem": key.osystem,
            "distro_series": key.distro_series,
            "license_key": new_key,
        }
        self.assertAttributes(reload_object(key), expected_result)


class LicenseKeyDeleteTest(MAASServerTestCase):
    def test_can_delete_license_key(self):
        self.client.login(user=factory.make_admin())
        key = factory.make_LicenseKey()
        delete_link = reverse(
            "license-key-delete", args=[key.osystem, key.distro_series]
        )
        response = self.client.post(delete_link, {"post": "yes"})
        self.assertEqual(
            (http.client.FOUND, reverse("settings_license_keys")),
            (response.status_code, extract_redirect(response)),
        )
        self.assertFalse(
            LicenseKey.objects.filter(
                osystem=key.osystem, distro_series=key.distro_series
            ).exists()
        )
