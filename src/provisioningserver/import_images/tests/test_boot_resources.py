# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the boot_resources module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import errno
import os
from random import randint

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from mock import MagicMock
from provisioningserver.config import BootConfig
from provisioningserver.import_images import boot_resources


def make_image_spec():
    """Return an `ImageSpec` with random values."""
    return boot_resources.ImageSpec(
        factory.make_name('arch'),
        factory.make_name('subarch'),
        factory.make_name('release'),
        factory.make_name('label'),
        )


class TestIterateBootResources(MAASTestCase):
    """Tests for `iterate_boot_resources`."""

    def test_empty_hierarchy_yields_nothing(self):
        self.assertItemsEqual(
            [],
            boot_resources.iterate_boot_resources(
                boot_resources.create_empty_hierarchy()))

    def test_finds_boot_resource(self):
        image_spec = make_image_spec()
        arch, subarch, release, label = image_spec
        self.assertItemsEqual(
            [image_spec],
            boot_resources.iterate_boot_resources(
                {arch: {subarch: {release: {label: factory.make_name()}}}}))


class TestValuePassesFilterList(MAASTestCase):
    """Tests for `value_passes_filter_list`."""

    def test_nothing_passes_empty_list(self):
        self.assertFalse(
            boot_resources.value_passes_filter_list(
                [], factory.make_name('value')))

    def test_unmatched_value_does_not_pass(self):
        self.assertFalse(
            boot_resources.value_passes_filter_list(
                [factory.make_name('filter')], factory.make_name('value')))

    def test_matched_value_passes(self):
        value = factory.make_name('value')
        self.assertTrue(
            boot_resources.value_passes_filter_list([value], value))

    def test_value_passes_if_matched_anywhere_in_filter(self):
        value = factory.make_name('value')
        self.assertTrue(
            boot_resources.value_passes_filter_list(
                [
                    factory.make_name('filter'),
                    value,
                    factory.make_name('filter'),
                ],
                value))

    def test_any_value_passes_asterisk(self):
        self.assertTrue(
            boot_resources.value_passes_filter_list(
                ['*'], factory.make_name('value')))


class TestValuePassesFilter(MAASTestCase):
    """Tests for `value_passes_filter`."""

    def test_unmatched_value_does_not_pass(self):
        self.assertFalse(
            boot_resources.value_passes_filter(
                factory.make_name('filter'), factory.make_name('value')))

    def test_matching_value_passes(self):
        value = factory.make_name('value')
        self.assertTrue(boot_resources.value_passes_filter(value, value))

    def test_any_value_matches_asterisk(self):
        self.assertTrue(
            boot_resources.value_passes_filter(
                '*', factory.make_name('value')))


class TestBootReverse(MAASTestCase):
    """Tests for `boot_reverse`."""

    def make_boot_resource(self):
        return {
            'content_id': factory.make_name('content_id'),
            'product_name': factory.make_name('product_name'),
            'version_name': factory.make_name('version_name'),
            }

    def test_maps_empty_dict_to_empty_dict(self):
        self.assertEqual(
            {},
            boot_resources.boot_reverse(
                boot_resources.create_empty_hierarchy()))

    def test_maps_boot_resource_by_content_id_product_name_and_version(self):
        image = make_image_spec()
        resource = self.make_boot_resource()
        boot_dict = set_resource(resource=resource.copy(), image_spec=image)
        self.assertEqual(
            {
                resource['content_id']: {
                    resource['product_name']: {
                        resource['version_name']: [image.subarch],
                    },
                },
            },
            boot_resources.boot_reverse(boot_dict))

    def test_concatenates_similar_resources(self):
        image1 = make_image_spec()
        image2 = make_image_spec()
        resource = self.make_boot_resource()
        boot_dict = {}
        # Create two images in boot_dict, both containing the same resource.
        for image in [image1, image2]:
            set_resource(
                boot_dict=boot_dict, resource=resource.copy(),
                image_spec=image)

        reverse_dict = boot_resources.boot_reverse(boot_dict)
        content_id = resource['content_id']
        product_name = resource['product_name']
        version_name = resource['version_name']
        self.assertItemsEqual([content_id], reverse_dict.keys())
        self.assertItemsEqual([product_name], reverse_dict[content_id].keys())
        self.assertItemsEqual(
            [version_name],
            reverse_dict[content_id][product_name].keys())
        subarches = reverse_dict[content_id][product_name][version_name]
        self.assertItemsEqual([image1.subarch, image2.subarch], subarches)


