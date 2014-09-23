# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.populate_tags`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.models import Tag
from maasserver.populate_tags import populate_tags_for_single_node
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.models import commissioningscript


class TestPopulateTagsForSingleNode(MAASServerTestCase):

    def test_updates_node_with_all_applicable_tags(self):
        node = factory.make_Node()
        factory.make_NodeResult_for_commissioning(
            node, commissioningscript.LSHW_OUTPUT_NAME, 0, b"<foo/>")
        factory.make_NodeResult_for_commissioning(
            node, commissioningscript.LLDP_OUTPUT_NAME, 0, b"<bar/>")
        tags = [
            factory.make_Tag("foo", "/foo"),
            factory.make_Tag("bar", "//lldp:bar"),
            factory.make_Tag("baz", "/foo/bar"),
            ]
        populate_tags_for_single_node(tags, node)
        self.assertItemsEqual(
            ["foo", "bar"], [tag.name for tag in node.tags.all()])

    def test_ignores_tags_with_unrecognised_namespaces(self):
        node = factory.make_Node()
        factory.make_NodeResult_for_commissioning(
            node, commissioningscript.LSHW_OUTPUT_NAME, 0, b"<foo/>")
        tags = [
            factory.make_Tag("foo", "/foo"),
            factory.make_Tag("lou", "//nge:bar"),
            ]
        populate_tags_for_single_node(tags, node)  # Look mom, no exception!
        self.assertSequenceEqual(
            ["foo"], [tag.name for tag in node.tags.all()])

    def test_ignores_tags_without_definition(self):
        node = factory.make_Node()
        factory.make_NodeResult_for_commissioning(
            node, commissioningscript.LSHW_OUTPUT_NAME, 0, b"<foo/>")
        tags = [
            factory.make_Tag("foo", "/foo"),
            Tag(name="empty", definition=""),
            Tag(name="null", definition=None),
            ]
        populate_tags_for_single_node(tags, node)  # Look mom, no exception!
        self.assertSequenceEqual(
            ["foo"], [tag.name for tag in node.tags.all()])
