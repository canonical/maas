# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test for RPC utility functions for Nodes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from datetime import timedelta
from itertools import imap
import json
from operator import attrgetter
import random
from random import randint

from django.core.exceptions import ValidationError
from maasserver.enum import NODE_STATUS
from maasserver.models.timestampedmodel import now
from maasserver.rpc.nodes import (
    commission_node,
    create_node,
    list_cluster_nodes_power_parameters,
    mark_node_failed,
    request_node_info_by_mac_address,
)
from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks
from maastesting.twisted import always_succeed_with
from provisioningserver.drivers import PowerTypeRegistry
from provisioningserver.power import QUERY_POWER_TYPES
from provisioningserver.rpc.cluster import (
    DescribePowerTypes,
    StartMonitors,
)
from provisioningserver.rpc.exceptions import (
    CommissionNodeFailed,
    NodeAlreadyExists,
    NodeStateViolation,
    NoSuchNode,
)
from simplejson import dumps
from testtools import ExpectedException
from testtools.matchers import (
    Contains,
    Equals,
    GreaterThan,
    Is,
    LessThan,
    Not,
)


class TestCreateNode(MAASServerTestCase):

    def prepare_cluster_rpc(self, cluster):
        self.useFixture(RegionEventLoopFixture('rpc'))
        self.useFixture(RunningEventLoopFixture())

        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(cluster, DescribePowerTypes)
        self.power_types = [item for name, item in PowerTypeRegistry]
        protocol.DescribePowerTypes.side_effect = always_succeed_with(
            {'power_types': self.power_types})
        return protocol

    def test__creates_node(self):
        cluster = factory.make_NodeGroup()
        cluster.accept()
        self.prepare_cluster_rpc(cluster)

        mac_addresses = [
            factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        power_type = random.choice(self.power_types)['name']
        power_parameters = dumps({})

        node = create_node(
            cluster.uuid, architecture, power_type, power_parameters,
            mac_addresses)

        self.assertEqual(
            (
                cluster,
                architecture,
                power_type,
                {},
            ),
            (
                node.nodegroup,
                node.architecture,
                node.power_type,
                node.power_parameters
            ))

        # Node should have an auto-generated name containing '-'
        self.expectThat(node.hostname, Contains("-"))
        self.expectThat(node.id, Not(Is(None)))

        self.expectThat(
            mac_addresses,
            Equals(
                [mac.mac_address for mac in node.macaddress_set.all()]))

    def test__creates_node_with_explicit_hostname(self):
        cluster = factory.make_NodeGroup()
        cluster.accept()
        self.prepare_cluster_rpc(cluster)

        mac_addresses = [
            factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        hostname = factory.make_hostname()
        power_type = random.choice(self.power_types)['name']
        power_parameters = dumps({})

        node = create_node(
            cluster.uuid, architecture, power_type, power_parameters,
            mac_addresses, hostname=hostname)

        self.assertEqual(
            (
                cluster,
                architecture,
                power_type,
                {},
                hostname
            ),
            (
                node.nodegroup,
                node.architecture,
                node.power_type,
                node.power_parameters,
                node.hostname
            ))
        self.expectThat(node.id, Not(Is(None)))
        self.expectThat(
            mac_addresses,
            Equals(
                [mac.mac_address for mac in node.macaddress_set.all()]))

    def test__create_node_fails_with_invalid_hostname(self):
        cluster = factory.make_NodeGroup()
        cluster.accept()
        self.prepare_cluster_rpc(cluster)

        mac_addresses = [
            factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        hostname = random.choice([
            "---",
            "Microsoft Windows",
            ])
        power_type = random.choice(self.power_types)['name']
        power_parameters = dumps({})

        with ExpectedException(ValidationError):
            create_node(
                cluster.uuid, architecture, power_type, power_parameters,
                mac_addresses, hostname=hostname)

    def test__raises_validation_errors_for_invalid_data(self):
        cluster = factory.make_NodeGroup()
        cluster.accept()
        self.prepare_cluster_rpc(cluster)

        self.assertRaises(
            ValidationError, create_node, cluster.uuid,
            architecture="spam/eggs", power_type="scrambled",
            power_parameters=dumps({}),
            mac_addresses=[factory.make_mac_address()])

    def test__raises_error_if_node_already_exists(self):
        cluster = factory.make_NodeGroup()
        cluster.accept()
        self.prepare_cluster_rpc(cluster)

        mac_addresses = [
            factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        power_type = random.choice(self.power_types)['name']
        power_parameters = dumps({})

        create_node(
            cluster.uuid, architecture, power_type, power_parameters,
            mac_addresses)
        self.assertRaises(
            NodeAlreadyExists, create_node, cluster.uuid, architecture,
            power_type, power_parameters, [mac_addresses[0]])

    def test__saves_power_parameters(self):
        cluster = factory.make_NodeGroup()
        cluster.accept()
        self.prepare_cluster_rpc(cluster)

        mac_addresses = [
            factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        power_type = random.choice(self.power_types)['name']
        power_parameters = {
            factory.make_name('key'): factory.make_name('value')
            for _ in range(3)
        }

        node = create_node(
            cluster.uuid, architecture, power_type, dumps(power_parameters),
            mac_addresses)

        # Reload the object from the DB so that we're sure its power
        # parameters are being persisted.
        node = reload_object(node)
        self.assertEqual(power_parameters, node.power_parameters)

    def test__forces_generic_subarchitecture_if_missing(self):
        cluster = factory.make_NodeGroup()
        cluster.accept()
        self.prepare_cluster_rpc(cluster)

        mac_addresses = [
            factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self, subarch_name='generic')
        power_type = random.choice(self.power_types)['name']
        power_parameters = dumps({})

        arch, subarch = architecture.split('/')
        node = create_node(
            cluster.uuid, arch, power_type, power_parameters,
            mac_addresses)

        self.assertEqual(architecture, node.architecture)


class TestCommissionNode(MAASServerTestCase):

    def prepare_cluster_rpc(self, cluster):
        self.useFixture(RegionEventLoopFixture('rpc'))
        self.useFixture(RunningEventLoopFixture())

        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(cluster, StartMonitors)
        protocol.StartMonitors.side_effect = always_succeed_with({})
        return protocol

    def test__commissions_node(self):
        cluster = factory.make_NodeGroup()
        cluster.accept()
        self.prepare_cluster_rpc(cluster)

        user = factory.make_User()
        node = factory.make_Node(nodegroup=cluster, owner=user)

        with post_commit_hooks:
            commission_node(node.system_id, user)

        self.assertEqual(
            NODE_STATUS.COMMISSIONING, reload_object(node).status)

    def test__raises_error_if_node_cannot_commission(self):
        cluster = factory.make_NodeGroup()
        cluster.accept()
        self.prepare_cluster_rpc(cluster)

        user = factory.make_User()
        node = factory.make_Node(
            nodegroup=cluster, owner=user, status=NODE_STATUS.RELEASING)

        self.assertRaises(
            CommissionNodeFailed, commission_node, node.system_id, user)


class TestMarkNodeFailed(MAASServerTestCase):

    def test__marks_node_as_failed(self):
        from maasserver.models import signals  # Circular import.
        self.addCleanup(signals.power.enable)
        signals.power.disable()

        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        mark_node_failed(node.system_id, factory.make_name('error'))
        self.assertEqual(
            NODE_STATUS.FAILED_COMMISSIONING, reload_object(node).status)

    def test__raises_NoSuchNode_if_node_doesnt_exist(self):
        self.assertRaises(
            NoSuchNode,
            mark_node_failed, factory.make_name(), factory.make_name('error'))

    def test__raises_NodeStateViolation_if_wrong_transition(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        self.assertRaises(
            NodeStateViolation,
            mark_node_failed, node.system_id, factory.make_name('error'))


class TestRequestNodeInfoByMACAddress(MAASServerTestCase):

    def test_request_node_info_by_mac_address_raises_exception_no_mac(self):
        self.assertRaises(
            NoSuchNode, request_node_info_by_mac_address,
            factory.make_mac_address())

    def test_request_node_info_by_mac_address_returns_node_for_mac(self):
        mac_address = factory.make_MACAddress_with_Node()
        node, boot_purpose = request_node_info_by_mac_address(
            mac_address.mac_address.get_raw())
        self.assertEqual(node, mac_address.node)


class TestListClusterNodesPowerParameters(MAASServerTestCase):
    """Tests for the `list_cluster_nodes_power_parameters()` function."""

    # Note that there are other, one-level-removed tests for this
    # function in the TestRegionProtocol_ListNodePowerParameters
    # testcase in maasserver.rpc.tests.test_regionservice.
    # Those tests have been left there for now because they also check
    # that the return values are being formatted correctly for RPC.

    def make_Node(
            self, cluster, power_type=None, power_state_updated=None,
            **kwargs):
        if power_type is None:
            # Ensure that this node's power status can be queried.
            power_type = random.choice(QUERY_POWER_TYPES)
        if power_state_updated is None:
            # Ensure that this node was last queried at least 5 minutes ago.
            power_state_updated = now() - timedelta(minutes=randint(6, 16))
        return factory.make_Node(
            nodegroup=cluster, power_type=power_type,
            power_state_updated=power_state_updated, **kwargs)

    def test__returns_unchecked_nodes_first(self):
        cluster = factory.make_NodeGroup()
        nodes = [self.make_Node(cluster) for _ in xrange(5)]
        node_unchecked = random.choice(nodes)
        node_unchecked.power_state_updated = None
        node_unchecked.save()

        power_parameters = list_cluster_nodes_power_parameters(cluster.uuid)
        system_ids = [params["system_id"] for params in power_parameters]

        # The unchecked node is always the first out.
        self.assertEqual(node_unchecked.system_id, system_ids[0])

    def test__excludes_recently_checked_nodes(self):
        cluster = factory.make_NodeGroup()

        node_unchecked = self.make_Node(cluster)
        node_unchecked.power_state_updated = None
        node_unchecked.save()

        datetime_now = now()
        node_checked_recently = self.make_Node(cluster)
        node_checked_recently.power_state_updated = datetime_now
        node_checked_recently.save()

        datetime_10_minutes_ago = datetime_now - timedelta(minutes=10)
        node_checked_long_ago = self.make_Node(cluster)
        node_checked_long_ago.power_state_updated = datetime_10_minutes_ago
        node_checked_long_ago.save()

        power_parameters = list_cluster_nodes_power_parameters(cluster.uuid)
        system_ids = [params["system_id"] for params in power_parameters]

        self.assertItemsEqual(
            {node_unchecked.system_id, node_checked_long_ago.system_id},
            system_ids)

    def test__excludes_unqueryable_power_types(self):
        cluster = factory.make_NodeGroup()
        node_queryable = self.make_Node(cluster)
        self.make_Node(cluster, "foobar")  # Unqueryable power type.

        power_parameters = list_cluster_nodes_power_parameters(cluster.uuid)
        system_ids = [params["system_id"] for params in power_parameters]

        self.assertItemsEqual([node_queryable.system_id], system_ids)

    def test__excludes_broken_nodes(self):
        cluster = factory.make_NodeGroup()
        node_queryable = self.make_Node(cluster)

        self.make_Node(cluster, status=NODE_STATUS.BROKEN)
        self.make_Node(
            cluster, status=NODE_STATUS.BROKEN, power_state_updated=(
                now() - timedelta(minutes=10)))

        power_parameters = list_cluster_nodes_power_parameters(cluster.uuid)
        system_ids = [params["system_id"] for params in power_parameters]

        self.assertItemsEqual([node_queryable.system_id], system_ids)

    def test__excludes_devices(self):
        cluster = factory.make_NodeGroup()
        node_queryable = self.make_Node(cluster)

        factory.make_Device(nodegroup=cluster)
        factory.make_Device(nodegroup=cluster, power_type="ipmi")
        factory.make_Device(
            nodegroup=cluster, power_type="ipmi", power_state_updated=(
                now() - timedelta(minutes=10)))

        power_parameters = list_cluster_nodes_power_parameters(cluster.uuid)
        system_ids = [params["system_id"] for params in power_parameters]

        self.assertItemsEqual([node_queryable.system_id], system_ids)

    def test__returns_checked_nodes_in_last_checked_order(self):
        cluster = factory.make_NodeGroup()
        nodes = [self.make_Node(cluster) for _ in xrange(5)]

        power_parameters = list_cluster_nodes_power_parameters(cluster.uuid)
        system_ids = [params["system_id"] for params in power_parameters]

        # Checked nodes are always sorted from least recently checked to most.
        node_sort_key = attrgetter("power_state_updated", "system_id")
        nodes_in_order = sorted(nodes, key=node_sort_key)
        self.assertEqual(
            [node.system_id for node in nodes_in_order],
            system_ids)

    def test__returns_at_most_60kiB_of_JSON(self):
        cluster = factory.make_NodeGroup()

        # Ensure that there are at least 64kiB of power parameters (when
        # converted to JSON) in the database.
        example_parameters = {"key%d" % i: "value%d" % i for i in xrange(100)}
        remaining = 2 ** 16
        while remaining > 0:
            node = self.make_Node(cluster, power_parameters=example_parameters)
            remaining -= len(json.dumps(node.get_effective_power_parameters()))

        nodes = list_cluster_nodes_power_parameters(cluster.uuid)

        # The total size of the JSON is less than 60kiB, but only a bit.
        nodes_json = imap(json.dumps, nodes)
        nodes_json_lengths = imap(len, nodes_json)
        nodes_json_length = sum(nodes_json_lengths)
        expected_maximum = 60 * (2 ** 10)  # 60kiB
        self.expectThat(nodes_json_length, LessThan(expected_maximum + 1))
        expected_minimum = 50 * (2 ** 10)  # 50kiB
        self.expectThat(nodes_json_length, GreaterThan(expected_minimum - 1))
