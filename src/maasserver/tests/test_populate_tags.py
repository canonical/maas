# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from unittest.mock import create_autospec

from twisted.internet.base import DelayedCall
from twisted.internet.task import Clock

from maasserver import populate_tags as populate_tags_module
from maasserver.models import Node, Tag
from maasserver.models import tag as tag_module
from maasserver.populate_tags import (
    populate_tag_for_multiple_nodes,
    populate_tags_for_single_node,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maastesting.twisted import always_succeed_with
from metadataserver.enum import RESULT_TYPE, SCRIPT_STATUS
from provisioningserver.refresh.node_info_scripts import (
    LLDP_OUTPUT_NAME,
    LSHW_OUTPUT_NAME,
)
from provisioningserver.rpc.common import Client


def make_script_result(node, script_name=None, stdout=None, exit_status=0):
    script_set = node.current_commissioning_script_set
    if script_set is None:
        script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.COMMISSIONING
        )
        node.current_commissioning_script_set = script_set
        node.save()
    if exit_status == 0:
        status = SCRIPT_STATUS.PASSED
    else:
        status = SCRIPT_STATUS.FAILED
    return factory.make_ScriptResult(
        script_set=script_set,
        status=status,
        exit_status=exit_status,
        script_name=script_name,
        stdout=stdout,
    )


def make_lshw_result(node, stdout=None, exit_status=0):
    return make_script_result(node, LSHW_OUTPUT_NAME, stdout, exit_status)


def make_lldp_result(node, stdout=None, exit_status=0):
    return make_script_result(node, LLDP_OUTPUT_NAME, stdout, exit_status)


class TestDoPopulateTags(MAASServerTestCase):
    def patch_clients(self, rack_controllers):
        clients = [
            create_autospec(Client, instance=True) for _ in rack_controllers
        ]
        for rack, client in zip(rack_controllers, clients):
            client.side_effect = always_succeed_with(None)
            client.ident = rack.system_id

        _get_clients = self.patch_autospec(
            populate_tags_module, "getAllClients"
        )
        _get_clients.return_value = clients

        return clients


class TestPopulateTagsInRegion(MAASTransactionServerTestCase):
    """Tests for populating tags in the region.

    This happens when there are no rack controllers to carry out the task.
    """

    def test_saving_tag_schedules_node_population(self):
        clock = self.patch(tag_module, "reactor", Clock())

        # Make a Tag by hand to trigger normal node population handling
        # behaviour rather than the (generally more convenient) default
        # behaviour in the factory.
        tag = Tag(name=factory.make_name("tag"), definition="true()")
        tag.save()

        # A call has been scheduled to populate tags.
        calls = clock.getDelayedCalls()
        self.assertEqual(len(calls), 1)
        [call] = calls
        self.assertIsInstance(call, DelayedCall)
        self.assertEqual(call.time, 0)
        self.assertEqual(call.func, tag._update_tag_node_relations)
        self.assertEqual(call.args, ())
        self.assertEqual(call.kw, {})


class TestPopulateTagsForSingleNode(MAASServerTestCase):
    def test_updates_node_with_all_applicable_tags(self):
        node = factory.make_Node()
        make_lshw_result(node, b"<foo/>")
        make_lldp_result(node, b"<bar/>")
        tags = [
            factory.make_Tag("foo", "/foo", populate=False),
            factory.make_Tag("bar", "//lldp:bar", populate=False),
            factory.make_Tag("baz", "/foo/bar", populate=False),
        ]
        populate_tags_for_single_node(tags, node)
        self.assertCountEqual(
            ["foo", "bar"], [tag.name for tag in node.tags.all()]
        )

    def test_ignores_tags_with_unrecognised_namespaces(self):
        node = factory.make_Node()
        make_lshw_result(node, b"<foo/>")
        tags = [
            factory.make_Tag("foo", "/foo", populate=False),
            factory.make_Tag("lou", "//nge:bar", populate=False),
        ]
        populate_tags_for_single_node(tags, node)  # Look mom, no exception!
        self.assertSequenceEqual(
            ["foo"], [tag.name for tag in node.tags.all()]
        )

    def test_ignores_tags_without_definition(self):
        node = factory.make_Node()
        make_lshw_result(node, b"<foo/>")
        tags = [
            factory.make_Tag("foo", "/foo", populate=False),
            Tag(name="empty", definition=""),
        ]
        populate_tags_for_single_node(tags, node)  # Look mom, no exception!
        self.assertSequenceEqual(
            ["foo"], [tag.name for tag in node.tags.all()]
        )


class TestPopulateTagForMultipleNodes(MAASServerTestCase):
    def test_updates_nodes_with_tag(self):
        nodes = [factory.make_Node() for _ in range(5)]
        for node in nodes[0:2]:
            make_lldp_result(node, b"<bar/>")
        tag = factory.make_Tag("bar", "//lldp:bar", populate=False)
        populate_tag_for_multiple_nodes(tag, nodes)
        self.assertCountEqual(
            [node.hostname for node in nodes[0:2]],
            [node.hostname for node in Node.objects.filter(tags__name="bar")],
        )
