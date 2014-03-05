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

    def test_default_arch_image_returns_None_if_no_images_match(self):
        series = Config.objects.get_config('commissioning_distro_series')
        result = BootImage.objects.get_default_arch_image_in_nodegroup(
            factory.make_node_group(), series, factory.make_name('purpose'))
        self.assertIsNone(result)

    def test_default_arch_image_returns_only_matching_image(self):
        nodegroup = factory.make_node_group()
        series = factory.make_name('series')
        arch = factory.make_name('arch')
        purpose = factory.make_name("purpose")
        factory.make_boot_image(
            architecture=arch, release=series, nodegroup=nodegroup,
            purpose=purpose)
        result = BootImage.objects.get_default_arch_image_in_nodegroup(
            nodegroup, series, purpose=purpose)
        self.assertEqual(result.architecture, arch)

    def test_default_arch_image_prefers_i386(self):
        nodegroup = factory.make_node_group()
        series = factory.make_name('series')
        purpose = factory.make_name("purpose")
        for arch in ['amd64', 'axp', 'i386', 'm88k']:
            factory.make_boot_image(
                architecture=arch, release=series, nodegroup=nodegroup,
                purpose=purpose)
        result = BootImage.objects.get_default_arch_image_in_nodegroup(
            nodegroup, series, purpose=purpose)
        self.assertEqual(result.architecture, "i386")

    def test_default_arch_image_returns_arbitrary_pick_if_all_else_fails(self):
        nodegroup = factory.make_node_group()
        series = factory.make_name('series')
        purpose = factory.make_name("purpose")
        images = [
            factory.make_boot_image(
                architecture=factory.make_name('arch'), release=series,
                nodegroup=nodegroup, purpose=purpose)
            for _ in range(3)
            ]
        self.assertIn(
            BootImage.objects.get_default_arch_image_in_nodegroup(
                nodegroup, series, purpose=purpose),
            images)

    def test_default_arch_image_copes_with_subarches(self):
        nodegroup = factory.make_node_group()
        arch = 'i386'
        series = factory.make_name('series')
        purpose = factory.make_name("purpose")
        images = [
            factory.make_boot_image(
                architecture=arch, subarchitecture=factory.make_name('sub'),
                release=series, nodegroup=nodegroup, purpose=purpose)
            for _ in range(3)
            ]
        self.assertIn(
            BootImage.objects.get_default_arch_image_in_nodegroup(
                nodegroup, series, purpose=purpose),
            images)

    def test_get_usable_architectures_returns_supported_arches(self):
        nodegroup = factory.make_node_group()
        arches = [factory.make_name('arch'), factory.make_name('arch')]
        for arch in arches:
            factory.make_boot_image(
                architecture=arch, nodegroup=nodegroup, purpose='install')
            factory.make_boot_image(
                architecture=arch, nodegroup=nodegroup,
                purpose='commissioning')
        self.assertItemsEqual(
            arches,
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
