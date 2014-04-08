# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `ProductMapping` class."""

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
from provisioningserver.import_images.product_mapping import ProductMapping
from provisioningserver.import_images.testing.factory import (
    make_boot_resource,
    )


class TestProductMapping(MAASTestCase):
    """Tests for `ProductMapping`."""

    def test_initially_empty(self):
        self.assertEqual({}, ProductMapping().mapping)

    def test_make_key_extracts_identifying_items(self):
        resource = make_boot_resource()
        content_id = resource['content_id']
        product_name = resource['product_name']
        version_name = resource['version_name']
        self.assertEqual(
            (content_id, product_name, version_name),
            ProductMapping.make_key(resource))

    def test_make_key_ignores_other_items(self):
        resource = make_boot_resource()
        resource['other_item'] = factory.make_name('other')
        self.assertEqual(
            (
                resource['content_id'],
                resource['product_name'],
                resource['version_name'],
            ),
            ProductMapping.make_key(resource))

    def test_make_key_fails_if_key_missing(self):
        resource = make_boot_resource()
        del resource['version_name']
        self.assertRaises(
            KeyError,
            ProductMapping.make_key, resource)

    def test_add_creates_subarches_list_if_needed(self):
        product_dict = ProductMapping()
        resource = make_boot_resource()
        subarch = factory.make_name('subarch')
        product_dict.add(resource, subarch)
        self.assertEqual(
            {product_dict.make_key(resource): [subarch]},
            product_dict.mapping)

    def test_add_appends_to_existing_list(self):
        product_dict = ProductMapping()
        resource = make_boot_resource()
        subarches = [factory.make_name('subarch') for _ in range(2)]
        for subarch in subarches:
            product_dict.add(resource, subarch)
        self.assertEqual(
            {product_dict.make_key(resource): subarches},
            product_dict.mapping)

    def test_contains_returns_true_for_stored_item(self):
        product_dict = ProductMapping()
        resource = make_boot_resource()
        subarch = factory.make_name('subarch')
        product_dict.add(resource, subarch)
        self.assertTrue(product_dict.contains(resource))

    def test_contains_returns_false_for_unstored_item(self):
        self.assertFalse(
            ProductMapping().contains(make_boot_resource()))

    def test_contains_ignores_similar_items(self):
        product_dict = ProductMapping()
        resource = make_boot_resource()
        subarch = factory.make_name('subarch')
        product_dict.add(resource.copy(), subarch)
        resource['product_name'] = factory.make_name('other')
        self.assertFalse(product_dict.contains(resource))

    def test_contains_ignores_extraneous_keys(self):
        product_dict = ProductMapping()
        resource = make_boot_resource()
        subarch = factory.make_name('subarch')
        product_dict.add(resource.copy(), subarch)
        resource['other_item'] = factory.make_name('other')
        self.assertTrue(product_dict.contains(resource))

    def test_get_returns_stored_item(self):
        product_dict = ProductMapping()
        resource = make_boot_resource()
        subarch = factory.make_name('subarch')
        product_dict.add(resource, subarch)
        self.assertEqual([subarch], product_dict.get(resource))

    def test_get_fails_for_unstored_item(self):
        product_dict = ProductMapping()
        resource = make_boot_resource()
        subarch = factory.make_name('subarch')
        product_dict.add(resource.copy(), subarch)
        resource['content_id'] = factory.make_name('other')
        self.assertRaises(KeyError, product_dict.get, resource)

    def test_get_ignores_extraneous_keys(self):
        product_dict = ProductMapping()
        resource = make_boot_resource()
        subarch = factory.make_name('subarch')
        product_dict.add(resource, subarch)
        resource['other_item'] = factory.make_name('other')
        self.assertEqual([subarch], product_dict.get(resource))
