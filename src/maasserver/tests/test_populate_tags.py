# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from unittest.mock import ANY, call, create_autospec

from django.db import transaction
from fixtures import FakeLogger
from twisted.internet import reactor
from twisted.internet.base import DelayedCall
from twisted.internet.task import Clock
from twisted.internet.threads import blockingCallFromThread

from apiclient.creds import convert_tuple_to_string
from maasserver import populate_tags as populate_tags_module
from maasserver import rpc as rpc_module
from maasserver.models import Node, Tag
from maasserver.models import tag as tag_module
from maasserver.models.user import (
    create_auth_token,
    get_auth_tokens,
    get_creds_tuple,
)
from maasserver.populate_tags import (
    _do_populate_tags,
    populate_tag_for_multiple_nodes,
    populate_tags,
    populate_tags_for_single_node,
)
from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import post_commit_hooks
from maasserver.utils.threads import deferToDatabase
from maastesting import get_testing_timeout
from maastesting.twisted import (
    always_fail_with,
    always_succeed_with,
    extract_result,
)
from metadataserver.enum import RESULT_TYPE, SCRIPT_STATUS
from provisioningserver.refresh.node_info_scripts import (
    LLDP_OUTPUT_NAME,
    LSHW_OUTPUT_NAME,
)
from provisioningserver.rpc.cluster import EvaluateTag
from provisioningserver.rpc.common import Client
from provisioningserver.utils.twisted import asynchronous


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

    def test_makes_calls_to_each_client_given(self):
        rack_controllers = [factory.make_RackController() for _ in range(3)]
        clients = self.patch_clients(rack_controllers)

        tag_name = factory.make_name("tag")
        tag_definition = factory.make_name("definition")
        tag_nsmap_prefix = factory.make_name("prefix")
        tag_nsmap_uri = factory.make_name("uri")
        tag_nsmap = [{"prefix": tag_nsmap_prefix, "uri": tag_nsmap_uri}]

        work = []
        rack_creds = []
        rack_nodes = []
        for rack, client in zip(rack_controllers, clients):
            creds = factory.make_name("creds")
            rack_creds.append(creds)
            nodes = [
                {"system_id": factory.make_Node().system_id} for _ in range(3)
            ]
            rack_nodes.append(nodes)
            work.append(
                {
                    "system_id": rack.system_id,
                    "hostname": rack.hostname,
                    "client": client,
                    "tag_name": tag_name,
                    "tag_definition": tag_definition,
                    "tag_nsmap": tag_nsmap,
                    "credentials": creds,
                    "nodes": nodes,
                }
            )

        [d] = _do_populate_tags(work)

        self.assertIsNone(extract_result(d))

        for rack, client, creds, nodes in zip(
            rack_controllers, clients, rack_creds, rack_nodes
        ):
            self.assertEqual(
                client.mock_calls,
                [
                    call(
                        EvaluateTag,
                        system_id=rack.system_id,
                        tag_name=tag_name,
                        tag_definition=tag_definition,
                        tag_nsmap=tag_nsmap,
                        credentials=creds,
                        nodes=nodes,
                    )
                ],
            )

    def test_logs_successes(self):
        rack_controller = factory.make_RackController()
        clients = self.patch_clients([rack_controller])

        tag_name = factory.make_name("tag")
        tag_definition = factory.make_name("definition")
        tag_nsmap = {}

        work = []
        for rack, client in zip([rack_controller], clients):
            work.append(
                {
                    "system_id": rack.system_id,
                    "hostname": rack.hostname,
                    "client": client,
                    "tag_name": tag_name,
                    "tag_definition": tag_definition,
                    "tag_nsmap": tag_nsmap,
                    "credentials": factory.make_name("creds"),
                    "nodes": [
                        {"system_id": factory.make_Node().system_id}
                        for _ in range(3)
                    ],
                }
            )

        with FakeLogger("maas") as log:
            [d] = _do_populate_tags(work)
            self.assertIsNone(extract_result(d))

        self.assertEqual(
            f"Tag {tag_name} ({tag_definition}) evaluated on rack controller {rack_controller.hostname} ({rack_controller.system_id})\n",
            log.output,
        )

    def test_logs_failures(self):
        rack_controller = factory.make_RackController()
        clients = self.patch_clients([rack_controller])
        clients[0].side_effect = always_fail_with(
            ZeroDivisionError("splendid day for a spot of cricket")
        )

        tag_name = factory.make_name("tag")
        tag_definition = factory.make_name("definition")
        tag_nsmap = {}

        work = []
        for rack, client in zip([rack_controller], clients):
            work.append(
                {
                    "system_id": rack.system_id,
                    "hostname": rack.hostname,
                    "client": client,
                    "tag_name": tag_name,
                    "tag_definition": tag_definition,
                    "tag_nsmap": tag_nsmap,
                    "credentials": factory.make_name("creds"),
                    "nodes": [
                        {"system_id": factory.make_Node().system_id}
                        for _ in range(3)
                    ],
                }
            )

        with FakeLogger("maas") as log:
            [d] = _do_populate_tags(work)
            self.assertIsNone(extract_result(d))

        self.assertEqual(
            (
                f"Tag {tag_name} ({tag_definition}) could not be evaluated on rack controller "
                f"{rack_controller.hostname} ({rack_controller.system_id}): splendid day for a spot of cricket\n"
            ),
            log.output,
        )


