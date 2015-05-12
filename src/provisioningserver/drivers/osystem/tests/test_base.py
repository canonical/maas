# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.osystem`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from mock import sentinel
from provisioningserver.drivers import osystem as osystem_module
from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystemRegistry,
)
from provisioningserver.testing.os import make_osystem
from provisioningserver.utils.testing import RegistryFixture


class TestOperatingSystem(MAASTestCase):

    def make_usable_osystem(self):
        return make_osystem(self, factory.make_name('os'), [
            BOOT_IMAGE_PURPOSE.COMMISSIONING,
            BOOT_IMAGE_PURPOSE.INSTALL,
            BOOT_IMAGE_PURPOSE.XINSTALL,
            ])

    def make_boot_image_for(self, osystem, release):
        return dict(
            osystem=osystem,
            release=release,
            )

    def configure_list_boot_images_for(self, osystem):
        images = [
            self.make_boot_image_for(osystem.name, release)
            for release in osystem.get_supported_releases()
            ]
        self.patch_autospec(
            osystem_module, 'list_boot_images_for').return_value = images
        return images

    def test_format_release_choices(self):
        osystem = self.make_usable_osystem()
        releases = osystem.get_supported_releases()
        self.assertItemsEqual(
            [(release, release) for release in releases],
            osystem.format_release_choices(releases))

    def test_format_release_choices_sorts(self):
        osystem = self.make_usable_osystem()
        releases = osystem.get_supported_releases()
        self.assertEqual(
            [(release, release) for release in sorted(releases, reverse=True)],
            osystem.format_release_choices(releases))

    def test_gen_supported_releases(self):
        osystem = self.make_usable_osystem()
        images = self.configure_list_boot_images_for(osystem)
        releases = {image['release'] for image in images}
        self.assertItemsEqual(
            releases, osystem.gen_supported_releases())


class TestOperatingSystemRegistry(MAASTestCase):

    def setUp(self):
        super(TestOperatingSystemRegistry, self).setUp()
        # Ensure the global registry is empty for each test run.
        self.useFixture(RegistryFixture())

    def test_operating_system_registry(self):
        self.assertItemsEqual([], OperatingSystemRegistry)
        OperatingSystemRegistry.register_item("resource", sentinel.resource)
        self.assertIn(
            sentinel.resource,
            (item for name, item in OperatingSystemRegistry))
