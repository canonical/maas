# Copyright 2014 Canonical Ltd.  This software is licensed under the
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

import random

from django.core.exceptions import ValidationError
from maasserver.enum import NODE_STATUS
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
from provisioningserver.drivers import PowerTypeRegistry
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
from provisioningserver.rpc.testing import always_succeed_with
from simplejson import dumps
from testtools import ExpectedException
from testtools.matchers import (
    Contains,
    Equals,
    Is,
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
        from maasserver import node_query  # Circular import.
        self.addCleanup(node_query.enable)
        node_query.disable()

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

    def test_does_not_return_power_info_for_broken_nodes(self):
        cluster = factory.make_NodeGroup()
        broken_node = factory.make_Node(
            nodegroup=cluster, status=NODE_STATUS.BROKEN)

        power_parameters = list_cluster_nodes_power_parameters(cluster.uuid)
        returned_system_ids = [
            power_params['system_id'] for power_params in power_parameters]

        self.assertThat(
            returned_system_ids, Not(Contains(broken_node.system_id)))
