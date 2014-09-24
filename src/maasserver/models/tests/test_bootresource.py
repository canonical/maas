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

from collections import Iterable
from datetime import datetime
import random

from django.core.exceptions import ValidationError
from maasserver.enum import (
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_TYPE,
    BOOT_RESOURCE_TYPE_CHOICES_DICT,
    COMPONENT,
    )
from maasserver.models import bootresource
from maasserver.models.bootresource import (
    BootResource,
    RTYPE_REQUIRING_OS_SERIES_NAME,
    )
from maasserver.models.component_error import ComponentError
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestBootResourceManager(MAASServerTestCase):
    """Tests for the `BootResource` model manager."""

    def make_boot_resource(self, rtype, name):
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        architecture = '%s/%s' % (arch, subarch)
        resource = factory.make_BootResource(
            rtype=rtype, name=name, architecture=architecture)
        return resource, (arch, subarch)

    def make_synced_boot_resource(self):
        os = factory.make_name('os')
        series = factory.make_name('series')
        name = '%s/%s' % (os, series)
        resource, (arch, subarch) = self.make_boot_resource(
            BOOT_RESOURCE_TYPE.SYNCED, name=name)
        return resource, (os, arch, subarch, series)

    def make_generated_boot_resource(self):
        os = factory.make_name('os')
        series = factory.make_name('series')
        name = '%s/%s' % (os, series)
        resource, (arch, subarch) = self.make_boot_resource(
            BOOT_RESOURCE_TYPE.GENERATED, name=name)
        return resource, (os, arch, subarch, series)

    def make_uploaded_boot_resource(self):
        name = factory.make_name('name')
        resource, (arch, subarch) = self.make_boot_resource(
            BOOT_RESOURCE_TYPE.UPLOADED, name=name)
        return resource, (name, arch, subarch)

    def test_has_synced_resource_returns_true_when_exists(self):
        _, args = self.make_synced_boot_resource()
        self.assertTrue(
            BootResource.objects.has_synced_resource(*args))

    def test_has_synced_resource_returns_false_when_doesnt_exists(self):
        os = factory.make_name('os')
        series = factory.make_name('series')
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        self.assertFalse(
            BootResource.objects.has_synced_resource(
                os, arch, subarch, series))

    def test_get_synced_resource_returns_resource_when_exists(self):
        resource, args = self.make_synced_boot_resource()
        self.assertEqual(
            resource, BootResource.objects.get_synced_resource(*args))

    def test_get_synced_resource_returns_None_when_doesnt_exists(self):
        os = factory.make_name('os')
        series = factory.make_name('series')
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        self.assertEqual(
            None,
            BootResource.objects.get_synced_resource(
                os, arch, subarch, series))

    def test_has_generated_resource_returns_true_when_exists(self):
        _, args = self.make_generated_boot_resource()
        self.assertTrue(
            BootResource.objects.has_generated_resource(*args))

    def test_has_generated_resource_returns_false_when_doesnt_exists(self):
        os = factory.make_name('os')
        series = factory.make_name('series')
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        self.assertFalse(
            BootResource.objects.has_generated_resource(
                os, arch, subarch, series))

    def test_get_generated_resource_returns_resource_when_exists(self):
        resource, args = self.make_generated_boot_resource()
        self.assertEqual(
            resource, BootResource.objects.get_generated_resource(*args))

    def test_get_generated_resource_returns_None_when_doesnt_exists(self):
        os = factory.make_name('os')
        series = factory.make_name('series')
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        self.assertEqual(
            None,
            BootResource.objects.get_generated_resource(
                os, arch, subarch, series))

    def test_has_uploaded_resource_returns_true_when_exists(self):
        _, args = self.make_uploaded_boot_resource()
        self.assertTrue(
            BootResource.objects.has_uploaded_resource(*args))

    def test_has_uploaded_resource_returns_false_when_doesnt_exists(self):
        name = factory.make_name('name')
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        self.assertFalse(
            BootResource.objects.has_uploaded_resource(
                name, arch, subarch))

    def test_get_uploaded_resource_returns_resource_when_exists(self):
        resource, args = self.make_uploaded_boot_resource()
        self.assertEqual(
            resource, BootResource.objects.get_uploaded_resource(*args))

    def test_get_uploaded_resource_returns_None_when_doesnt_exists(self):
        name = factory.make_name('name')
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        self.assertEqual(
            None,
            BootResource.objects.get_uploaded_resource(
                name, arch, subarch))

    def test_get_usable_architectures(self):
        arches = [
            '%s/%s' % (factory.make_name('arch'), factory.make_name('subarch'))
            for _ in range(3)
            ]
        for arch in arches:
            factory.make_usable_boot_resource(architecture=arch)
        usable_arches = BootResource.objects.get_usable_architectures()
        self.assertIsInstance(usable_arches, set)
        self.assertItemsEqual(
            arches, usable_arches)

    def test_get_usable_architectures_combines_subarches(self):
        arches = set()
        for _ in range(3):
            arch = factory.make_name('arch')
            subarches = [factory.make_name('subarch') for _ in range(3)]
            architecture = '%s/%s' % (arch, subarches.pop())
            arches.add(architecture)
            for subarch in subarches:
                arches.add('%s/%s' % (arch, subarch))
            factory.make_usable_boot_resource(
                architecture=architecture,
                extra={'subarches': ','.join(subarches)})
        usable_arches = BootResource.objects.get_usable_architectures()
        self.assertIsInstance(usable_arches, set)
        self.assertItemsEqual(
            arches, usable_arches)

    def test_get_commissionable_resource_returns_iterable(self):
        os = factory.make_name('os')
        series = factory.make_name('series')
        name = '%s/%s' % (os, series)
        factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name)
        commissionables = BootResource.objects.get_commissionable_resource(
            os, series)
        self.assertIsInstance(commissionables, Iterable)

    def test_get_commissionable_resource_returns_only_commissionable(self):
        os = factory.make_name('os')
        series = factory.make_name('series')
        name = '%s/%s' % (os, series)
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name)
        not_commissionable = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name)
        factory.make_BootResourceSet(not_commissionable)
        commissionables = BootResource.objects.get_commissionable_resource(
            os, series)
        self.assertItemsEqual([resource], commissionables)

    def test_get_commissionable_resource_returns_only_for_os_series(self):
        os = factory.make_name('os')
        series = factory.make_name('series')
        name = '%s/%s' % (os, series)
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name)
        factory.make_usable_boot_resource()
        commissionables = BootResource.objects.get_commissionable_resource(
            os, series)
        self.assertItemsEqual([resource], commissionables)

    def test_get_commissionable_resource_returns_sorted_by_architecture(self):
        os = factory.make_name('os')
        series = factory.make_name('series')
        name = '%s/%s' % (os, series)
        resource_b = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name, architecture='b/generic')
        resource_a = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name, architecture='a/generic')
        resource_c = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name, architecture='c/generic')
        commissionables = BootResource.objects.get_commissionable_resource(
            os, series)
        self.assertEquals(
            [resource_a, resource_b, resource_c], list(commissionables))

    def test_get_default_commissioning_resource_returns_i386_first(self):
        os = factory.make_name('os')
        series = factory.make_name('series')
        name = '%s/%s' % (os, series)
        arches = ['i386/generic', 'amd64/generic', 'arm64/generic']
        for arch in arches:
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name, architecture=arch)
        self.assertEqual(
            'i386/generic',
            BootResource.objects.get_default_commissioning_resource(
                os, series).architecture)

    def test_get_default_commissioning_resource_returns_amd64_second(self):
        os = factory.make_name('os')
        series = factory.make_name('series')
        name = '%s/%s' % (os, series)
        arches = ['amd64/generic', 'arm64/generic']
        for arch in arches:
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name, architecture=arch)
        self.assertEqual(
            'amd64/generic',
            BootResource.objects.get_default_commissioning_resource(
                os, series).architecture)

    def test_get_default_commissioning_resource_returns_first_arch(self):
        os = factory.make_name('os')
        series = factory.make_name('series')
        name = '%s/%s' % (os, series)
        arches = ['ppc64el/generic', 'arm64/generic']
        for arch in arches:
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name, architecture=arch)
        self.assertEqual(
            'arm64/generic',
            BootResource.objects.get_default_commissioning_resource(
                os, series).architecture)

    def test_get_resource_for_returns_matching_resource(self):
        resources = [
            factory.make_BootResource(
                rtype=random.choice(RTYPE_REQUIRING_OS_SERIES_NAME))
            for _ in range(3)
            ]
        resource = resources.pop()
        subarches = [factory.make_name('subarch') for _ in range(3)]
        subarch = random.choice(subarches)
        resource.extra['subarches'] = ','.join(subarches)
        resource.save()
        osystem, series = resource.name.split('/')
        arch, _ = resource.split_arch()
        self.assertEqual(
            resource,
            BootResource.objects.get_resource_for(
                osystem, arch, subarch, series))


