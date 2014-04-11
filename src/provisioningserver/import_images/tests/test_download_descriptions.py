# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `download_descriptions` module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.matchers import MockAnyCall
from maastesting.testcase import MAASTestCase
from provisioningserver.import_images import download_descriptions
from provisioningserver.import_images.boot_image_mapping import (
    BootImageMapping,
    )
from provisioningserver.import_images.testing.factory import (
    make_image_spec,
    set_resource,
    )


class TestValuePassesFilterList(MAASTestCase):
    """Tests for `value_passes_filter_list`."""

    def test_nothing_passes_empty_list(self):
        self.assertFalse(
            download_descriptions.value_passes_filter_list(
                [], factory.make_name('value')))

    def test_unmatched_value_does_not_pass(self):
        self.assertFalse(
            download_descriptions.value_passes_filter_list(
                [factory.make_name('filter')], factory.make_name('value')))

    def test_matched_value_passes(self):
        value = factory.make_name('value')
        self.assertTrue(
            download_descriptions.value_passes_filter_list([value], value))

    def test_value_passes_if_matched_anywhere_in_filter(self):
        value = factory.make_name('value')
        self.assertTrue(
            download_descriptions.value_passes_filter_list(
                [
                    factory.make_name('filter'),
                    value,
                    factory.make_name('filter'),
                ],
                value))

    def test_any_value_passes_asterisk(self):
        self.assertTrue(
            download_descriptions.value_passes_filter_list(
                ['*'], factory.make_name('value')))


class TestValuePassesFilter(MAASTestCase):
    """Tests for `value_passes_filter`."""

    def test_unmatched_value_does_not_pass(self):
        self.assertFalse(
            download_descriptions.value_passes_filter(
                factory.make_name('filter'), factory.make_name('value')))

    def test_matching_value_passes(self):
        value = factory.make_name('value')
        self.assertTrue(
            download_descriptions.value_passes_filter(value, value))

    def test_any_value_matches_asterisk(self):
        self.assertTrue(
            download_descriptions.value_passes_filter(
                '*', factory.make_name('value')))


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
            download_descriptions.image_passes_filter(
                None, arch, subarch, release, label))

    def test_any_image_passes_empty_filter(self):
        arch, subarch, release, label = make_image_spec()
        self.assertTrue(
            download_descriptions.image_passes_filter(
                [], arch, subarch, release, label))

    def test_image_passes_matching_filter(self):
        image = make_image_spec()
        self.assertTrue(
            download_descriptions.image_passes_filter(
                [self.make_filter_from_image(image)],
                image.arch, image.subarch, image.release, image.label))

    def test_image_does_not_pass_nonmatching_filter(self):
        image = make_image_spec()
        self.assertFalse(
            download_descriptions.image_passes_filter(
                [self.make_filter_from_image()],
                image.arch, image.subarch, image.release, image.label))

    def test_image_passes_if_one_filter_matches(self):
        image = make_image_spec()
        self.assertTrue(
            download_descriptions.image_passes_filter(
                [
                    self.make_filter_from_image(),
                    self.make_filter_from_image(image),
                    self.make_filter_from_image(),
                ], image.arch, image.subarch, image.release, image.label))

    def test_filter_checks_release(self):
        image = make_image_spec()
        self.assertFalse(
            download_descriptions.image_passes_filter(
                [
                    self.make_filter_from_image(image._replace(
                        release=factory.make_name('other-release')))
                ], image.arch, image.subarch, image.release, image.label))

    def test_filter_checks_arches(self):
        image = make_image_spec()
        self.assertFalse(
            download_descriptions.image_passes_filter(
                [
                    self.make_filter_from_image(image._replace(
                        arch=factory.make_name('other-arch')))
                ], image.arch, image.subarch, image.release, image.label))

    def test_filter_checks_subarches(self):
        image = make_image_spec()
        self.assertFalse(
            download_descriptions.image_passes_filter(
                [
                    self.make_filter_from_image(image._replace(
                        subarch=factory.make_name('other-subarch')))
                ], image.arch, image.subarch, image.release, image.label))

    def test_filter_checks_labels(self):
        image = make_image_spec()
        self.assertFalse(
            download_descriptions.image_passes_filter(
                [
                    self.make_filter_from_image(image._replace(
                        label=factory.make_name('other-label')))
                ], image.arch, image.subarch, image.release, image.label))


class TestBootMerge(MAASTestCase):
    """Tests for `boot_merge`."""

    def test_integrates(self):
        # End-to-end scenario for boot_merge: start with an empty boot
        # resources dict, and receive one resource from Simplestreams.
        total_resources = BootImageMapping()
        resources_from_repo = set_resource()
        download_descriptions.boot_merge(total_resources, resources_from_repo)
        # Since we started with an empty dict, the result contains the same
        # item that we got from Simplestreams, and nothing else.
        self.assertEqual(resources_from_repo.mapping, total_resources.mapping)

    def test_obeys_filters(self):
        filters = [
            {
                'arches': [factory.make_name('other-arch')],
                'subarches': [factory.make_name('other-subarch')],
                'release': factory.make_name('other-release'),
                'label': [factory.make_name('other-label')],
            },
            ]
        total_resources = BootImageMapping()
        resources_from_repo = set_resource()
        download_descriptions.boot_merge(
            total_resources, resources_from_repo, filters=filters)
        self.assertEqual({}, total_resources.mapping)

    def test_does_not_overwrite_existing_entry(self):
        image = make_image_spec()
        total_resources = set_resource(
            resource="Original resource", image_spec=image)
        original_resources = total_resources.mapping.copy()
        resources_from_repo = set_resource(
            resource="New resource", image_spec=image)
        download_descriptions.boot_merge(total_resources, resources_from_repo)
        self.assertEqual(original_resources, total_resources.mapping)


class TestDownloadImageDescriptions(MAASTestCase):

    def test_warns_if_no_resources_found(self):
        self.patch(download_descriptions, 'logger')
        # Stop the RepoDumper from finding any boot resources at all.
        self.patch(download_descriptions, 'RepoDumper')
        path = factory.make_name('path')
        download_descriptions.download_image_descriptions(path)
        self.assertThat(
            download_descriptions.logger.warn,
            MockAnyCall(
                "No resources found in Simplestreams repository %r.  "
                "Is it correctly configured?",
                path))
