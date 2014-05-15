# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :class:`BootImage`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.models import (
    BootImage,
    Config,
    )
from maasserver.testing import reload_object
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.testing.boot_images import make_boot_image_params


class TestBootImageManager(MAASServerTestCase):

    def test_have_image_returns_False_if_image_not_available(self):
        self.assertFalse(
            BootImage.objects.have_image(
                factory.make_node_group(), **make_boot_image_params()))

    def test_have_image_returns_True_if_image_available(self):
        nodegroup = factory.make_node_group()
        params = make_boot_image_params()
        factory.make_boot_image(nodegroup=nodegroup, **params)
        self.assertTrue(BootImage.objects.have_image(nodegroup, **params))

    def test_register_image_registers_new_image(self):
        nodegroup = factory.make_node_group()
        params = make_boot_image_params()
        BootImage.objects.register_image(nodegroup, **params)
        self.assertTrue(BootImage.objects.have_image(nodegroup, **params))

    def test_register_image_leaves_existing_image_intact(self):
        nodegroup = factory.make_node_group()
        params = make_boot_image_params()
        factory.make_boot_image(nodegroup=nodegroup, **params)
        BootImage.objects.register_image(nodegroup, **params)
        self.assertTrue(BootImage.objects.have_image(nodegroup, **params))

    def test_register_image_updates_subarches_for_existing_image(self):
        nodegroup = factory.make_node_group()
        params = make_boot_image_params()
        image = factory.make_boot_image(nodegroup=nodegroup, **params)
        params['supported_subarches'] = factory.make_name("subarch")
        BootImage.objects.register_image(nodegroup, **params)
        image = reload_object(image)
        self.assertEqual(
            params['supported_subarches'], image.supported_subarches)

    def test_default_arch_image_returns_None_if_no_images_match(self):
        osystem = Config.objects.get_config('commissioning_osystem')
        series = Config.objects.get_config('commissioning_distro_series')
        result = BootImage.objects.get_default_arch_image_in_nodegroup(
            factory.make_node_group(), osystem, series,
            factory.make_name('purpose'))
        self.assertIsNone(result)

    def test_default_arch_image_returns_only_matching_image(self):
        nodegroup = factory.make_node_group()
        osystem = factory.make_name('os')
        series = factory.make_name('series')
        label = factory.make_name('label')
        arch = factory.make_name('arch')
        purpose = factory.make_name("purpose")
        factory.make_boot_image(
            osystem=osystem, architecture=arch,
            release=series, label=label,
            nodegroup=nodegroup, purpose=purpose)
        result = BootImage.objects.get_default_arch_image_in_nodegroup(
            nodegroup, osystem, series, purpose=purpose)
        self.assertEqual(result.architecture, arch)

    def test_default_arch_image_prefers_i386(self):
        nodegroup = factory.make_node_group()
        osystem = factory.make_name('os')
        series = factory.make_name('series')
        label = factory.make_name('label')
        purpose = factory.make_name("purpose")
        for arch in ['amd64', 'axp', 'i386', 'm88k']:
            factory.make_boot_image(
                osystem=osystem, architecture=arch,
                release=series, nodegroup=nodegroup,
                purpose=purpose, label=label)
        result = BootImage.objects.get_default_arch_image_in_nodegroup(
            nodegroup, osystem, series, purpose=purpose)
        self.assertEqual(result.architecture, "i386")

    def test_default_arch_image_returns_arbitrary_pick_if_all_else_fails(self):
        nodegroup = factory.make_node_group()
        osystem = factory.make_name('os')
        series = factory.make_name('series')
        label = factory.make_name('label')
        purpose = factory.make_name("purpose")
        images = [
            factory.make_boot_image(
                osystem=osystem, architecture=factory.make_name('arch'),
                release=series, label=label, nodegroup=nodegroup,
                purpose=purpose)
            for _ in range(3)
            ]
        self.assertIn(
            BootImage.objects.get_default_arch_image_in_nodegroup(
                nodegroup, osystem, series, purpose=purpose),
            images)

    def test_default_arch_image_copes_with_subarches(self):
        nodegroup = factory.make_node_group()
        arch = 'i386'
        osystem = factory.make_name('os')
        series = factory.make_name('series')
        label = factory.make_name('label')
        purpose = factory.make_name("purpose")
        images = [
            factory.make_boot_image(
                osystem=osystem, architecture=arch,
                subarchitecture=factory.make_name('sub'),
                release=series, label=label, nodegroup=nodegroup,
                purpose=purpose)
            for _ in range(3)
            ]
        self.assertIn(
            BootImage.objects.get_default_arch_image_in_nodegroup(
                nodegroup, osystem, series, purpose=purpose),
            images)

    def test_get_usable_architectures_returns_supported_arches(self):
        nodegroup = factory.make_node_group()
        arches = [
            (factory.make_name('arch'), factory.make_name('subarch')),
            (factory.make_name('arch'), factory.make_name('subarch'))]
        for arch, subarch in arches:
            factory.make_boot_image(
                architecture=arch, subarchitecture=subarch,
                nodegroup=nodegroup, purpose='install')
            factory.make_boot_image(
                architecture=arch, subarchitecture=subarch,
                nodegroup=nodegroup, purpose='commissioning')
        expected = ["%s/%s" % (arch, subarch) for arch, subarch in arches]
        self.assertItemsEqual(
            expected,
            BootImage.objects.get_usable_architectures(nodegroup))

    def test_get_usable_architectures_uses_given_nodegroup(self):
        nodegroup = factory.make_node_group()
        arch = factory.make_name('arch')
        factory.make_boot_image(
            architecture=arch, nodegroup=nodegroup, purpose='install')
        factory.make_boot_image(
            architecture=arch, nodegroup=nodegroup,
            purpose='commissioning')
        self.assertItemsEqual(
            [],
            BootImage.objects.get_usable_architectures(
                factory.make_node_group()))

    def test_get_usable_architectures_requires_commissioning_image(self):
        arch = factory.make_name('arch')
        nodegroup = factory.make_node_group()
        factory.make_boot_image(
            architecture=arch, nodegroup=nodegroup, purpose='install')
        self.assertItemsEqual(
            [],
            BootImage.objects.get_usable_architectures(nodegroup))

    def test_get_usable_architectures_requires_install_image(self):
        arch = factory.make_name('arch')
        nodegroup = factory.make_node_group()
        factory.make_boot_image(
            architecture=arch, nodegroup=nodegroup, purpose='commissioning')
        self.assertItemsEqual(
            [],
            BootImage.objects.get_usable_architectures(nodegroup))

    def test_get_latest_image_returns_latest_image_for_criteria(self):
        osystem = factory.make_name('os')
        arch = factory.make_name('arch')
        subarch = factory.make_name('sub')
        release = factory.make_name('release')
        nodegroup = factory.make_node_group()
        purpose = factory.make_name("purpose")
        boot_image = factory.make_boot_image(
            nodegroup=nodegroup, osystem=osystem, architecture=arch,
            subarchitecture=subarch, release=release, purpose=purpose,
            label=factory.make_name('label'))
        self.assertEqual(
            boot_image,
            BootImage.objects.get_latest_image(
                nodegroup, osystem, arch, subarch, release, purpose))

    def test_get_latest_image_falls_back_to_supported_subarches(self):
        # If the required subarch is not the primary subarch,
        # get_latest_image should fall back to examining the list of
        # supported_subarches.
        osystem = factory.make_name('os')
        arch = factory.make_name('arch')
        primary_subarch = factory.make_name('primary_subarch')
        release = factory.make_name('release')
        nodegroup = factory.make_node_group()
        purpose = factory.make_name("purpose")
        supported_subarches = [
            factory.make_name("supported1"), factory.make_name("supported2")]

        boot_image = factory.make_boot_image(
            nodegroup=nodegroup, osystem=osystem, architecture=arch,
            subarchitecture=primary_subarch, release=release, purpose=purpose,
            label=factory.make_name('label'),
            supported_subarches=supported_subarches)

        # Now check that get_latest_image() finds an image with a
        # subarch that is only in supported_subarches.
        required_subarch = supported_subarches[0]
        self.assertEqual(
            boot_image,
            BootImage.objects.get_latest_image(
                nodegroup, osystem, arch, required_subarch, release, purpose))

    def test_get_latest_image_doesnt_return_images_for_other_purposes(self):
        osystem = factory.make_name('os')
        arch = factory.make_name('arch')
        subarch = factory.make_name('sub')
        release = factory.make_name('release')
        nodegroup = factory.make_node_group()
        purpose = factory.make_name("purpose")
        relevant_image = factory.make_boot_image(
            nodegroup=nodegroup, osystem=osystem, architecture=arch,
            subarchitecture=subarch, release=release, purpose=purpose,
            label=factory.make_name('label'))

        # Create a bunch of more recent but irrelevant BootImages..
        factory.make_boot_image(
            nodegroup=factory.make_node_group(), osystem=osystem,
            architecture=arch, subarchitecture=subarch, release=release,
            purpose=purpose, label=factory.make_name('label'))
        factory.make_boot_image(
            nodegroup=nodegroup, osystem=osystem,
            architecture=factory.make_name('arch'),
            subarchitecture=subarch, release=release, purpose=purpose,
            label=factory.make_name('label'))
        factory.make_boot_image(
            nodegroup=nodegroup, osystem=osystem, architecture=arch,
            subarchitecture=factory.make_name('subarch'),
            release=release, purpose=purpose,
            label=factory.make_name('label'))
        factory.make_boot_image(
            nodegroup=nodegroup, osystem=osystem,
            architecture=factory.make_name('arch'),
            subarchitecture=subarch,
            release=factory.make_name('release'), purpose=purpose,
            label=factory.make_name('label'))
        factory.make_boot_image(
            nodegroup=nodegroup, osystem=osystem,
            architecture=factory.make_name('arch'),
            subarchitecture=subarch, release=release,
            purpose=factory.make_name('purpose'),
            label=factory.make_name('label'))
        factory.make_boot_image(
            nodegroup=nodegroup, osystem=factory.make_name('os'),
            architecture=factory.make_name('arch'),
            subarchitecture=subarch, release=release,
            purpose=factory.make_name('purpose'),
            label=factory.make_name('label'))

        self.assertEqual(
            relevant_image,
            BootImage.objects.get_latest_image(
                nodegroup, osystem, arch, subarch, release, purpose))

    def test_get_usable_osystems_returns_supported_osystems(self):
        nodegroup = factory.make_node_group()
        osystems = [
            factory.make_name('os'),
            factory.make_name('os'),
            ]
        for osystem in osystems:
            factory.make_boot_image(
                osystem=osystem,
                nodegroup=nodegroup)
        self.assertItemsEqual(
            osystems,
            BootImage.objects.get_usable_osystems(nodegroup))

    def test_get_usable_osystems_uses_given_nodegroup(self):
        nodegroup = factory.make_node_group()
        osystem = factory.make_name('os')
        factory.make_boot_image(
            osystem=osystem, nodegroup=nodegroup)
        self.assertItemsEqual(
            [],
            BootImage.objects.get_usable_osystems(
                factory.make_node_group()))

    def test_get_usable_releases_returns_supported_releases(self):
        nodegroup = factory.make_node_group()
        osystem = factory.make_name('os')
        releases = [
            factory.make_name('release'),
            factory.make_name('release'),
            ]
        for release in releases:
            factory.make_boot_image(
                osystem=osystem,
                release=release,
                nodegroup=nodegroup)
        self.assertItemsEqual(
            releases,
            BootImage.objects.get_usable_releases(nodegroup, osystem))

    def test_get_usable_releases_uses_given_nodegroup(self):
        nodegroup = factory.make_node_group()
        osystem = factory.make_name('os')
        release = factory.make_name('release')
        factory.make_boot_image(
            osystem=osystem, release=release, nodegroup=nodegroup)
        self.assertItemsEqual(
            [],
            BootImage.objects.get_usable_releases(
                factory.make_node_group(), osystem))

    def test_get_usable_releases_uses_given_osystem(self):
        nodegroup = factory.make_node_group()
        osystem = factory.make_name('os')
        release = factory.make_name('release')
        factory.make_boot_image(
            osystem=osystem, release=release, nodegroup=nodegroup)
        self.assertItemsEqual(
            [],
            BootImage.objects.get_usable_releases(
                factory.make_node_group(), factory.make_name('os')))
