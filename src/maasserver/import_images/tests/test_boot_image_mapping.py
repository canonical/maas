# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootImageMapping` and its module."""


from maasserver.import_images.boot_image_mapping import BootImageMapping
from maasserver.import_images.testing.factory import (
    make_image_spec,
    set_resource,
)
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase


class TestBootImageMapping(MAASTestCase):
    """Tests for `BootImageMapping`."""

    def test_initially_empty(self):
        self.assertCountEqual([], BootImageMapping().items())

    def test_items_returns_items(self):
        image = make_image_spec()
        resource = factory.make_name("resource")
        image_dict = set_resource(image_spec=image, resource=resource)
        self.assertCountEqual([(image, resource)], image_dict.items())

    def test_is_empty_returns_True_if_empty(self):
        self.assertTrue(BootImageMapping().is_empty())

    def test_is_empty_returns_False_if_not_empty(self):
        mapping = BootImageMapping()
        mapping.setdefault(make_image_spec(), factory.make_name("resource"))
        self.assertFalse(mapping.is_empty())

    def test_setdefault_sets_unset_item(self):
        image_dict = BootImageMapping()
        image = make_image_spec()
        resource = factory.make_name("resource")
        image_dict.setdefault(image, resource)
        self.assertCountEqual([(image, resource)], image_dict.items())

    def test_setdefault_leaves_set_item_unchanged(self):
        image = make_image_spec()
        old_resource = factory.make_name("resource")
        image_dict = set_resource(image_spec=image, resource=old_resource)
        image_dict.setdefault(image, factory.make_name("newresource"))
        self.assertCountEqual([(image, old_resource)], image_dict.items())

    def test_set_overwrites_item(self):
        image_dict = BootImageMapping()
        image = make_image_spec()
        resource = factory.make_name("resource")
        image_dict.setdefault(image, factory.make_name("resource"))
        image_dict.set(image, resource)
        self.assertCountEqual([(image, resource)], image_dict.items())

    def test_get_image_arches_gets_arches_from_imagespecs(self):
        expected_arches = set()
        mapping = None
        for _ in range(0, 3):
            image_spec = make_image_spec()
            resource = factory.make_name("resource")
            expected_arches.add(image_spec.arch)
            mapping = set_resource(mapping, image_spec, resource)

        self.assertEqual(expected_arches, mapping.get_image_arches())
