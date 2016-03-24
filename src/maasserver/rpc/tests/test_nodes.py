# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test for RPC utility functions for Nodes."""

__all__ = []

from datetime import timedelta
import json
from json import dumps
from operator import attrgetter
import random
from random import randint

from django.core.exceptions import ValidationError
from maasserver.enum import (
    INTERFACE_TYPE,
    NODE_STATUS,
)
from maasserver.models.node import Node
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
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import (
    post_commit_hooks,
    reload_object,
)
from maastesting.twisted import always_succeed_with
from provisioningserver.drivers import gen_power_types
from provisioningserver.rpc.cluster import DescribePowerTypes
from provisioningserver.rpc.exceptions import (
    CommissionNodeFailed,
    NodeAlreadyExists,
    NodeStateViolation,
    NoSuchNode,
)
from testtools import ExpectedException
from testtools.matchers import (
    GreaterThan,
    Is,
    LessThan,
    Not,
)


class TestCreateNode(MAASServerTestCase):

    def prepare_rack_rpc(self):
        rack_controller = factory.make_RackController()
        self.useFixture(RegionEventLoopFixture('rpc'))
        self.useFixture(RunningEventLoopFixture())

        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(rack_controller, DescribePowerTypes)
        self.power_types = list(gen_power_types())
        protocol.DescribePowerTypes.side_effect = always_succeed_with(
            {'power_types': self.power_types})
        return protocol

    def test__creates_node(self):
        self.prepare_rack_rpc()

        mac_addresses = [
            factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        power_type = random.choice(self.power_types)['name']
        power_parameters = dumps({})

        node = create_node(
            architecture, power_type, power_parameters,
            mac_addresses)

        self.assertEqual(
            (
                architecture,
                power_type,
                {},
            ),
            (
                node.architecture,
                node.power_type,
                node.power_parameters
            ))

        # Node will not have an auto-generated name because migrations are
        # not ran in the testing environment.
        # self.expectThat(node.hostname, Contains("-"))
        self.expectThat(node.id, Not(Is(None)))
        self.assertItemsEqual(
            mac_addresses,
            [nic.mac_address for nic in node.interface_set.all()])

    def test__creates_node_with_explicit_hostname(self):
        self.prepare_rack_rpc()

        mac_addresses = [
            factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        hostname = factory.make_hostname()
        power_type = random.choice(self.power_types)['name']
        power_parameters = dumps({})

        node = create_node(
            architecture, power_type, power_parameters,
            mac_addresses, hostname=hostname)

        self.assertEqual(
            (
                architecture,
                power_type,
                {},
                hostname
            ),
            (
                node.architecture,
                node.power_type,
                node.power_parameters,
                node.hostname
            ))
        self.expectThat(node.id, Not(Is(None)))
        self.assertItemsEqual(
            mac_addresses,
            [nic.mac_address for nic in node.interface_set.all()])

    def test__create_node_fails_with_invalid_hostname(self):
        self.prepare_rack_rpc()

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
                architecture, power_type, power_parameters,
                mac_addresses, hostname=hostname)

    def test__creates_node_with_explicit_domain(self):
        self.prepare_rack_rpc()

        mac_addresses = [
            factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        hostname = factory.make_hostname()
        domain = factory.make_Domain()
        power_type = random.choice(self.power_types)['name']
        power_parameters = dumps({})

        node = create_node(
            architecture, power_type, power_parameters,
            mac_addresses, domain=domain.name, hostname=hostname)

        self.assertEqual(
            (
                architecture,
                power_type,
                {},
                domain.id,
                hostname,
            ),
            (
                node.architecture,
                node.power_type,
                node.power_parameters,
                node.domain.id,
                node.hostname,
            ))
        self.expectThat(node.id, Not(Is(None)))
        self.assertItemsEqual(
            mac_addresses,
            [nic.mac_address for nic in node.interface_set.all()])

    def test__create_node_fails_with_invalid_domain(self):
        self.prepare_rack_rpc()

        mac_addresses = [
            factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        power_type = random.choice(self.power_types)['name']
        power_parameters = dumps({})

        with ExpectedException(ValidationError):
            create_node(
                architecture, power_type, power_parameters,
                mac_addresses, factory.make_name('domain'))

    def test__raises_validation_errors_for_invalid_data(self):
        self.prepare_rack_rpc()

        self.assertRaises(
            ValidationError, create_node,
            architecture="spam/eggs", power_type="scrambled",
            power_parameters=dumps({}),
            mac_addresses=[factory.make_mac_address()])

    def test__raises_error_if_node_already_exists(self):
        self.prepare_rack_rpc()

        mac_addresses = [
            factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        power_type = random.choice(self.power_types)['name']
        power_parameters = dumps({})

        create_node(
            architecture, power_type, power_parameters,
            mac_addresses)
        self.assertRaises(
            NodeAlreadyExists, create_node, architecture,
            power_type, power_parameters, [mac_addresses[0]])

    def test__saves_power_parameters(self):
        self.prepare_rack_rpc()

        mac_addresses = [
            factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        power_type = random.choice(self.power_types)['name']
        power_parameters = {
            factory.make_name('key'): factory.make_name('value')
            for _ in range(3)
        }

        node = create_node(
            architecture, power_type, dumps(power_parameters),
            mac_addresses)

        # Reload the object from the DB so that we're sure its power
        # parameters are being persisted.
        node = reload_object(node)
        self.assertEqual(power_parameters, node.power_parameters)

    def test__forces_generic_subarchitecture_if_missing(self):
        self.prepare_rack_rpc()

        mac_addresses = [
            factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self, subarch_name='generic')
        power_type = random.choice(self.power_types)['name']
        power_parameters = dumps({})

        arch, subarch = architecture.split('/')
        node = create_node(
            arch, power_type, power_parameters,
            mac_addresses)

        self.assertEqual(architecture, node.architecture)


class TestCommissionNode(MAASServerTestCase):

    def prepare_rack_rpc(self):
        rack_controller = factory.make_RackController()
        self.useFixture(RegionEventLoopFixture('rpc'))
        self.useFixture(RunningEventLoopFixture())

        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(rack_controller)
        return protocol

    def test__commissions_node(self):
        self.prepare_rack_rpc()

        user = factory.make_User()
        node = factory.make_Node(owner=user)
        self.patch(Node, "_start").return_value = None

        with post_commit_hooks:
            commission_node(node.system_id, user)

        self.assertEqual(
            NODE_STATUS.COMMISSIONING, reload_object(node).status)

    def test__raises_error_if_node_cannot_commission(self):
        self.prepare_rack_rpc()

        user = factory.make_User()
        node = factory.make_Node(
            owner=user, status=NODE_STATUS.RELEASING)

        self.assertRaises(
            CommissionNodeFailed, commission_node, node.system_id, user)


class TestMarkNodeFailed(MAASServerTestCase):

    def test__marks_node_as_failed(self):
        from maasserver.models import signals  # Circular import.
        self.addCleanup(signals.power.signals.enable)
        signals.power.signals.disable()

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
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        node, boot_purpose = request_node_info_by_mac_address(
            interface.mac_address.get_raw())
        self.assertEqual(node, interface.node)


class TestListClusterNodesPowerParameters(MAASServerTestCase):
    """Tests for the `list_cluster_nodes_power_parameters()` function."""

    # Note that there are other, one-level-removed tests for this
    # function in the TestRegionProtocol_ListNodePowerParameters
    # testcase in maasserver.rpc.tests.test_regionservice.
    # Those tests have been left there for now because they also check
    # that the return values are being formatted correctly for RPC.

    def make_Node(
            self, power_type=None, power_state_queried=None, **kwargs):
        if power_state_queried is None:
            # Ensure that this node was last queried at least 5 minutes ago.
            power_state_queried = now() - timedelta(minutes=randint(6, 16))
        node = factory.make_Node(
            power_type=power_type,
            power_state_queried=power_state_queried, **kwargs)
        return node

    def test__returns_only_accessible_nodes(self):
        rack = factory.make_RackController(power_type='')
        # Accessible nodes.
        node_ids = [
            self.make_Node(bmc_connected_to=rack).system_id
            for _ in range(5)
        ]
        # Inaccessible nodes.
        for _ in range(5):
            node = self.make_Node(bmc_connected_to=rack)
            node.bmc = None
            node.save()

        power_parameters = list_cluster_nodes_power_parameters(rack.system_id)
        system_ids = [params["system_id"] for params in power_parameters]
        self.assertEquals(sorted(node_ids), sorted(system_ids))

    def test__returns_unchecked_nodes_first(self):
        rack = factory.make_RackController(power_type='')
        datetime_10_minutes_ago = now() - timedelta(minutes=10)
        nodes = [
            self.make_Node(
                bmc_connected_to=rack,
                power_state_queried=datetime_10_minutes_ago)
            for _ in range(5)
        ]
        node_unchecked = random.choice(nodes)
        node_unchecked.power_state_queried = None
        node_unchecked.save()

        power_parameters = list_cluster_nodes_power_parameters(rack.system_id)
        system_ids = [params["system_id"] for params in power_parameters]

        # The unchecked node is always the first out.
        self.assertEqual(node_unchecked.system_id, system_ids[0])

    def test__excludes_recently_checked_nodes(self):
        rack = factory.make_RackController(power_type='')

        node_unchecked = self.make_Node(bmc_connected_to=rack)
        node_unchecked.power_state_queried = None
        node_unchecked.save()

        datetime_now = now()
        node_checked_recently = self.make_Node(bmc_connected_to=rack)
        node_checked_recently.power_state_queried = datetime_now
        node_checked_recently.save()

        datetime_10_minutes_ago = datetime_now - timedelta(minutes=10)
        node_checked_long_ago = self.make_Node(bmc_connected_to=rack)
        node_checked_long_ago.power_state_queried = datetime_10_minutes_ago
        node_checked_long_ago.save()

        power_parameters = list_cluster_nodes_power_parameters(rack.system_id)
        system_ids = [params["system_id"] for params in power_parameters]

        self.assertItemsEqual(
            {node_unchecked.system_id, node_checked_long_ago.system_id},
            system_ids)

    def test__excludes_broken_nodes(self):
        rack = factory.make_RackController(power_type='')
        node_queryable = self.make_Node(bmc_connected_to=rack)

        self.make_Node(status=NODE_STATUS.BROKEN, bmc_connected_to=rack)
        self.make_Node(
            status=NODE_STATUS.BROKEN, power_state_queried=(
                now() - timedelta(minutes=10)), bmc_connected_to=rack)

        power_parameters = list_cluster_nodes_power_parameters(rack.system_id)
        system_ids = [params["system_id"] for params in power_parameters]

        self.assertItemsEqual([node_queryable.system_id], system_ids)

    def test__excludes_no_power_type(self):
        rack = factory.make_RackController(power_type='')
        node_queryable = self.make_Node(bmc_connected_to=rack)

        factory.make_Device(power_type='')
        factory.make_Device(power_type='')
        factory.make_Device(
            power_type='', power_state_queried=(
                now() - timedelta(minutes=10)))

        power_parameters = list_cluster_nodes_power_parameters(rack.system_id)
        system_ids = [params["system_id"] for params in power_parameters]

        self.assertItemsEqual([node_queryable.system_id], system_ids)

    def test__returns_checked_nodes_in_last_checked_order(self):
        rack = factory.make_RackController(power_type='')
        nodes = [self.make_Node(bmc_connected_to=rack) for _ in range(5)]

        power_parameters = list_cluster_nodes_power_parameters(rack.system_id)
        system_ids = [params["system_id"] for params in power_parameters]

        # Checked nodes are always sorted from least recently checked to most.
        node_sort_key = attrgetter("power_state_queried", "system_id")
        nodes_in_order = sorted(nodes, key=node_sort_key)
        self.assertEqual(
            [node.system_id for node in nodes_in_order],
            system_ids)

    def test__returns_at_most_60kiB_of_JSON(self):
        # Configure the rack controller subnt to be very large so it
        # can hold that many BMC connected to the interface for the rack
        # controller.
        rack = factory.make_RackController(power_type='')
        rack_interface = rack.get_boot_interface()
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv6_network(slash=8)))
        factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet), subnet=subnet,
            interface=rack_interface)

        # Ensure that there are at least 64kiB of power parameters (when
        # converted to JSON) in the database.
        example_parameters = {"key%d" % i: "value%d" % i for i in range(100)}
        remaining = 2 ** 16
        while remaining > 0:
            node = self.make_Node(
                bmc_connected_to=rack, power_parameters=example_parameters)
            remaining -= len(json.dumps(node.get_effective_power_parameters()))

        nodes = list_cluster_nodes_power_parameters(rack.system_id)

        # The total size of the JSON is less than 60kiB, but only a bit.
        nodes_json = map(json.dumps, nodes)
        nodes_json_lengths = map(len, nodes_json)
        nodes_json_length = sum(nodes_json_lengths)
        expected_maximum = 60 * (2 ** 10)  # 60kiB
        self.expectThat(nodes_json_length, LessThan(expected_maximum + 1))
        expected_minimum = 50 * (2 ** 10)  # 50kiB
        self.expectThat(nodes_json_length, GreaterThan(expected_minimum - 1))
