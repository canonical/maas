# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
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
    NodeGroup,
    Config,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.testing.boot_images import make_boot_image_params


class TestBootImageManager(MAASServerTestCase):

    def setUp(self):
        super(TestBootImageManager, self).setUp()
        self.nodegroup = NodeGroup.objects.ensure_master()

    def test_have_image_returns_False_if_image_not_available(self):
        self.assertFalse(
            BootImage.objects.have_image(
                self.nodegroup, **make_boot_image_params()))

    def test_have_image_returns_True_if_image_available(self):
        params = make_boot_image_params()
        factory.make_boot_image(nodegroup=self.nodegroup, **params)
        self.assertTrue(
            BootImage.objects.have_image(self.nodegroup, **params))

    def test_register_image_registers_new_image(self):
        params = make_boot_image_params()
        BootImage.objects.register_image(self.nodegroup, **params)
        self.assertTrue(
            BootImage.objects.have_image(self.nodegroup, **params))

    def test_register_image_leaves_existing_image_intact(self):
        params = make_boot_image_params()
        factory.make_boot_image(nodegroup=self.nodegroup, **params)
        BootImage.objects.register_image(self.nodegroup, **params)
        self.assertTrue(
            BootImage.objects.have_image(self.nodegroup, **params))

    def test_default_arch_image_none(self):
        series = Config.objects.get_config('commissioning_distro_series')
        result = BootImage.objects.get_default_arch_image_in_nodegroup(
            self.nodegroup, series, None)
        self.assertIsNone(result)

    def test_default_arch_image_one(self):
        series = Config.objects.get_config('commissioning_distro_series')
        purpose = factory.make_name("purpose")
        factory.make_boot_image(
            architecture="amd64", release=series, nodegroup=self.nodegroup,
            purpose=purpose)
        result = BootImage.objects.get_default_arch_image_in_nodegroup(
            self.nodegroup, series, purpose=purpose)
        self.assertEqual(result.architecture, "amd64")

    def test_default_arch_image_many(self):
        series = Config.objects.get_config('commissioning_distro_series')
        purpose = factory.make_name("purpose")
        factory.make_boot_image(
            architecture="amd64", release=series, nodegroup=self.nodegroup,
            purpose=purpose)
        factory.make_boot_image(
            architecture="other", release=series, nodegroup=self.nodegroup,
            purpose=purpose)
        result = BootImage.objects.get_default_arch_image_in_nodegroup(
            self.nodegroup, series, purpose=purpose)
        self.assertEqual(result.architecture, "amd64")
