# Copyright 2014-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test for RPC utility functions for Nodes."""


from datetime import timedelta
import json
from operator import attrgetter
import random
from random import randint
from unittest.mock import sentinel

from django.core.exceptions import ValidationError
from testtools import ExpectedException
from testtools.matchers import Equals, GreaterThan, HasLength, LessThan

from maasserver import ntp
from maasserver.enum import INTERFACE_TYPE, NODE_STATUS, NODE_TYPE, POWER_STATE
from maasserver.models.node import Node
from maasserver.models.timestampedmodel import now
from maasserver.rpc.nodes import (
    commission_node,
    create_node,
    get_controller_type,
    get_time_configuration,
    list_cluster_nodes_power_parameters,
    mark_node_failed,
    request_node_info_by_mac_address,
    update_node_power_state,
)
from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import post_commit_hooks, reload_object
from maastesting.twisted import always_succeed_with
from metadataserver.builtin_scripts import load_builtin_scripts
from provisioningserver.drivers.power.registry import PowerDriverRegistry
from provisioningserver.rpc.cluster import DescribePowerTypes
from provisioningserver.rpc.exceptions import (
    CommissionNodeFailed,
    NodeAlreadyExists,
    NodeStateViolation,
    NoSuchCluster,
    NoSuchNode,
)