class TestBootResource(MAASServerTestCase):
    """Tests for the `BootResource` model."""

    def make_complete_boot_resource_set(self, resource):
        resource_set = factory.make_BootResourceSet(resource)
        filename = factory.make_name('name')
        filetype = factory.pick_enum(BOOT_RESOURCE_FILE_TYPE)
        largefile = factory.make_LargeFile()
        factory.make_BootResourceFile(
            resource_set, largefile, filename=filename, filetype=filetype)
        return resource_set

    def test_validation_raises_error_on_missing_subarch(self):
        arch = factory.make_name('arch')
        self.assertRaises(
            ValidationError, factory.make_BootResource, architecture=arch)

    def test_validation_raises_error_on_invalid_name_for_synced(self):
        name = factory.make_name('name')
        arch = '%s/%s' % (
            factory.make_name('arch'), factory.make_name('subarch'))
        resource = BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name, architecture=arch)
        self.assertRaises(
            ValidationError, resource.save)

    def test_validation_raises_error_on_invalid_name_for_generated(self):
        name = factory.make_name('name')
        arch = '%s/%s' % (
            factory.make_name('arch'), factory.make_name('subarch'))
        resource = BootResource(
            rtype=BOOT_RESOURCE_TYPE.GENERATED, name=name, architecture=arch)
        self.assertRaises(
            ValidationError, resource.save)

    def test_validation_raises_error_on_invalid_name_for_uploaded(self):
        name = '%s/%s' % (
            factory.make_name('os'), factory.make_name('series'))
        arch = '%s/%s' % (
            factory.make_name('arch'), factory.make_name('subarch'))
        resource = BootResource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED, name=name, architecture=arch)
        self.assertRaises(
            ValidationError, resource.save)

    def test_create_raises_error_on_not_unique(self):
        name = '%s/%s' % (
            factory.make_name('os'), factory.make_name('series'))
        arch = '%s/%s' % (
            factory.make_name('arch'), factory.make_name('subarch'))
        factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name, architecture=arch)
        self.assertRaises(
            ValidationError,
            factory.make_BootResource,
            rtype=BOOT_RESOURCE_TYPE.GENERATED, name=name, architecture=arch)

    def test_display_rtype(self):
        for key, value in BOOT_RESOURCE_TYPE_CHOICES_DICT.items():
            resource = BootResource(rtype=key)
            self.assertEqual(value, resource.display_rtype)

    def test_split_arch(self):
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        architecture = '%s/%s' % (arch, subarch)
        resource = factory.make_BootResource(architecture=architecture)
        self.assertEqual([arch, subarch], resource.split_arch())

    def test_get_latest_set(self):
        resource = factory.make_BootResource()
        factory.make_BootResourceSet(resource)
        latest_two = factory.make_BootResourceSet(resource)
        self.assertEqual(latest_two, resource.get_latest_set())

    def test_get_latest_complete_set(self):
        resource = factory.make_BootResource()
        factory.make_BootResourceSet(resource)
        self.make_complete_boot_resource_set(resource)
        latest_complete = self.make_complete_boot_resource_set(resource)
        factory.make_BootResourceSet(resource)
        self.assertEqual(latest_complete, resource.get_latest_complete_set())

    def configure_now(self):
        now = datetime.now()
        self.patch(bootresource, 'now').return_value = now
        return now.strftime('%Y%m%d')

    def test_get_next_version_name_returns_current_date(self):
        expected_version = self.configure_now()
        resource = factory.make_BootResource()
        self.assertEqual(expected_version, resource.get_next_version_name())

    def test_get_next_version_name_returns_first_revision(self):
        expected_version = '%s.1' % self.configure_now()
        resource = factory.make_BootResource()
        factory.make_BootResourceSet(
            resource, version=resource.get_next_version_name())
        self.assertEqual(expected_version, resource.get_next_version_name())

    def test_get_next_version_name_returns_later_revision(self):
        expected_version = self.configure_now()
        set_count = random.randint(2, 4)
        resource = factory.make_BootResource()
        for _ in range(set_count):
            factory.make_BootResourceSet(
                resource, version=resource.get_next_version_name())
        self.assertEqual(
            '%s.%d' % (expected_version, set_count),
            resource.get_next_version_name())

    def test_supports_subarch_returns_True_if_subarch_in_name_matches(self):
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        architecture = '%s/%s' % (arch, subarch)
        resource = factory.make_BootResource(architecture=architecture)
        self.assertTrue(resource.supports_subarch(subarch))

    def test_supports_subarch_returns_False_if_subarches_is_missing(self):
        resource = factory.make_BootResource()
        self.assertFalse(
            resource.supports_subarch(factory.make_name('subarch')))

    def test_supports_subarch_returns_True_if_subarch_in_subarches(self):
        subarches = [factory.make_name('subarch') for _ in range(3)]
        subarch = random.choice(subarches)
        resource = factory.make_BootResource(
            extra={'subarches': ','.join(subarches)})
        self.assertTrue(resource.supports_subarch(subarch))

    def test_supports_subarch_returns_False_if_subarch_not_in_subarches(self):
        subarches = [factory.make_name('subarch') for _ in range(3)]
        resource = factory.make_BootResource(
            extra={'subarches': ','.join(subarches)})
        self.assertFalse(
            resource.supports_subarch(factory.make_name('subarch')))

    def test_shows_and_hides_missing_boot_image_error(self):
        resource = factory.make_BootResource()
        self.assertFalse(
            ComponentError.objects.filter(
                component=COMPONENT.IMPORT_PXE_FILES).exists())
        resource.delete()
        self.assertTrue(
            ComponentError.objects.filter(
                component=COMPONENT.IMPORT_PXE_FILES).exists())
