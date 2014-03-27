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


class TestIterateBootResources(MAASTestCase):
    """Tests for `iterate_boot_resources`."""

    def make_image_spec(self):
        return boot_resources.ImageSpec(
            factory.make_name('arch'),
            factory.make_name('subarch'),
            factory.make_name('release'),
            factory.make_name('label'),
            )

    def test_empty_hierarchy_yields_nothing(self):
        self.assertItemsEqual(
            [],
            boot_resources.iterate_boot_resources(
                boot_resources.create_empty_hierarchy()))

    def test_finds_boot_resource(self):
        image_spec = self.make_image_spec()
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
