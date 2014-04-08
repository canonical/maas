# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootImageMapping` and its module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import json

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.import_images.boot_image_mapping import (
    BootImageMapping,
    )
from provisioningserver.import_images.testing.factory import (
    make_image_spec,
    set_resource,
    )


class TestBootImageMapping(MAASTestCase):
    """Tests for `BootImageMapping`."""

    def test_initially_empty(self):
        self.assertItemsEqual([], BootImageMapping().items())

    def test_items_returns_items(self):
        image = make_image_spec()
        resource = factory.make_name('resource')
        image_dict = set_resource(image_spec=image, resource=resource)
        self.assertItemsEqual([(image, resource)], image_dict.items())

    def test_setdefault_sets_unset_item(self):
        image_dict = BootImageMapping()
        image = make_image_spec()
        resource = factory.make_name('resource')
        image_dict.setdefault(image, resource)
        self.assertItemsEqual([(image, resource)], image_dict.items())

    def test_setdefault_leaves_set_item_unchanged(self):
        image = make_image_spec()
        old_resource = factory.make_name('resource')
        image_dict = set_resource(image_spec=image, resource=old_resource)
        image_dict.setdefault(image, factory.make_name('newresource'))
        self.assertItemsEqual([(image, old_resource)], image_dict.items())

    def test_dump_json_is_consistent(self):
        image = make_image_spec()
        resource = factory.make_name('resource')
        image_dict_1 = set_resource(image_spec=image, resource=resource)
        image_dict_2 = set_resource(image_spec=image, resource=resource)
        self.assertEqual(image_dict_1.dump_json(), image_dict_2.dump_json())

    def test_dump_json_represents_empty_dict_as_empty_object(self):
        self.assertEqual('{}', BootImageMapping().dump_json())

    def test_dump_json_represents_entry(self):
        image = make_image_spec()
        resource = factory.make_name('resource')
        image_dict = set_resource(image_spec=image, resource=resource)
        self.assertEqual(
            {
                image.arch: {
                    image.subarch: {
                        image.release: {image.label: resource},
                    },
                },
            },
            json.loads(image_dict.dump_json()))

    def test_dump_json_combines_similar_entries(self):
        image = make_image_spec()
        other_release = factory.make_name('other-release')
        resource1 = factory.make_name('resource')
        resource2 = factory.make_name('other-resource')
        image_dict = BootImageMapping()
        set_resource(image_dict, image, resource1)
        set_resource(
            image_dict, image._replace(release=other_release), resource2)
        self.assertEqual(
            {
                image.arch: {
                    image.subarch: {
                        image.release: {image.label: resource1},
                        other_release: {image.label: resource2},
                    },
                },
            },
            json.loads(image_dict.dump_json()))
