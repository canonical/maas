# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver models."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django.core.exceptions import ValidationError
from maasserver.models.tag import Tag
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.models.commissioningscript import inject_lshw_result


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
        inject_lshw_result(node1, b'<node><child /></node>')
        node2 = factory.make_node()
        inject_lshw_result(node2, b'<node />')
        tag = factory.make_tag(definition='//node/child')
        self.assertItemsEqual([tag.name], node1.tag_names())
        self.assertItemsEqual([], node2.tag_names())

    def test_removes_old_values(self):
        node1 = factory.make_node()
        inject_lshw_result(node1, b'<node><foo /></node>')
        node2 = factory.make_node()
        inject_lshw_result(node2, b'<node><bar /></node>')
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
        inject_lshw_result(node1, b'<node><foo /></node>')
        node2 = factory.make_node()
        inject_lshw_result(node2, b'<node><bar /></node>')
        tag1 = factory.make_tag(definition='//node/foo')
        self.assertItemsEqual([tag1.name], node1.tag_names())
        self.assertItemsEqual([], node2.tag_names())
        tag2 = factory.make_tag(definition='//node/bar')
        self.assertItemsEqual([tag1.name], node1.tag_names())
        self.assertItemsEqual([tag2.name], node2.tag_names())

    def test_rollsback_invalid_xpath(self):
        node = factory.make_node()
        inject_lshw_result(node, b'<node><foo /></node>')
        tag = factory.make_tag(definition='//node/foo')
        self.assertItemsEqual([tag.name], node.tag_names())
        tag.definition = 'invalid::tag'
        self.assertRaises(ValidationError, tag.save)
        self.assertItemsEqual([tag.name], node.tag_names())


class TestTagIsDefined(MAASServerTestCase):
    """Tests for the `Tag.is_defined` property."""

    scenarios = (
        ("null", dict(definition=None, expected=False)),
        ("empty", dict(definition="", expected=False)),
        ("whitespace", dict(definition="   \t\n ", expected=False)),
        ("defined", dict(definition="//node", expected=True)),
    )

    def test(self):
        tag = Tag(name="tag", definition=self.definition)
        self.assertIs(self.expected, tag.is_defined)
