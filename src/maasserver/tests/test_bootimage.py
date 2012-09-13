# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :class:`BootImage`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver.models import BootImage
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase


class TestBootImageManager(TestCase):

    def make_image_params(self):
        return dict(
            architecture=factory.make_name('architecture'),
            subarchitecture=factory.make_name('subarchitecture'),
            release=factory.make_name('release'),
            purpose=factory.make_name('purpose'))

    def test_have_image_returns_False_if_image_not_available(self):
        self.assertFalse(
            BootImage.objects.have_image(**self.make_image_params()))

    def test_have_image_returns_True_if_image_available(self):
        params = self.make_image_params()
        factory.make_boot_image(**params)
        self.assertTrue(BootImage.objects.have_image(**params))

    def test_register_image_registers_new_image(self):
        params = self.make_image_params()
        BootImage.objects.register_image(**params)
        self.assertTrue(BootImage.objects.have_image(**params))

    def test_register_image_leaves_existing_image_intact(self):
        params = self.make_image_params()
        factory.make_boot_image(**params)
        BootImage.objects.register_image(**params)
        self.assertTrue(BootImage.objects.have_image(**params))