class TestCreateNode(MAASTransactionServerTestCase):
    def prepare_rack_rpc(self):
        rack_controller = factory.make_RackController()
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())

        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(rack_controller, DescribePowerTypes)
        self.power_types = PowerDriverRegistry.get_schema()
        protocol.DescribePowerTypes.side_effect = always_succeed_with(
            {"power_types": self.power_types}
        )
        return protocol

    def test_creates_node(self):
        self.prepare_rack_rpc()

        mac_addresses = [factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)

        node = create_node(architecture, "manual", {}, mac_addresses)

        self.assertEqual(
            (architecture, "manual", {}),
            (node.architecture, node.power_type, node.get_power_parameters()),
        )

        # Node will not have an auto-generated name because migrations are
        # not ran in the testing environment.
        # self.expectThat(node.hostname, Contains("-"))
        self.assertIsNotNone(node.id)
        self.assertCountEqual(
            mac_addresses,
            [
                nic.mac_address
                for nic in node.current_config.interface_set.all()
            ],
        )

    def test_creates_node_with_explicit_hostname(self):
        self.prepare_rack_rpc()

        mac_addresses = [factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        hostname = factory.make_hostname()

        node = create_node(
            architecture, "manual", {}, mac_addresses, hostname=hostname
        )

        self.assertEqual(
            (architecture, "manual", {}, hostname),
            (
                node.architecture,
                node.power_type,
                node.get_power_parameters(),
                node.hostname,
            ),
        )
        self.assertIsNotNone(node.id)
        self.assertCountEqual(
            mac_addresses,
            [
                nic.mac_address
                for nic in node.current_config.interface_set.all()
            ],
        )

    def test_create_node_fails_with_invalid_hostname(self):
        self.prepare_rack_rpc()

        mac_addresses = [factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        hostname = random.choice(["---", "Microsoft Windows"])
        power_type = random.choice(self.power_types)["name"]
        power_parameters = {}

        with ExpectedException(ValidationError):
            create_node(
                architecture,
                power_type,
                power_parameters,
                mac_addresses,
                hostname=hostname,
            )

    def test_creates_node_with_explicit_domain(self):
        self.prepare_rack_rpc()

        mac_addresses = [factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        hostname = factory.make_hostname()
        domain = factory.make_Domain()

        node = create_node(
            architecture,
            "manual",
            {},
            mac_addresses,
            domain=domain.name,
            hostname=hostname,
        )

        self.assertEqual(
            (architecture, "manual", {}, domain.id, hostname),
            (
                node.architecture,
                node.power_type,
                node.get_power_parameters(),
                node.domain.id,
                node.hostname,
            ),
        )
        self.assertIsNotNone(node.id)
        self.assertCountEqual(
            mac_addresses,
            [
                nic.mac_address
                for nic in node.current_config.interface_set.all()
            ],
        )

    def test_create_node_fails_with_invalid_domain(self):
        self.prepare_rack_rpc()

        mac_addresses = [factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        power_type = random.choice(self.power_types)["name"]
        power_parameters = {}

        with ExpectedException(ValidationError):
            create_node(
                architecture,
                power_type,
                power_parameters,
                mac_addresses,
                factory.make_name("domain"),
            )

    def test_raises_validation_errors_for_invalid_data(self):
        self.prepare_rack_rpc()

        self.assertRaises(
            ValidationError,
            create_node,
            architecture="spam/eggs",
            power_type="scrambled",
            power_parameters={},
            mac_addresses=[factory.make_mac_address()],
        )

    def test_raises_error_if_node_already_exists(self):
        self.prepare_rack_rpc()

        mac_addresses = [factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        power_type = "manual"
        power_parameters = {}

        create_node(architecture, power_type, power_parameters, mac_addresses)
        self.assertRaises(
            NodeAlreadyExists,
            create_node,
            architecture,
            power_type,
            power_parameters,
            [mac_addresses[0]],
        )

    def test_saves_power_parameters(self):
        self.prepare_rack_rpc()

        mac_addresses = [factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        power_parameters = {
            "power_address": factory.make_ip_address(),  # XXX: URLs break.
            "power_pass": factory.make_name("power_pass"),
            "power_id": factory.make_name("power_id"),
        }

        node = create_node(
            architecture, "virsh", power_parameters, mac_addresses
        )

        # Reload the object from the DB so that we're sure its power
        # parameters are being persisted.
        node = reload_object(node)
        self.assertEqual(power_parameters, node.get_power_parameters())

    def test_forces_generic_subarchitecture_if_missing(self):
        self.prepare_rack_rpc()

        mac_addresses = [factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self, subarch_name="generic")

        arch, subarch = architecture.split("/")
        node = create_node(arch, "manual", {}, mac_addresses)

        self.assertEqual(architecture, node.architecture)


class TestCommissionNode(MAASTransactionServerTestCase):
    def prepare_rack_rpc(self):
        rack_controller = factory.make_RackController()
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())

        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(rack_controller)
        return protocol

    def test_raises_NoSuchNode_if_node_doesnt_exist(self):
        self.assertRaises(
            NoSuchNode,
            commission_node,
            factory.make_name("system_id"),
            factory.make_name("user"),
        )

    def test_commissions_node(self):
        load_builtin_scripts()
        self.prepare_rack_rpc()

        user = factory.make_User()
        node = factory.make_Node(owner=user)
        self.patch(Node, "_start").return_value = None

        with post_commit_hooks:
            commission_node(node.system_id, user)

        self.assertEqual(NODE_STATUS.COMMISSIONING, reload_object(node).status)

    def test_raises_error_if_node_cannot_commission(self):
        self.prepare_rack_rpc()

        user = factory.make_User()
        node = factory.make_Node(owner=user, status=NODE_STATUS.RELEASING)

        self.assertRaises(
            CommissionNodeFailed, commission_node, node.system_id, user
        )


class TestMarkNodeFailed(MAASServerTestCase):
    def test_marks_node_as_failed(self):
        from maasserver.models import signals  # Circular import.

        self.addCleanup(signals.power.signals.enable)
        signals.power.signals.disable()

        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        mark_node_failed(node.system_id, factory.make_name("error"))
        self.assertEqual(
            NODE_STATUS.FAILED_COMMISSIONING, reload_object(node).status
        )

    def test_raises_NoSuchNode_if_node_doesnt_exist(self):
        self.assertRaises(
            NoSuchNode,
            mark_node_failed,
            factory.make_name(),
            factory.make_name("error"),
        )

    def test_raises_NodeStateViolation_if_wrong_transition(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        self.assertRaises(
            NodeStateViolation,
            mark_node_failed,
            node.system_id,
            factory.make_name("error"),
        )


class TestRequestNodeInfoByMACAddress(MAASServerTestCase):
    def test_request_node_info_by_mac_address_raises_exception_no_mac(self):
        self.assertRaises(
            NoSuchNode,
            request_node_info_by_mac_address,
            factory.make_mac_address(),
        )

    def test_request_node_info_by_mac_address_returns_node_for_mac(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        node, boot_purpose = request_node_info_by_mac_address(
            interface.mac_address
        )
        self.assertEqual(node, interface.node_config.node)


class TestListClusterNodesPowerParameters(MAASServerTestCase):
    """Tests for the `list_cluster_nodes_power_parameters()` function."""

    # Note that there are other, one-level-removed tests for this
    # function in the TestRegionProtocol_ListNodePowerParameters
    # testcase in maasserver.rpc.tests.test_regionservice.
    # Those tests have been left there for now because they also check
    # that the return values are being formatted correctly for RPC.

    def make_Node(self, power_state_queried=None, **kwargs):
        if power_state_queried is None:
            # Ensure that this node was last queried at least 5 minutes ago.
            power_state_queried = now() - timedelta(minutes=randint(6, 16))
        node = factory.make_Node(
            power_state_queried=power_state_queried, **kwargs
        )
        return node

    def test_raises_NoSuchCluster_if_rack_doesnt_exist(self):
        self.assertRaises(
            NoSuchCluster,
            list_cluster_nodes_power_parameters,
            factory.make_name("system_id"),
        )

    def test_returns_only_accessible_nodes(self):
        rack = factory.make_RackController()
        # Accessible nodes.
        node_ids = [
            self.make_Node(bmc_connected_to=rack).system_id for _ in range(3)
        ]
        # Inaccessible nodes.
        for _ in range(3):
            node = self.make_Node(bmc_connected_to=rack)
            node.bmc = None
            node.save()

        power_parameters = list_cluster_nodes_power_parameters(rack.system_id)
        system_ids = [params["system_id"] for params in power_parameters]
        self.assertCountEqual(node_ids, system_ids)

    def test_returns_unchecked_nodes_first(self):
        rack = factory.make_RackController()
        datetime_10_minutes_ago = now() - timedelta(minutes=10)
        nodes = [
            self.make_Node(
                bmc_connected_to=rack,
                power_state_queried=datetime_10_minutes_ago,
            )
            for _ in range(5)
        ]
        node_unchecked = random.choice(nodes)
        node_unchecked.power_state_queried = None
        node_unchecked.save()

        power_parameters = list_cluster_nodes_power_parameters(rack.system_id)
        system_ids = [params["system_id"] for params in power_parameters]

        # The unchecked node is always the first out.
        self.assertEqual(node_unchecked.system_id, system_ids[0])

    def test_excludes_recently_checked_nodes(self):
        rack = factory.make_RackController()

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

        self.assertCountEqual(
            {node_unchecked.system_id, node_checked_long_ago.system_id},
            system_ids,
        )

    def test_excludes_broken_nodes(self):
        rack = factory.make_RackController()
        node_queryable = self.make_Node(bmc_connected_to=rack)

        self.make_Node(status=NODE_STATUS.BROKEN, bmc_connected_to=rack)
        self.make_Node(
            status=NODE_STATUS.BROKEN,
            power_state_queried=(now() - timedelta(minutes=10)),
            bmc_connected_to=rack,
        )

        power_parameters = list_cluster_nodes_power_parameters(rack.system_id)
        system_ids = [params["system_id"] for params in power_parameters]

        self.assertEqual([node_queryable.system_id], system_ids)

    def test_excludes_no_power_type(self):
        rack = factory.make_RackController()
        node_queryable = self.make_Node(bmc_connected_to=rack)

        factory.make_Device(power_type=None)
        factory.make_Device(power_type=None)
        factory.make_Device(
            power_type=None,
            power_state_queried=(now() - timedelta(minutes=10)),
        )

        power_parameters = list_cluster_nodes_power_parameters(rack.system_id)
        system_ids = [params["system_id"] for params in power_parameters]

        self.assertEqual([node_queryable.system_id], system_ids)

    def test_returns_checked_nodes_in_last_checked_order(self):
        rack = factory.make_RackController()
        nodes = [self.make_Node(bmc_connected_to=rack) for _ in range(5)]

        power_parameters = list_cluster_nodes_power_parameters(rack.system_id)
        system_ids = [params["system_id"] for params in power_parameters]

        # Checked nodes are always sorted from least recently checked to most.
        node_sort_key = attrgetter("power_state_queried", "system_id")
        nodes_in_order = sorted(nodes, key=node_sort_key)
        self.assertEqual(
            [node.system_id for node in nodes_in_order], system_ids
        )

    def test_returns_at_most_60kiB_of_JSON(self):
        # Configure the rack controller subnet to be very large so it
        # can hold that many BMC connected to the interface for the rack
        # controller.
        rack = factory.make_RackController()
        rack_interface = rack.get_boot_interface()
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv6_network(slash=8))
        )
        factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=rack_interface,
        )

        # Ensure that there are at least 64kiB of power parameters (when
        # converted to JSON) in the database.
        example_parameters = {"key%d" % i: "value%d" % i for i in range(250)}
        remaining = 2**16
        while remaining > 0:
            node = self.make_Node(
                bmc_connected_to=rack, power_parameters=example_parameters
            )
            remaining -= len(json.dumps(node.get_effective_power_parameters()))

        nodes = list_cluster_nodes_power_parameters(
            rack.system_id, limit=None
        )  # Remove numeric limit.

        # The total size of the JSON is less than 60kiB, but only a bit.
        nodes_json = map(json.dumps, nodes)
        nodes_json_lengths = map(len, nodes_json)
        nodes_json_length = sum(nodes_json_lengths)
        expected_maximum = 60 * (2**10)  # 60kiB
        self.expectThat(nodes_json_length, LessThan(expected_maximum + 1))
        expected_minimum = 50 * (2**10)  # 50kiB
        self.expectThat(nodes_json_length, GreaterThan(expected_minimum - 1))

    def test_limited_to_10_nodes_at_a_time_by_default(self):
        # Configure the rack controller subnet to be large enough.
        rack = factory.make_RackController()
        rack_interface = rack.get_boot_interface()
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv6_network(slash=8))
        )
        factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=rack_interface,
        )

        # Create at least 11 nodes connected to the rack.
        for _ in range(11):
            self.make_Node(bmc_connected_to=rack)

        # Only 10 nodes' power parameters are returned.
        self.assertThat(
            list_cluster_nodes_power_parameters(rack.system_id), HasLength(10)
        )


class TestUpdateNodePowerState(MAASServerTestCase):
    def test_raises_NoSuchNode_if_node_doesnt_exist(self):
        self.assertRaises(
            NoSuchNode,
            update_node_power_state,
            factory.make_name("system_id"),
            factory.make_name("power_state"),
        )

    def test_updates_node_power_state(self):
        node = factory.make_Node(power_state=POWER_STATE.OFF)
        update_node_power_state(node.system_id, POWER_STATE.ON)
        self.assertEqual(reload_object(node).power_state, POWER_STATE.ON)


class TestGetControllerType(MAASServerTestCase):
    """Tests for `get_controller_type`."""

    def test_raises_NoSuchNode_if_node_doesnt_exist(self):
        self.assertRaises(
            NoSuchNode, get_controller_type, factory.make_name("system_id")
        )


class TestGetControllerType_Scenarios(MAASServerTestCase):
    """Scenario tests for `get_controller_type`."""

    scenarios = (
        (
            "rack",
            dict(
                node_type=NODE_TYPE.RACK_CONTROLLER,
                is_region=False,
                is_rack=True,
            ),
        ),
        (
            "region",
            dict(
                node_type=NODE_TYPE.REGION_CONTROLLER,
                is_region=True,
                is_rack=False,
            ),
        ),
        (
            "region+rack",
            dict(
                node_type=NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                is_region=True,
                is_rack=True,
            ),
        ),
        (
            "machine",
            dict(node_type=NODE_TYPE.MACHINE, is_region=False, is_rack=False),
        ),
    )

    def test_returns_node_type(self):
        node = factory.make_Node(node_type=self.node_type)
        self.assertEqual(
            {"is_region": self.is_region, "is_rack": self.is_rack},
            get_controller_type(node.system_id),
        )


class TestGetTimeConfiguration(MAASServerTestCase):
    """Tests for `get_controller_type`."""

    def test_raises_NoSuchNode_if_node_doesnt_exist(self):
        self.assertRaises(
            NoSuchNode, get_time_configuration, factory.make_name("system_id")
        )


class TestGetTimeConfiguration_Scenarios(MAASServerTestCase):
    """Scenario tests for `get_time_configuration`."""

    scenarios = (
        ("rack", dict(node_type=NODE_TYPE.RACK_CONTROLLER)),
        ("region", dict(node_type=NODE_TYPE.REGION_CONTROLLER)),
        ("region+rack", dict(node_type=NODE_TYPE.REGION_AND_RACK_CONTROLLER)),
        ("machine", dict(node_type=NODE_TYPE.MACHINE)),
        ("device", dict(node_type=NODE_TYPE.DEVICE)),
    )

    def test_calls_through_to_ntp_module_returns_servers_and_peers(self):
        get_servers_for = self.patch(ntp, "get_servers_for")
        get_servers_for.return_value = frozenset({sentinel.server})
        get_peers_for = self.patch(ntp, "get_peers_for")
        get_peers_for.return_value = frozenset({sentinel.peer})
        node = factory.make_Node(node_type=self.node_type)
        self.assertThat(
            get_time_configuration(node.system_id),
            Equals(
                {
                    "servers": frozenset({sentinel.server}),
                    "peers": frozenset({sentinel.peer}),
                }
            ),
        )
