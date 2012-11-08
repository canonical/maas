# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver models."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.core.exceptions import ValidationError
from maasserver.models import Tag
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase


class TagTest(TestCase):

    def test_factory_make_tag(self):
        """
        The generated system_id looks good.

        """
        tag = factory.make_tag('tag-name', '//node[@id=display]')
        self.assertEqual('tag-name', tag.name)
        self.assertEqual('//node[@id=display]', tag.definition)
        self.assertEqual('', tag.comment)
        self.assertIsNot(None, tag.updated)
        self.assertIsNot(None, tag.created)

    def test_add_tag_to_node(self):
        node = factory.make_node()
        tag = factory.make_tag()
        tag.save()
        node.tags.add(tag)
        self.assertEqual([tag.id], [t.id for t in node.tags.all()])
        self.assertEqual([node.id], [n.id for n in tag.node_set.all()])

    def test_valid_tag_names(self):
        for valid in ['valid-dash', 'under_score', 'long' * 50]:
            tag = factory.make_tag(name=valid)
            self.assertEqual(valid, tag.name)

    def test_validate_traps_invalid_tag_name(self):
        for invalid in ['invalid:name', 'no spaces', 'no\ttabs',
                        'no&ampersand', 'no!shouting', '',
                        'too-long' * 33, '\xb5']:
            self.assertRaises(ValidationError, factory.make_tag, name=invalid)

    def test_applies_tags_to_nodes(self):
        node1 = factory.make_node()
        node1.set_hardware_details('<node><child /></node>')
        node2 = factory.make_node()
        node2.set_hardware_details('<node />')
        tag = factory.make_tag(definition='/node/child')
        self.assertItemsEqual([tag.name], node1.tag_names())
        self.assertItemsEqual([], node2.tag_names())

    def test_removes_old_values(self):
        node1 = factory.make_node()
        node1.set_hardware_details('<node><foo /></node>')
        node2 = factory.make_node()
        node2.set_hardware_details('<node><bar /></node>')
        tag = factory.make_tag(definition='/node/foo')
        self.assertItemsEqual([tag.name], node1.tag_names())
        self.assertItemsEqual([], node2.tag_names())
        tag.definition = '/node/bar'
        tag.save()
        self.assertItemsEqual([], node1.tag_names())
        self.assertItemsEqual([tag.name], node2.tag_names())
        # And we notice if we change it *again* and then save.
        tag.definition = '/node/foo'
        tag.save()
        self.assertItemsEqual([tag.name], node1.tag_names())
        self.assertItemsEqual([], node2.tag_names())

    def test_doesnt_touch_other_tags(self):
        node1 = factory.make_node()
        node1.set_hardware_details('<node><foo /></node>')
        node2 = factory.make_node()
        node2.set_hardware_details('<node><bar /></node>')
        tag1 = factory.make_tag(definition='/node/foo')
        self.assertItemsEqual([tag1.name], node1.tag_names())
        self.assertItemsEqual([], node2.tag_names())
        tag2 = factory.make_tag(definition='/node/bar')
        self.assertItemsEqual([tag1.name], node1.tag_names())
        self.assertItemsEqual([tag2.name], node2.tag_names())

    def test_get_nodes_returns_unowned_nodes(self):
        user1 = factory.make_user()
        node1 = factory.make_node()
        tag = factory.make_tag()
        node1.tags.add(tag)
        self.assertItemsEqual([node1], Tag.objects.get_nodes(tag.name, user1))

    def test_get_nodes_returns_self_owned_nodes(self):
        user1 = factory.make_user()
        node1 = factory.make_node(owner=user1)
        tag = factory.make_tag()
        node1.tags.add(tag)
        self.assertItemsEqual([node1], Tag.objects.get_nodes(tag.name, user1))

    def test_get_nodes_doesnt_return_other_owned_nodes(self):
        user1 = factory.make_user()
        user2 = factory.make_user()
        node1 = factory.make_node(owner=user1)
        tag = factory.make_tag()
        node1.tags.add(tag)
        self.assertItemsEqual([], Tag.objects.get_nodes(tag.name, user2))

    def test_get_nodes_returns_everything_for_superuser(self):
        user1 = factory.make_user()
        user2 = factory.make_user()
        user2.is_superuser = True
        node1 = factory.make_node(owner=user1)
        node2 = factory.make_node()
        tag = factory.make_tag()
        node1.tags.add(tag)
        node2.tags.add(tag)
        self.assertItemsEqual([node1, node2],
                              Tag.objects.get_nodes(tag.name, user2))

    def test_get_nodes_with_mac_does_one_query(self):
        user = factory.make_user()
        tag = factory.make_tag()
        nodes = [factory.make_node(mac=True) for counter in range(5)]
        for node in nodes:
            node.tags.add(tag)
        # 1 query to lookup the tag, 1 to find the associated nodes, and 1 to
        # grab the mac addresses.
        mac_count = 0
        with self.assertNumQueries(3):
            nodes = Tag.objects.get_nodes(tag.name, user, prefetch_mac=True)
            for node in nodes:
                for mac in node.macaddress_set.all():
                    mac_count += 1
        # Make sure that we didn't succeed by just returning 1 node
        self.assertEqual(5, mac_count)

    def test_rollsback_invalid_xpath(self):
        node = factory.make_node()
        node.set_hardware_details('<node><foo /></node>')
        tag = factory.make_tag(definition='/node/foo')
        self.assertItemsEqual([tag.name], node.tag_names())
        tag.definition = 'invalid::tag'
        self.assertRaises(ValidationError, tag.save)
        self.assertItemsEqual([tag.name], node.tag_names())
