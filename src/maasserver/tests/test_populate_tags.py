# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
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

from maasserver import populate_tags as populate_tags_module
from maasserver.models import Tag
from maasserver.populate_tags import (
    populate_tags,
    populate_tags_for_single_node,
    tag_nsmap,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.models import commissioningscript
import mock


class TestPopulateTags(MAASServerTestCase):

    def test_populate_tags_task_routed_to_nodegroup_worker(self):
        nodegroup = factory.make_node_group()
        tag = factory.make_tag()
        task = self.patch(populate_tags_module, 'update_node_tags')
        populate_tags(tag)
        args, kwargs = task.apply_async.call_args
        self.assertEqual(nodegroup.work_queue, kwargs['queue'])

    def test_populate_tags_task_routed_to_all_nodegroup_workers(self):
        nodegroups = [factory.make_node_group() for i in range(5)]
        tag = factory.make_tag()
        refresh = self.patch(populate_tags_module, 'refresh_worker')
        task = self.patch(populate_tags_module, 'update_node_tags')
        populate_tags(tag)
        refresh_calls = [mock.call(nodegroup) for nodegroup in nodegroups]
        refresh.assert_has_calls(refresh_calls, any_order=True)
        task_calls = [
            mock.call(
                queue=nodegroup.work_queue,
                kwargs={
                    'tag_name': tag.name,
                    'tag_definition': tag.definition,
                    'tag_nsmap': tag_nsmap,
                },
            )
            for nodegroup in nodegroups
        ]
        task.apply_async.assert_has_calls(task_calls, any_order=True)


class TestPopulateTagsForSingleNode(MAASServerTestCase):

    def test_updates_node_with_all_applicable_tags(self):
        node = factory.make_node()
        factory.make_node_commission_result(
            node, commissioningscript.LSHW_OUTPUT_NAME, 0, b"<foo/>")
        factory.make_node_commission_result(
            node, commissioningscript.LLDP_OUTPUT_NAME, 0, b"<bar/>")
        tags = [
            factory.make_tag("foo", "/foo"),
            factory.make_tag("bar", "//lldp:bar"),
            factory.make_tag("baz", "/foo/bar"),
            ]
        populate_tags_for_single_node(tags, node)
        self.assertItemsEqual(
            ["foo", "bar"], [tag.name for tag in node.tags.all()])

    def test_ignores_tags_with_unrecognised_namespaces(self):
        node = factory.make_node()
        factory.make_node_commission_result(
            node, commissioningscript.LSHW_OUTPUT_NAME, 0, b"<foo/>")
        tags = [
            factory.make_tag("foo", "/foo"),
            factory.make_tag("lou", "//nge:bar"),
            ]
        populate_tags_for_single_node(tags, node)  # Look mom, no exception!
        self.assertSequenceEqual(
            ["foo"], [tag.name for tag in node.tags.all()])

    def test_ignores_tags_without_definition(self):
        node = factory.make_node()
        factory.make_node_commission_result(
            node, commissioningscript.LSHW_OUTPUT_NAME, 0, b"<foo/>")
        tags = [
            factory.make_tag("foo", "/foo"),
            Tag(name="empty", definition=""),
            Tag(name="null", definition=None),
            ]
        populate_tags_for_single_node(tags, node)  # Look mom, no exception!
        self.assertSequenceEqual(
            ["foo"], [tag.name for tag in node.tags.all()])
