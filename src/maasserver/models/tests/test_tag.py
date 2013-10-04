# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
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
from maasserver.models.node import update_hardware_details
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.fields import Bin
from metadataserver.models.commissioningscript import LSHW_OUTPUT_NAME
from metadataserver.models.nodecommissionresult import NodeCommissionResult


def set_hardware_details(node, xmlbytes):
    # FIXME: Gavin Panella, bug=1235174, 2013-10-04
    #
    # This is a temporary shim to allow removal of
    # Node.set_hardware_details(), and thus the use of the
    # Node.hardware_details field.
    #
    # It is being replaced by storing the results only in
    # NodeCommissionResult, and reprocessing tags using all
    # relevant probed details.
    assert isinstance(xmlbytes, bytes)
    NodeCommissionResult.objects.store_data(
        node, LSHW_OUTPUT_NAME, script_result=0, data=Bin(xmlbytes))
    update_hardware_details(node, xmlbytes)


class TagTest(MAASServerTestCase):

    def test_factory_make_tag(self):
        """
        The generated system_id looks good.

        """
        tag = factory.make_tag('tag-name', '//node[@id=display]')
        self.assertEqual('tag-name', tag.name)
        self.assertEqual('//node[@id=display]', tag.definition)
        self.assertEqual('', tag.comment)
        self.assertIs(None, tag.kernel_opts)
        self.assertIsNot(None, tag.updated)
        self.assertIsNot(None, tag.created)

    def test_factory_make_tag_with_hardware_details(self):
        tag = factory.make_tag('a-tag', 'true', kernel_opts="console=ttyS0")
        self.assertEqual('a-tag', tag.name)
        self.assertEqual('true', tag.definition)
        self.assertEqual('', tag.comment)
        self.assertEqual('console=ttyS0', tag.kernel_opts)
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
        set_hardware_details(node1, b'<node><child /></node>')
        node2 = factory.make_node()
        set_hardware_details(node2, b'<node />')
        tag = factory.make_tag(definition='//node/child')
        self.assertItemsEqual([tag.name], node1.tag_names())
        self.assertItemsEqual([], node2.tag_names())

    def test_removes_old_values(self):
        node1 = factory.make_node()
        set_hardware_details(node1, b'<node><foo /></node>')
        node2 = factory.make_node()
        set_hardware_details(node2, b'<node><bar /></node>')
        tag = factory.make_tag(definition='//node/foo')
        self.assertItemsEqual([tag.name], node1.tag_names())
        self.assertItemsEqual([], node2.tag_names())
        tag.definition = '//node/bar'
        tag.save()
        self.assertItemsEqual([], node1.tag_names())
        self.assertItemsEqual([tag.name], node2.tag_names())
        # And we notice if we change it *again* and then save.
        tag.definition = '//node/foo'
        tag.save()
        self.assertItemsEqual([tag.name], node1.tag_names())
        self.assertItemsEqual([], node2.tag_names())

    def test_doesnt_touch_other_tags(self):
        node1 = factory.make_node()
        set_hardware_details(node1, b'<node><foo /></node>')
        node2 = factory.make_node()
        set_hardware_details(node2, b'<node><bar /></node>')
        tag1 = factory.make_tag(definition='//node/foo')
        self.assertItemsEqual([tag1.name], node1.tag_names())
        self.assertItemsEqual([], node2.tag_names())
        tag2 = factory.make_tag(definition='//node/bar')
        self.assertItemsEqual([tag1.name], node1.tag_names())
        self.assertItemsEqual([tag2.name], node2.tag_names())

    def test_rollsback_invalid_xpath(self):
        node = factory.make_node()
        set_hardware_details(node, b'<node><foo /></node>')
        tag = factory.make_tag(definition='//node/foo')
        self.assertItemsEqual([tag.name], node.tag_names())
        tag.definition = 'invalid::tag'
        self.assertRaises(ValidationError, tag.save)
        self.assertItemsEqual([tag.name], node.tag_names())
