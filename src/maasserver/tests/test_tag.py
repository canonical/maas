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
        tag = factory.make_tag('tag-name')
        tag.save()
        node.tags.add(tag)
        self.assertEqual([tag.id], [t.id for t in node.tags.all()])
        self.assertEqual([node.id], [n.id for n in tag.node_set.all()])