class TestPopulateTagsEndToNearlyEnd(MAASTransactionServerTestCase):
    """Tests for populating tags on racks.

    This happens when there are connected rack controllers able to carry out
    the task.
    """

    def prepare_live_rpc(self):
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        return self.useFixture(MockLiveRegionToClusterRPCFixture())

    def test_populate_tags_fails_called_in_transaction(self):
        with transaction.atomic():
            tag = factory.make_Tag(populate=False)
            self.assertRaises(
                transaction.TransactionManagementError, populate_tags, tag
            )

    def test_calls_are_made_to_all_clusters(self):
        rpc_fixture = self.prepare_live_rpc()
        rack_controllers = [factory.make_RackController() for _ in range(3)]
        protocols = []
        rack_creds = []
        for rack in rack_controllers:
            tokens = list(get_auth_tokens(rack.owner))
            if len(tokens) > 0:
                # Use the latest token.
                token = tokens[-1]
            else:
                token = create_auth_token(rack.owner)
            creds = convert_tuple_to_string(get_creds_tuple(token))
            rack_creds.append(creds)

            protocol = rpc_fixture.makeCluster(rack, EvaluateTag)
            protocol.EvaluateTag.side_effect = always_succeed_with({})
            protocols.append(protocol)
        tag = factory.make_Tag(populate=False)

        [d] = populate_tags(tag)

        # `d` is a testing-only convenience. We must wait for it to fire, and
        # we must do that from the reactor thread.
        wait_for_populate = asynchronous(lambda: d)
        wait_for_populate().wait(get_testing_timeout())

        for rack, protocol, creds in zip(
            rack_controllers, protocols, rack_creds
        ):
            protocol.EvaluateTag.assert_called_once_with(
                protocol,
                tag_name=tag.name,
                tag_definition=tag.definition,
                system_id=rack.system_id,
                tag_nsmap=ANY,
                credentials=creds,
                nodes=ANY,
            )


class TestPopulateTagsInRegion(MAASTransactionServerTestCase):
    """Tests for populating tags in the region.

    This happens when there are no rack controllers to carry out the task.
    """

    def test_saving_tag_schedules_node_population(self):
        clock = self.patch(tag_module, "reactor", Clock())

        with post_commit_hooks:
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
        self.assertEqual(call.func, deferToDatabase)
        self.assertEqual(call.args, (populate_tags, tag))
        self.assertEqual(call.kw, {})

    def test_populate_in_region_when_no_clients(self):
        clock = self.patch(tag_module, "reactor", Clock())

        # Ensure there are no clients.
        self.patch(rpc_module, "getAllClients").return_value = []

        with post_commit_hooks:
            node = factory.make_Node()
            # Make a Tag by hand to trigger normal node population handling
            # behaviour rather than the (generally more convenient) default
            # behaviour in the factory.
            tag = Tag(name=factory.make_name("tag"), definition="true()")
            tag.save()

        # A call has been scheduled to populate tags.
        [call] = clock.getDelayedCalls()
        # Execute the call ourselves in the real reactor.
        blockingCallFromThread(reactor, call.func, *call.args, **call.kw)
        # The tag's node set has been updated.
        self.assertCountEqual([node], tag.node_set.all())


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