class TestImagePassesFilter(MAASTestCase):
    """Tests for `image_passes_filter`."""

    def make_filter_from_image(self, image_spec=None):
        """Create a filter dict that matches the given `ImageSpec`.

        If `image_spec` is not given, creates a random value.
        """
        if image_spec is None:
            image_spec = make_image_spec()
        return {
            'arches': [image_spec.arch],
            'subarches': [image_spec.subarch],
            'release': image_spec.release,
            'labels': [image_spec.label],
            }

    def test_any_image_passes_none_filter(self):
        arch, subarch, release, label = make_image_spec()
        self.assertTrue(
            boot_resources.image_passes_filter(
                None, arch, subarch, release, label))

    def test_any_image_passes_empty_filter(self):
        arch, subarch, release, label = make_image_spec()
        self.assertTrue(
            boot_resources.image_passes_filter(
                [], arch, subarch, release, label))

    def test_image_passes_matching_filter(self):
        image = make_image_spec()
        self.assertTrue(
            boot_resources.image_passes_filter(
                [self.make_filter_from_image(image)],
                image.arch, image.subarch, image.release, image.label))

    def test_image_does_not_pass_nonmatching_filter(self):
        image = make_image_spec()
        self.assertFalse(
            boot_resources.image_passes_filter(
                [self.make_filter_from_image()],
                image.arch, image.subarch, image.release, image.label))

    def test_image_passes_if_one_filter_matches(self):
        image = make_image_spec()
        self.assertTrue(
            boot_resources.image_passes_filter(
                [
                    self.make_filter_from_image(),
                    self.make_filter_from_image(image),
                    self.make_filter_from_image(),
                ], image.arch, image.subarch, image.release, image.label))

    def test_filter_checks_release(self):
        image = make_image_spec()
        self.assertFalse(
            boot_resources.image_passes_filter(
                [
                    self.make_filter_from_image(image._replace(
                        release=factory.make_name('other-release')))
                ], image.arch, image.subarch, image.release, image.label))

    def test_filter_checks_arches(self):
        image = make_image_spec()
        self.assertFalse(
            boot_resources.image_passes_filter(
                [
                    self.make_filter_from_image(image._replace(
                        arch=factory.make_name('other-arch')))
                ], image.arch, image.subarch, image.release, image.label))

    def test_filter_checks_subarches(self):
        image = make_image_spec()
        self.assertFalse(
            boot_resources.image_passes_filter(
                [
                    self.make_filter_from_image(image._replace(
                        subarch=factory.make_name('other-subarch')))
                ], image.arch, image.subarch, image.release, image.label))

    def test_filter_checks_labels(self):
        image = make_image_spec()
        self.assertFalse(
            boot_resources.image_passes_filter(
                [
                    self.make_filter_from_image(image._replace(
                        label=factory.make_name('other-label')))
                ], image.arch, image.subarch, image.release, image.label))


def set_resource(boot_dict=None, image_spec=None, resource=None):
    """Add a boot resource to `boot_dict`, creating it if necessary."""
    if boot_dict is None:
        boot_dict = {}
    if image_spec is None:
        image_spec = make_image_spec()
    if resource is None:
        resource = factory.make_name('boot-resource')
    arch, subarch, release, label = image_spec
    # Drill down into the dict; along the way, create any missing levels of
    # nested dicts.
    nested_dict = boot_dict
    for level in (arch, subarch, release):
        nested_dict.setdefault(level, {})
        nested_dict = nested_dict[level]
    # At the bottom level, indexed by "label," insert "resource" as the
    # value.
    nested_dict[label] = resource
    return boot_dict


class TestBootMerge(MAASTestCase):
    """Tests for `boot_merge`."""

    def test_integrates(self):
        # End-to-end scenario for boot_merge: start with an empty boot
        # resources dict, and receive one resource from Simplestreams.
        total_resources = boot_resources.create_empty_hierarchy()
        resources_from_repo = set_resource()
        boot_resources.boot_merge(total_resources, resources_from_repo.copy())
        # Since we started with an empty dict, the result contains the same
        # item that we got from Simplestreams, and nothing else.
        self.assertEqual(resources_from_repo, total_resources)

    def test_obeys_filters(self):
        filters = [
            {
                'arches': [factory.make_name('other-arch')],
                'subarches': [factory.make_name('other-subarch')],
                'release': factory.make_name('other-release'),
                'label': [factory.make_name('other-label')],
            },
            ]
        total_resources = boot_resources.create_empty_hierarchy()
        resources_from_repo = set_resource()
        boot_resources.boot_merge(
            total_resources, resources_from_repo, filters=filters)
        self.assertEqual({}, total_resources)

    def test_does_not_overwrite_existing_entry(self):
        image = make_image_spec()
        original_resources = set_resource(
            resource="Original resource", image_spec=image)
        total_resources = original_resources.copy()
        resources_from_repo = set_resource(
            resource="New resource", image_spec=image)
        boot_resources.boot_merge(total_resources, resources_from_repo.copy())
        self.assertEqual(original_resources, total_resources)


class TestMain(MAASTestCase):

    def test_raises_ioerror_when_no_config_file_found(self):
        # Suppress log output.
        self.logger = self.patch(boot_resources, 'logger')
        filename = "/tmp/%s" % factory.make_name("config")
        self.assertFalse(os.path.exists(filename))
        args = MagicMock()
        args.config_file = filename
        self.assertRaises(
            boot_resources.NoConfigFile,
            boot_resources.main, args)

    def test_raises_non_ENOENT_IOErrors(self):
        # main() will raise a NoConfigFile error when it encounters an
        # ENOENT IOError, but will otherwise just re-raise the original
        # IOError.
        args = MagicMock()
        mock_load_from_cache = self.patch(BootConfig, 'load_from_cache')
        other_error = IOError(randint(errno.ENOENT + 1, 1000))
        mock_load_from_cache.side_effect = other_error
        # Suppress log output.
        self.logger = self.patch(boot_resources, 'logger')
        raised_error = self.assertRaises(IOError, boot_resources.main, args)
        self.assertEqual(other_error, raised_error)
