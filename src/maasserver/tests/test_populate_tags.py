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

from itertools import izip

from fixtures import FakeLogger
from maasserver import populate_tags as populate_tags_module
from maasserver.enum import NODEGROUP_STATUS
from maasserver.models import Tag
from maasserver.populate_tags import (
    _do_populate_tags,
    _get_clients_for_populating_tags,
    populate_tags,
    populate_tags_for_single_node,
)
from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from metadataserver.models import commissioningscript
from mock import (
    ANY,
    create_autospec,
    sentinel,
)
from provisioningserver.rpc.cluster import EvaluateTag
from provisioningserver.rpc.common import Client
from provisioningserver.rpc.testing import (
    always_fail_with,
    always_succeed_with,
)
from provisioningserver.utils.twisted import asynchronous
from testtools.deferredruntest import extract_result
from testtools.monkey import MonkeyPatcher
from twisted.internet import defer


def make_accepted_NodeGroup():
    return factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)


def make_Tag_without_populating():
    # Create a tag but prevent evaluation when saving.
    dont_populate = MonkeyPatcher((Tag, "populate_nodes", lambda self: None))
    return dont_populate.run_with_patches(factory.make_Tag)


class TestGetClientsForPopulatingTags(MAASServerTestCase):

    def test__returns_no_clients_when_there_are_no_clusters(self):
        tag_name = factory.make_name("tag")
        clients = _get_clients_for_populating_tags([], tag_name)
        self.assertEqual([], clients)

    def patch_getClientFor(self):
        return self.patch_autospec(populate_tags_module, "getClientFor")

    def test__returns_no_clients_when_there_is_an_error(self):
        nodegroup_with_connection = make_accepted_NodeGroup()
        nodegroup_without_connection = make_accepted_NodeGroup()

        def getClientFor(uuid, timeout):
            if uuid == nodegroup_with_connection.uuid:
                return defer.succeed(sentinel.client)
            else:
                return defer.fail(ZeroDivisionError())
        self.patch_getClientFor().side_effect = getClientFor

        tag_name = factory.make_name("tag")
        clusters = [
            (nodegroup_with_connection.uuid,
             nodegroup_with_connection.cluster_name),
            (nodegroup_without_connection.uuid,
             nodegroup_without_connection.cluster_name),
        ]
        clients = _get_clients_for_populating_tags(clusters, tag_name)
        self.assertEqual([sentinel.client], clients)

    def test__logs_errors_obtaining_clients(self):
        getClientFor = self.patch_getClientFor()
        getClientFor.side_effect = always_fail_with(
            ZeroDivisionError("an error message one would surmise"))
        nodegroup = make_accepted_NodeGroup()
        tag_name = factory.make_name("tag")
        clusters = [(nodegroup.uuid, nodegroup.cluster_name)]
        with FakeLogger("maas") as log:
            _get_clients_for_populating_tags(clusters, tag_name)
        self.assertDocTestMatches(
            "Cannot evaluate tag ... on cluster ... (...): ... surmise",
            log.output)

    def test__waits_for_clients_for_30_seconds_by_default(self):
        getClientFor = self.patch_getClientFor()
        getClientFor.side_effect = always_succeed_with(sentinel.client)
        nodegroup = make_accepted_NodeGroup()
        tag_name = factory.make_name("tag")
        clusters = [(nodegroup.uuid, nodegroup.cluster_name)]
        clients = _get_clients_for_populating_tags(clusters, tag_name)
        self.assertEqual([sentinel.client], clients)
        self.assertThat(
            getClientFor, MockCalledOnceWith(
                nodegroup.uuid, timeout=30))

    def test__obtains_multiple_clients(self):
        getClientFor = self.patch_getClientFor()
        # Return a 2-tuple as a stand-in for a real client.
        getClientFor.side_effect = lambda uuid, timeout: (
            defer.succeed((sentinel.client, uuid)))
        nodegroups = [make_accepted_NodeGroup() for _ in xrange(3)]
        tag_name = factory.make_name("tag")
        clusters = [(ng.uuid, ng.cluster_name) for ng in nodegroups]
        clients = _get_clients_for_populating_tags(clusters, tag_name)
        self.assertItemsEqual(
            [(sentinel.client, nodegroup.uuid) for nodegroup in nodegroups],
            clients)


