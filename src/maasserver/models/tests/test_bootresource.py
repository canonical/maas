# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootResource`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django.core.exceptions import ValidationError
from maasserver.enum import (
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_TYPE,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestBootResource(MAASServerTestCase):
    """Tests for the `BootResource` model."""

    def make_complete_boot_resource_set(self, resource):
        resource_set = factory.make_boot_resource_set(resource)
        filename = factory.make_name('name')
        filetype = factory.pick_enum(BOOT_RESOURCE_FILE_TYPE)
        largefile = factory.make_large_file()
        factory.make_boot_resource_file(
            resource_set, largefile, filename=filename, filetype=filetype)
        return resource_set

    def test_validation_raises_error_on_missing_subarch(self):
        arch = factory.make_name('arch')
        self.assertRaises(
            ValidationError, factory.make_boot_resource, architecture=arch)

    def test_create_raises_error_on_not_unique(self):
        rtype = factory.pick_enum(BOOT_RESOURCE_TYPE)
        name = factory.make_name('name')
        arch = '%s/%s' % (
            factory.make_name('arch'), factory.make_name('subarch'))
        factory.make_boot_resource(rtype=rtype, name=name, architecture=arch)
        self.assertRaises(
            ValidationError,
            factory.make_boot_resource,
            rtype=rtype, name=name, architecture=arch)

    def test_split_arch(self):
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        architecture = '%s/%s' % (arch, subarch)
        resource = factory.make_boot_resource(architecture=architecture)
        self.assertEqual([arch, subarch], resource.split_arch())