class TestDoPopulateTags(MAASServerTestCase):

    def patch_clients(self, nodegroups):
        clients = [create_autospec(Client, instance=True) for _ in nodegroups]
        for nodegroup, client in izip(nodegroups, clients):
            client.side_effect = always_succeed_with(None)
            client.ident = nodegroup.uuid

        _get_clients = self.patch_autospec(
            populate_tags_module, "_get_clients_for_populating_tags")
        _get_clients.return_value = defer.succeed(clients)

        return clients

    def test__makes_calls_to_each_client_given(self):
        nodegroups = [make_accepted_NodeGroup() for _ in xrange(3)]
        clients = self.patch_clients(nodegroups)

        tag_name = factory.make_name("tag")
        tag_definition = factory.make_name("definition")
        tag_nsmap_prefix = factory.make_name("prefix")
        tag_nsmap_uri = factory.make_name("uri")
        tag_nsmap = {tag_nsmap_prefix: tag_nsmap_uri}

        clusters = list(
            (ng.uuid, ng.cluster_name, ng.api_credentials)
            for ng in nodegroups)

        [d] = _do_populate_tags(
            clusters, tag_name, tag_definition, tag_nsmap)

        self.assertIsNone(extract_result(d))

        for nodegroup, client in izip(nodegroups, clients):
            self.expectThat(client, MockCalledOnceWith(
                EvaluateTag, tag_name=tag_name, tag_definition=tag_definition,
                tag_nsmap=[{"prefix": tag_nsmap_prefix, "uri": tag_nsmap_uri}],
                credentials=nodegroup.api_credentials))

    def test__logs_successes(self):
        nodegroups = [make_accepted_NodeGroup()]
        self.patch_clients(nodegroups)

        tag_name = factory.make_name("tag")
        tag_definition = factory.make_name("definition")
        tag_nsmap = {}

        clusters = list(
            (ng.uuid, ng.cluster_name, ng.api_credentials)
            for ng in nodegroups)

        with FakeLogger("maas") as log:
            [d] = _do_populate_tags(
                clusters, tag_name, tag_definition, tag_nsmap)
            self.assertIsNone(extract_result(d))

        self.assertDocTestMatches(
            "Tag tag-... (definition-...) evaluated on cluster ... (...)",
            log.output)

    def test__logs_failures(self):
        nodegroups = [make_accepted_NodeGroup()]
        [client] = self.patch_clients(nodegroups)
        client.side_effect = always_fail_with(
            ZeroDivisionError("splendid day for a spot of cricket"))

        tag_name = factory.make_name("tag")
        tag_definition = factory.make_name("definition")
        tag_nsmap = {}

        clusters = list(
            (ng.uuid, ng.cluster_name, ng.api_credentials)
            for ng in nodegroups)

        with FakeLogger("maas") as log:
            [d] = _do_populate_tags(
                clusters, tag_name, tag_definition, tag_nsmap)
            self.assertIsNone(extract_result(d))

        self.assertDocTestMatches(
            "Tag tag-... (definition-...) could not be evaluated ... (...): "
            "splendid day for a spot of cricket", log.output)


class TestPopulateTags(MAASServerTestCase):

    def patch_do_populate_tags(self):
        do_populate_tags = self.patch_autospec(
            populate_tags_module, "_do_populate_tags")
        do_populate_tags.return_value = [sentinel.d]
        return do_populate_tags

    def test__calls_do_populate_tags_with_no_clusters(self):
        do_populate_tags = self.patch_do_populate_tags()
        tag = make_Tag_without_populating()
        populate_tags(tag)
        self.assertThat(do_populate_tags, MockCalledOnceWith(
            (), tag.name, tag.definition, populate_tags_module.tag_nsmap))

    def test__calls_do_populate_tags_with_clusters(self):
        do_populate_tags = self.patch_do_populate_tags()
        nodegroups = [make_accepted_NodeGroup() for _ in xrange(3)]
        tag = make_Tag_without_populating()
        populate_tags(tag)
        clusters_expected = tuple(
            (ng.uuid, ng.cluster_name, ng.api_credentials)
            for ng in nodegroups)
        self.assertThat(do_populate_tags, MockCalledOnceWith(
            clusters_expected, tag.name, tag.definition,
            populate_tags_module.tag_nsmap))


class TestPopulateTagsEndToNearlyEnd(MAASServerTestCase):

    def prepare_live_rpc(self):
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        return self.useFixture(MockLiveRegionToClusterRPCFixture())

    def test__calls_are_made_to_all_clusters(self):
        rpc_fixture = self.prepare_live_rpc()
        nodegroups = [make_accepted_NodeGroup() for _ in xrange(3)]
        protocols = []
        for nodegroup in nodegroups:
            protocol = rpc_fixture.makeCluster(nodegroup, EvaluateTag)
            protocol.EvaluateTag.side_effect = always_succeed_with({})
            protocols.append(protocol)
        tag = make_Tag_without_populating()

        d = populate_tags(tag)

        # `d` is a testing-only convenience. We must wait for it to fire, and
        # we must do that from the reactor thread.
        wait_for_populate = asynchronous(lambda: d)
        wait_for_populate().wait(10)

        for nodegroup, protocol in izip(nodegroups, protocols):
            self.expectThat(protocol.EvaluateTag, MockCalledOnceWith(
                protocol, tag_name=tag.name, tag_definition=tag.definition,
                tag_nsmap=ANY, credentials=nodegroup.api_credentials))


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
