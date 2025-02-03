import json
import random
from unittest.mock import call

from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_TYPE,
)
from maasserver.models import Event, EventType
from maasserver.models.config import Config
from maasserver.models.fabric import Fabric
from maasserver.models.interface import (
    BondInterface,
    BridgeInterface,
    Interface,
    PhysicalInterface,
    VLANInterface,
)
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.subnet import Subnet
from maasserver.models.vlan import VLAN
from maasserver.testing.commissioning import (
    FakeCommissioningData,
    LXDAddress,
    LXDNetworkCard,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import get_one, post_commit_hooks, reload_object
from maastesting.testcase import MAASTestCase
from metadataserver.builtin_scripts import hooks
from metadataserver.builtin_scripts import network as network_module
from metadataserver.builtin_scripts.network import (
    _hardware_sync_network_device_notify,
    get_interface_dependencies,
    update_interface,
    update_node_interfaces,
)
from provisioningserver.events import EVENT_DETAILS, EVENT_TYPES
from provisioningserver.refresh.node_info_scripts import (
    COMMISSIONING_OUTPUT_NAME,
)


class UpdateInterfacesMixin:
    def create_empty_controller(self, **kwargs):
        node_type = random.choice(
            [
                NODE_TYPE.REGION_CONTROLLER,
                NODE_TYPE.RACK_CONTROLLER,
                NODE_TYPE.REGION_AND_RACK_CONTROLLER,
            ]
        )
        return factory.make_Node(
            node_type=node_type, status=NODE_STATUS.DEPLOYED, **kwargs
        ).as_self()

    def update_interfaces(
        self,
        node,
        data,
        passes=None,
    ):
        with post_commit_hooks:
            data = data.render(include_extra=node.is_controller)
            # update_node_interfaces() is idempotent, so it doesn't matter
            # if it's called once or twice.
            if passes is None:
                passes = random.randint(1, 2)
            for _ in range(passes):
                hooks.process_lxd_results(node, json.dumps(data).encode(), 0)
            return passes


class TestUpdateInterfaces(MAASServerTestCase, UpdateInterfacesMixin):
    def setUp(self):
        super().setUp()
        self.patch(hooks, "start_workflow")

    def test_create_interface_default_numanode(self):
        node = factory.make_Machine()
        data = FakeCommissioningData()
        data.create_physical_network_without_nic("eth0")
        self.update_interfaces(node, data)
        eth0 = node.current_config.interface_set.get(name="eth0")
        self.assertEqual(eth0.numa_node, node.default_numanode)

    def test_dont_create_default_vlan_for_missing_links_deployed_machines(
        self,
    ):
        node = factory.make_Machine(status=NODE_STATUS.DEPLOYED)
        data = FakeCommissioningData()
        data_eth0 = data.create_physical_network(
            "eth0",
            mac_address="11:11:11:11:11:11",
        )
        data_eth0.state = "up"
        self.update_interfaces(node, data)
        eth0 = PhysicalInterface.objects.get(
            name="eth0", node_config=node.current_config
        )
        self.assertIsNone(eth0.vlan)

    def test_vlan_interfaces_with_known_link_deployed_machine(self):
        node = factory.make_Machine(status=NODE_STATUS.DEPLOYED)
        vlan123 = factory.make_VLAN(vid=123)
        vlan456 = factory.make_VLAN(vid=456, fabric=vlan123.fabric)
        factory.make_Subnet(cidr="10.10.10.0/24", vlan=vlan123)
        factory.make_Subnet(cidr="10.10.20.0/24", vlan=vlan456)
        data = FakeCommissioningData()
        data_eth0 = data.create_physical_network(
            "eth0",
            mac_address="11:11:11:11:11:11",
        )
        data_eth0.state = "up"
        vlan_network123 = data.create_vlan_network(
            "eth0.123", parent=data_eth0, vid=123
        )
        vlan_network123.addresses = [LXDAddress("10.10.10.10", 24)]
        vlan_network456 = data.create_vlan_network(
            "eth0.456", parent=data_eth0, vid=456
        )
        vlan_network456.addresses = [LXDAddress("10.10.20.10", 24)]
        self.update_interfaces(node, data)
        eth0 = PhysicalInterface.objects.get(
            name="eth0", node_config=node.current_config
        )
        eth0_vlan123 = Interface.objects.get(
            name="eth0.123", node_config=node.current_config
        )
        eth0_vlan456 = Interface.objects.get(
            name="eth0.456", node_config=node.current_config
        )
        self.assertEqual(INTERFACE_TYPE.VLAN, eth0_vlan123.type)
        self.assertEqual(123, eth0_vlan123.vlan.vid)
        self.assertEqual(INTERFACE_TYPE.VLAN, eth0_vlan456.type)
        self.assertEqual(456, eth0_vlan456.vlan.vid)
        self.assertEqual(
            eth0_vlan123.vlan.fabric_id, eth0_vlan456.vlan.fabric_id
        )
        self.assertIsNotNone(eth0.vlan_id)
        self.assertNotIn(
            eth0.vlan_id, [eth0_vlan456.vlan_id, eth0_vlan123.vlan_id]
        )
        self.assertEqual(eth0.vlan.fabric_id, eth0_vlan123.vlan.fabric_id)
        self.assertEqual(eth0.vlan.fabric_id, eth0_vlan456.vlan.fabric_id)

    def test_vlan_interfaces_with_new_known_link_deployed_machine(self):
        node = factory.make_Machine(status=NODE_STATUS.DEPLOYED)
        vlan456 = factory.make_VLAN(vid=456)
        factory.make_Subnet(cidr="10.10.20.0/24", vlan=vlan456)
        data = FakeCommissioningData()
        data_eth0 = data.create_physical_network(
            "eth0",
            mac_address="11:11:11:11:11:11",
        )
        data_eth0.state = "up"
        vlan_network123 = data.create_vlan_network(
            "eth0.123", parent=data_eth0, vid=123
        )
        vlan_network123.addresses = [LXDAddress("10.10.10.10", 24)]
        vlan_network456 = data.create_vlan_network(
            "eth0.456", parent=data_eth0, vid=456
        )
        vlan_network456.addresses = [LXDAddress("10.10.20.10", 24)]
        self.update_interfaces(node, data)
        eth0 = PhysicalInterface.objects.get(
            name="eth0", node_config=node.current_config
        )
        eth0_vlan123 = Interface.objects.get(
            name="eth0.123", node_config=node.current_config
        )
        eth0_vlan456 = Interface.objects.get(
            name="eth0.456", node_config=node.current_config
        )
        self.assertEqual(INTERFACE_TYPE.VLAN, eth0_vlan123.type)
        self.assertEqual(123, eth0_vlan123.vlan.vid)
        self.assertEqual(INTERFACE_TYPE.VLAN, eth0_vlan456.type)
        self.assertEqual(456, eth0_vlan456.vlan.vid)
        self.assertEqual(
            eth0_vlan123.vlan.fabric_id, eth0_vlan456.vlan.fabric_id
        )
        self.assertIsNotNone(eth0.vlan_id)
        self.assertNotIn(
            eth0.vlan_id, [eth0_vlan456.vlan_id, eth0_vlan123.vlan_id]
        )
        self.assertEqual(eth0.vlan.fabric_id, eth0_vlan123.vlan.fabric_id)
        self.assertEqual(eth0.vlan.fabric_id, eth0_vlan456.vlan.fabric_id)

    def test_vlan_interfaces_with_new_unknown_link_deployed_machine(self):
        node = factory.make_Machine(status=NODE_STATUS.DEPLOYED)
        vlan123 = factory.make_VLAN(vid=123)
        factory.make_Subnet(cidr="10.10.10.0/24", vlan=vlan123)
        data = FakeCommissioningData()
        data_eth0 = data.create_physical_network(
            "eth0",
            mac_address="11:11:11:11:11:11",
        )
        data_eth0.state = "up"
        vlan_network123 = data.create_vlan_network(
            "eth0.123", parent=data_eth0, vid=123
        )
        vlan_network123.addresses = [LXDAddress("10.10.10.10", 24)]
        vlan_network456 = data.create_vlan_network(
            "eth0.456", parent=data_eth0, vid=456
        )
        vlan_network456.addresses = [LXDAddress("10.10.20.10", 24)]
        self.update_interfaces(node, data)
        eth0 = PhysicalInterface.objects.get(
            name="eth0", node_config=node.current_config
        )
        eth0_vlan123 = Interface.objects.get(
            name="eth0.123", node_config=node.current_config
        )
        eth0_vlan456 = Interface.objects.get(
            name="eth0.456", node_config=node.current_config
        )
        self.assertEqual(INTERFACE_TYPE.VLAN, eth0_vlan123.type)
        self.assertEqual(123, eth0_vlan123.vlan.vid)
        self.assertEqual(INTERFACE_TYPE.VLAN, eth0_vlan456.type)
        self.assertEqual(456, eth0_vlan456.vlan.vid)
        self.assertEqual(
            eth0_vlan123.vlan.fabric_id, eth0_vlan456.vlan.fabric_id
        )
        self.assertIsNotNone(eth0.vlan_id)
        self.assertNotIn(
            eth0.vlan_id, [eth0_vlan456.vlan_id, eth0_vlan123.vlan_id]
        )
        self.assertEqual(eth0.vlan.fabric_id, eth0_vlan123.vlan.fabric_id)
        self.assertEqual(eth0.vlan.fabric_id, eth0_vlan456.vlan.fabric_id)

    def test_vlan_interfaces_with_unknown_link_deployed_machine(self):
        node = factory.make_Machine(status=NODE_STATUS.DEPLOYED)
        data = FakeCommissioningData()
        data_eth0 = data.create_physical_network(
            "eth0",
            mac_address="11:11:11:11:11:11",
        )
        data_eth0.state = "up"
        vlan_network123 = data.create_vlan_network(
            "eth0.123", parent=data_eth0, vid=123
        )
        vlan_network123.addresses = [LXDAddress("10.10.10.10", 24)]
        vlan_network456 = data.create_vlan_network(
            "eth0.456", parent=data_eth0, vid=456
        )
        vlan_network456.addresses = [LXDAddress("10.10.20.10", 24)]
        self.update_interfaces(node, data)
        eth0 = PhysicalInterface.objects.get(
            name="eth0", node_config=node.current_config
        )
        eth0_vlan123 = Interface.objects.get(
            name="eth0.123", node_config=node.current_config
        )
        eth0_vlan456 = Interface.objects.get(
            name="eth0.456", node_config=node.current_config
        )
        self.assertEqual(INTERFACE_TYPE.VLAN, eth0_vlan123.type)
        self.assertEqual(123, eth0_vlan123.vlan.vid)
        self.assertEqual(INTERFACE_TYPE.VLAN, eth0_vlan456.type)
        self.assertEqual(456, eth0_vlan456.vlan.vid)
        self.assertEqual(
            eth0_vlan123.vlan.fabric_id, eth0_vlan456.vlan.fabric_id
        )
        self.assertIsNotNone(eth0.vlan_id)
        self.assertNotIn(
            eth0.vlan_id, [eth0_vlan456.vlan_id, eth0_vlan123.vlan_id]
        )
        self.assertEqual(eth0.vlan.fabric_id, eth0_vlan123.vlan.fabric_id)
        self.assertEqual(eth0.vlan.fabric_id, eth0_vlan456.vlan.fabric_id)

    def test_dont_create_default_vlan_if_disabled(self):
        Config.objects.set_config(name="auto_vlan_creation", value=False)
        node = factory.make_Machine(status=NODE_STATUS.NEW)
        data = FakeCommissioningData()
        data_eth0 = data.create_physical_network(
            "eth0",
            mac_address="11:11:11:11:11:11",
        )
        data_eth0.state = "up"
        self.update_interfaces(node, data)
        eth0 = PhysicalInterface.objects.get(
            name="eth0", node_config=node.current_config
        )
        self.assertIsNone(eth0.vlan)

    def test_all_new_physical_interfaces_no_links(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        eth0 = data.create_physical_network(
            "eth0",
            mac_address="11:11:11:11:11:11",
        )
        eth0.state = "up"
        eth1 = data.create_physical_network(
            "eth1",
            mac_address="22:22:22:22:22:22",
        )
        eth1.state = "down"

        self.update_interfaces(controller, data)

        eth0 = PhysicalInterface.objects.get(
            name="eth0", node_config=controller.current_config
        )
        self.assertEqual("11:11:11:11:11:11", eth0.mac_address)
        self.assertTrue(eth0.enabled)
        self.assertTrue(eth0.link_connected)
        self.assertIsNone(eth0.vlan)
        self.assertEqual([], list(eth0.parents.all()))
        eth1 = PhysicalInterface.objects.get(
            name="eth1", node_config=controller.current_config
        )
        self.assertEqual("22:22:22:22:22:22", eth1.mac_address)
        self.assertTrue(eth1.enabled)
        self.assertFalse(eth1.link_connected)
        self.assertIsNone(eth1.vlan)
        self.assertEqual([], list(eth1.parents.all()))

    def test_vlans_with_alternate_naming_conventions(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        data.create_vlan_network("vlan0100", parent=eth0_network)
        data.create_vlan_network("vlan101", parent=eth0_network)
        data.create_vlan_network("eth0.0102", parent=eth0_network)

        self.update_interfaces(controller, data)

        eth0 = PhysicalInterface.objects.get(
            name="eth0", node_config=controller.current_config
        )
        self.assertEqual(eth0_network.hwaddr, eth0.mac_address)
        self.assertTrue(eth0.enabled)
        self.assertTrue(eth0.link_connected)
        self.assertEqual([], list(eth0.parents.all()))
        vlan0100 = Interface.objects.get(
            name="vlan0100", node_config=controller.current_config
        )
        self.assertEqual(INTERFACE_TYPE.VLAN, vlan0100.type)
        # XXX: For some reason MAAS forces VLAN interfaces to have the
        # same MAC as the parent. But in reality, VLAN interfaces may
        # have different MAC addresses.
        self.assertEqual(eth0_network.hwaddr, vlan0100.mac_address)
        self.assertTrue(vlan0100.enabled)
        self.assertTrue(vlan0100.link_connected)
        self.assertEqual([eth0], list(vlan0100.parents.all()))
        vlan101 = Interface.objects.get(
            name="vlan101", node_config=controller.current_config
        )
        self.assertEqual(INTERFACE_TYPE.VLAN, vlan101.type)
        # XXX: For some reason MAAS forces VLAN interfaces to have the
        # same MAC as the parent. But in reality, VLAN interfaces may
        # have different MAC addresses.
        self.assertEqual(eth0_network.hwaddr, vlan101.mac_address)
        self.assertTrue(vlan101.enabled)
        self.assertTrue(vlan101.link_connected)
        self.assertEqual([eth0], list(vlan101.parents.all()))
        eth0_0102 = Interface.objects.get(
            name="eth0.0102", node_config=controller.current_config
        )
        self.assertEqual(INTERFACE_TYPE.VLAN, eth0_0102.type)
        # XXX: For some reason MAAS forces VLAN interfaces to have the
        # same MAC as the parent. But in reality, VLAN interfaces may
        # have different MAC addresses.
        self.assertEqual(eth0_network.hwaddr, eth0_0102.mac_address)
        self.assertTrue(eth0_0102.enabled)
        self.assertTrue(eth0_0102.link_connected)
        self.assertEqual([eth0], list(eth0_0102.parents.all()))

    def test_vlans_with_alternate_naming_conventions_vm_host(self):
        host = factory.make_Machine()
        factory.make_Pod(host=host)
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        data.create_vlan_network("vlan0100", parent=eth0_network, vid=1)
        data.create_vlan_network("vlan101", parent=eth0_network, vid=2)
        data.create_vlan_network("eth0.0102", parent=eth0_network, vid=3)

        self.update_interfaces(host, data)

        interface_names = VLANInterface.objects.filter(
            node_config=host.current_config
        ).values_list("name", flat=True)
        self.assertCountEqual(
            ["eth0.0102", "vlan0100", "vlan101"], interface_names
        )

    def test_vlans_with_alternate_naming_conventions_host(self):
        host = factory.make_Machine()
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        data.create_vlan_network("vlan0100", parent=eth0_network, vid=1)
        data.create_vlan_network("vlan101", parent=eth0_network, vid=2)
        data.create_vlan_network("eth0.0102", parent=eth0_network, vid=3)

        self.update_interfaces(host, data)

        interface_names = VLANInterface.objects.filter(
            node_config=host.current_config
        ).values_list("name", flat=True)
        self.assertCountEqual(
            ["eth0.0102", "vlan0100", "vlan101"], interface_names
        )

    def test_vlan_interface_moved_vlan(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        data.create_vlan_network("eth0.100", parent=eth0_network, vid=100)

        self.update_interfaces(controller, data)

        eth0 = PhysicalInterface.objects.get(
            name="eth0", node_config=controller.current_config
        )
        eth0_100 = VLANInterface.objects.get(
            name="eth0.100", node_config=controller.current_config
        )
        eth0_fabric_id = eth0.vlan.fabric_id
        self.assertEqual(eth0_fabric_id, eth0_100.vlan.fabric_id)
        self.assertCountEqual(
            [0, 100],
            [
                vlan.vid
                for vlan in VLAN.objects.filter(fabric_id=eth0_fabric_id)
            ],
        )

        # Simulate someone moving the VLAN of the VLAN interface, but
        # before the parent VLAN is moved, update_interfaces() is
        # called. This may happen, since our UI and API don't allow you
        # to move multiple VLANs at a time.
        new_fabric = factory.make_Fabric()
        eth0_100.vlan.fabric = new_fabric
        eth0_100.vlan.save()
        self.update_interfaces(controller, data)

        # We're now in a situation where the main interface and its VLAN
        # interface have different fabrics. It's not a valid situation,
        # but we have to allow it so that people can use our API to move
        # multiple VLANs to a different fabric.
        eth0 = PhysicalInterface.objects.get(
            name="eth0", node_config=controller.current_config
        )
        eth0_100 = VLANInterface.objects.get(
            name="eth0.100", node_config=controller.current_config
        )
        self.assertEqual(eth0_fabric_id, eth0.vlan.fabric_id)
        self.assertEqual(new_fabric.id, eth0_100.vlan.fabric_id)
        self.assertCountEqual(
            [0, 100],
            list(
                VLAN.objects.filter(fabric=new_fabric).values_list(
                    "vid", flat=True
                )
            ),
        )
        self.assertCountEqual(
            [0],
            list(
                VLAN.objects.filter(fabric_id=eth0_fabric_id).values_list(
                    "vid", flat=True
                )
            ),
        )

    def test_sets_discovery_parameters(self):
        controller = self.create_empty_controller()
        eth0_mac = factory.make_mac_address()
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=eth0_mac
        )
        data.create_vlan_network(
            "eth0.100", vid=100, parent=eth0_network, mac_address=eth0_mac
        )
        eth1_network = data.create_physical_network("eth1")
        eth1_network.state = "down"

        self.update_interfaces(controller, data)

        eth0 = Interface.objects.get(
            name="eth0", node_config=controller.current_config
        )
        self.assertTrue(eth0.neighbour_discovery_state)
        self.assertTrue(eth0.mdns_discovery_state)
        eth0_vlan = Interface.objects.get(
            name="eth0.100", node_config=controller.current_config
        )
        self.assertFalse(eth0_vlan.neighbour_discovery_state)
        self.assertTrue(eth0_vlan.mdns_discovery_state)
        eth1 = Interface.objects.get(
            name="eth1", node_config=controller.current_config
        )
        self.assertFalse(eth1.neighbour_discovery_state)
        self.assertTrue(eth1.mdns_discovery_state)

    def test_clears_discovery_parameters(self):
        controller = self.create_empty_controller()
        eth0_mac = factory.make_mac_address()
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=eth0_mac
        )
        vlan_network = data.create_vlan_network(
            "eth0.100", vid=100, parent=eth0_network, mac_address=eth0_mac
        )
        self.update_interfaces(controller, data)

        # Disable the interfaces so that we can make sure neighbour discovery
        # is properly disabled on update.
        eth0_network.state = "down"
        vlan_network.state = "down"

        self.update_interfaces(controller, data)

        eth0 = Interface.objects.get(
            name="eth0", node_config=controller.current_config
        )
        self.assertFalse(eth0.neighbour_discovery_state)
        self.assertTrue(eth0.mdns_discovery_state)
        eth0_vlan = Interface.objects.get(
            name="eth0.100", node_config=controller.current_config
        )
        self.assertFalse(eth0_vlan.neighbour_discovery_state)
        self.assertTrue(eth0_vlan.mdns_discovery_state)

    def test_link_alias_controller(self):
        controller = self.create_empty_controller()
        network = factory.make_ip4_or_6_network()
        ip1 = factory.pick_ip_in_network(network)
        ip2 = factory.pick_ip_in_network(network, but_not=[ip1])
        data = FakeCommissioningData()
        eth0 = data.create_physical_network(
            "eth0",
            mac_address="11:11:11:11:11:11",
        )
        eth0.addresses = [
            LXDAddress(str(ip1), network.prefixlen),
            LXDAddress(str(ip2), network.prefixlen),
        ]
        self.update_interfaces(controller, data)
        eth0 = Interface.objects.get(
            name="eth0", node_config=controller.current_config
        )
        eth0_addresses = list(eth0.ip_addresses.all())
        subnet = Subnet.objects.get(cidr=str(network.cidr))
        self.assertCountEqual(
            [
                (IPADDRESS_TYPE.STICKY, ip1, subnet),
                (IPADDRESS_TYPE.STICKY, ip2, subnet),
            ],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

    def test_link_alias_commissioning(self):
        machine = factory.make_Machine(status=NODE_STATUS.COMMISSIONING)
        network = factory.make_ip4_or_6_network()
        ip1 = factory.pick_ip_in_network(network)
        ip2 = factory.pick_ip_in_network(network, but_not=[ip1])
        data = FakeCommissioningData()
        eth0 = data.create_physical_network(
            "eth0",
            mac_address="11:11:11:11:11:11",
        )
        eth0.addresses = [
            LXDAddress(str(ip1), network.prefixlen),
            LXDAddress(str(ip2), network.prefixlen),
        ]
        self.update_interfaces(machine, data)
        eth0 = Interface.objects.get(
            name="eth0", node_config=machine.current_config
        )
        eth0_addresses = list(eth0.ip_addresses.all())
        subnet = Subnet.objects.get(cidr=str(network.cidr))
        self.assertCountEqual(
            [
                (IPADDRESS_TYPE.AUTO, None, subnet),
                (IPADDRESS_TYPE.DISCOVERED, ip1, subnet),
                (IPADDRESS_TYPE.DISCOVERED, ip2, subnet),
            ],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

    def test_link_ip_with_full_netmask_wider_subnet(self):
        controller = self.create_empty_controller()
        net4 = factory.make_ipv4_network(slash=24)
        net6 = factory.make_ipv6_network(slash=64)
        subnet4 = factory.make_Subnet(cidr=str(net4.cidr))
        subnet6 = factory.make_Subnet(cidr=str(net6.cidr))
        # pick IPs in each network
        ip4 = net4[10]
        ip6 = net6[10]
        data = FakeCommissioningData()
        eth0 = data.create_physical_network(
            "eth0",
            mac_address="11:11:11:11:11:11",
        )
        # record the addresses with a full netmask
        eth0.addresses = [
            LXDAddress(str(ip4), 32),
            LXDAddress(str(ip6), 128),
        ]
        self.update_interfaces(controller, data)
        eth0 = Interface.objects.get(
            name="eth0", node_config=controller.current_config
        )
        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertCountEqual(
            [
                (IPADDRESS_TYPE.STICKY, str(ip4), subnet4),
                (IPADDRESS_TYPE.STICKY, str(ip6), subnet6),
            ],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

    def test_link_ip_with_full_netmask_no_wider_subnet(self):
        controller = self.create_empty_controller()
        net4 = factory.make_ipv4_network(slash=24)
        net6 = factory.make_ipv6_network(slash=64)
        # pick IPs in each network
        ip4 = net4[10]
        ip6 = net6[10]
        data = FakeCommissioningData()
        eth0 = data.create_physical_network(
            "eth0",
            mac_address="11:11:11:11:11:11",
        )
        # record the addresses with a full netmask
        eth0.addresses = [
            LXDAddress(str(ip4), 32),
            LXDAddress(str(ip6), 128),
        ]
        self.update_interfaces(controller, data)
        eth0 = Interface.objects.get(
            name="eth0", node_config=controller.current_config
        )
        eth0_addresses = list(eth0.ip_addresses.all())
        # subnets with full netmask are created
        subnet4 = Subnet.objects.get(cidr=f"{ip4}/32")
        subnet6 = Subnet.objects.get(cidr=f"{ip6}/128")
        self.assertCountEqual(
            [
                (IPADDRESS_TYPE.STICKY, str(ip4), subnet4),
                (IPADDRESS_TYPE.STICKY, str(ip6), subnet6),
            ],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

    def test_new_physical_with_new_subnet_link(self):
        controller = self.create_empty_controller()
        network = factory.make_ip4_or_6_network()
        ip = factory.pick_ip_in_network(network)
        gateway_ip = factory.pick_ip_in_network(network, but_not=[ip])
        data = FakeCommissioningData()
        eth0 = data.create_physical_network(
            "eth0",
            mac_address="11:11:11:11:11:11",
        )
        eth0.addresses = [LXDAddress(str(ip), network.prefixlen)]
        data.address_annotations[str(ip)] = {"gateway": str(gateway_ip)}
        self.update_interfaces(controller, data)
        eth0 = Interface.objects.get(
            name="eth0", node_config=controller.current_config
        )
        default_vlan = Fabric.objects.get_default_fabric().get_default_vlan()
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual("11:11:11:11:11:11", eth0.mac_address)
        self.assertEqual(default_vlan, eth0.vlan)
        self.assertTrue(eth0.enabled)
        subnet = Subnet.objects.get(cidr=str(network.cidr))
        self.assertEqual(str(network.cidr), subnet.name)
        self.assertEqual(default_vlan, subnet.vlan)
        self.assertEqual(gateway_ip, subnet.gateway_ip)
        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertCountEqual(
            [(IPADDRESS_TYPE.STICKY, ip, subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

    def test_new_physical_with_local_link(self):
        controller = self.create_empty_controller()
        network = factory.make_ip4_or_6_network()
        ip = factory.pick_ip_in_network(network)
        data = FakeCommissioningData()
        eth0 = data.create_physical_network(
            "eth0",
            mac_address="11:11:11:11:11:11",
        )
        eth0.addresses = [
            LXDAddress(str(ip), network.prefixlen, scope="local"),
        ]

        self.update_interfaces(controller, data)

        eth0 = Interface.objects.get(
            name="eth0", node_config=controller.current_config
        )

        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual("11:11:11:11:11:11", eth0.mac_address)
        self.assertIsNone(eth0.vlan)
        self.assertTrue(eth0.enabled)

        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertEqual(
            [],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

    def test_new_physical_with_dhcp_link(self):
        controller = self.create_empty_controller()
        network = factory.make_ip4_or_6_network()
        ip = factory.pick_ip_in_network(network)
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        eth0_network.addresses = [LXDAddress(str(ip), network.prefixlen)]
        data.address_annotations[str(ip)] = {"mode": "dhcp"}

        self.update_interfaces(controller, data)

        eth0 = Interface.objects.get(
            name="eth0", node_config=controller.current_config
        )
        default_vlan = Fabric.objects.get_default_fabric().get_default_vlan()
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(eth0_network.hwaddr, eth0.mac_address)
        self.assertEqual(default_vlan, eth0.vlan)
        dhcp_addresses = list(
            eth0.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.DHCP)
        )
        self.assertEqual([None], [address.ip for address in dhcp_addresses])
        subnet = Subnet.objects.get(cidr=str(network.cidr))
        self.assertEqual(str(network.cidr), subnet.name)
        self.assertEqual(default_vlan, subnet.vlan)
        discovered_addresses = list(
            eth0.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.DISCOVERED)
        )
        self.assertEqual(
            [(ip, subnet)],
            [(address.ip, address.subnet) for address in discovered_addresses],
        )

    def test_new_physical_with_multiple_dhcp_link(self):
        controller = self.create_empty_controller()
        network1 = factory.make_ip4_or_6_network()
        ip1 = str(factory.pick_ip_in_network(network1))
        network2 = factory.make_ip4_or_6_network()
        ip2 = str(factory.pick_ip_in_network(network2))
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        eth0_network.addresses = [
            LXDAddress(ip1, network1.prefixlen),
            LXDAddress(ip2, network2.prefixlen),
        ]
        data.address_annotations[ip1] = {"mode": "dhcp"}
        data.address_annotations[ip2] = {"mode": "dhcp"}

        self.update_interfaces(controller, data)

        eth0 = Interface.objects.get(
            name="eth0", node_config=controller.current_config
        )
        default_vlan = Fabric.objects.get_default_fabric().get_default_vlan()
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(eth0_network.hwaddr, eth0.mac_address)
        self.assertEqual(default_vlan, eth0.vlan)
        dhcp_addresses = list(
            eth0.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.DHCP)
        )
        self.assertEqual(
            [None, None], [address.ip for address in dhcp_addresses]
        )
        discovered_addresses = list(
            eth0.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.DISCOVERED)
        )
        self.assertCountEqual(
            [ip1, ip2],
            [address.ip for address in discovered_addresses],
        )

    def test_new_physical_with_resource_info(self):
        controller = self.create_empty_controller(with_empty_script_sets=True)
        data = FakeCommissioningData()
        card = data.create_network_card()
        card.vendor = factory.make_name("vendor")
        card.product = factory.make_name("product")
        card.firmware_version = factory.make_name("firmware_version")
        data.create_physical_network("eth0", card=card)

        self.update_interfaces(controller, data)
        eth0 = Interface.objects.get(
            name="eth0", node_config=controller.current_config
        )
        self.assertEqual(card.vendor, eth0.vendor)
        self.assertEqual(card.product, eth0.product)
        self.assertEqual(card.firmware_version, eth0.firmware_version)

    def test_new_physical_with_existing_subnet_link_with_gateway(self):
        controller = self.create_empty_controller()
        subnet = factory.make_Subnet()
        network = subnet.get_ipnetwork()
        gateway_ip = factory.pick_ip_in_network(network)
        subnet.gateway_ip = gateway_ip
        subnet.save()
        ip = str(factory.pick_ip_in_network(network, but_not=[gateway_ip]))
        diff_gateway_ip = str(
            factory.pick_ip_in_network(network, but_not=[gateway_ip, ip])
        )
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        eth0_network.addresses = [LXDAddress(ip, network.prefixlen)]
        data.address_annotations[ip] = {"gateway": diff_gateway_ip}

        self.update_interfaces(controller, data)

        eth0 = Interface.objects.get(
            name="eth0", node_config=controller.current_config
        )
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(eth0_network.hwaddr, eth0.mac_address)
        self.assertEqual(subnet.vlan, eth0.vlan)

        # Check that the gateway IP didn't change.
        self.assertEqual(gateway_ip, subnet.gateway_ip)
        [eth0_address] = list(eth0.ip_addresses.all())
        self.assertEqual(ip, eth0_address.ip)
        self.assertEqual(IPADDRESS_TYPE.STICKY, eth0_address.alloc_type)
        self.assertEqual(subnet, eth0_address.subnet)

    def test_new_physical_with_existing_subnet_link_without_gateway(self):
        controller = self.create_empty_controller()
        subnet = factory.make_Subnet()
        subnet.gateway_ip = None
        subnet.save()
        network = subnet.get_ipnetwork()
        gateway_ip = str(factory.pick_ip_in_network(network))
        ip = str(factory.pick_ip_in_network(network, but_not=[gateway_ip]))

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        eth0_network.addresses = [LXDAddress(ip, network.prefixlen)]
        data.address_annotations[ip] = {"gateway": gateway_ip}

        self.update_interfaces(controller, data)

        eth0 = Interface.objects.get(
            name="eth0", node_config=controller.current_config
        )
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(eth0_network.hwaddr, eth0.mac_address)
        self.assertEqual(subnet.vlan, eth0.vlan)

        subnet = reload_object(subnet)
        # Check that the gateway IP did get set.
        self.assertEqual(gateway_ip, subnet.gateway_ip)

        [eth0_address] = list(eth0.ip_addresses.all())
        self.assertEqual(ip, eth0_address.ip)
        self.assertEqual(IPADDRESS_TYPE.STICKY, eth0_address.alloc_type)
        self.assertEqual(subnet, eth0_address.subnet)

    def test_new_physical_with_multiple_subnets(self):
        controller = self.create_empty_controller()
        vlan = factory.make_VLAN()
        subnet1 = factory.make_Subnet(vlan=vlan)
        ip1 = str(factory.pick_ip_in_Subnet(subnet1))
        subnet2 = factory.make_Subnet(vlan=vlan)
        ip2 = str(factory.pick_ip_in_Subnet(subnet2))
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        eth0_network.addresses = [
            LXDAddress(ip1, subnet1.get_ipnetwork().prefixlen),
            LXDAddress(ip2, subnet2.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        eth0 = Interface.objects.get(
            name="eth0", node_config=controller.current_config
        )
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(eth0_network.hwaddr, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)

        eth0_addresses = list(eth0.ip_addresses.order_by("id"))
        self.assertCountEqual(
            [
                (IPADDRESS_TYPE.STICKY, ip1, subnet1),
                (IPADDRESS_TYPE.STICKY, ip2, subnet2),
            ],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

    def test_existing_physical_with_existing_static_link(self):
        controller = self.create_empty_controller()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = str(factory.pick_ip_in_Subnet(subnet))
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            node_config=controller.current_config,
            vlan=vlan,
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=ip,
            subnet=subnet,
            interface=interface,
        )

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        eth0_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        [eth0] = controller.current_config.interface_set.all()
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)

        eth0_addresses = list(interface.ip_addresses.all())
        self.assertCountEqual(
            [(IPADDRESS_TYPE.STICKY, ip, subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

    def test_existing_physical_with_existing_auto_link(self):
        controller = self.create_empty_controller()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=ip,
            subnet=subnet,
            interface=interface,
        )
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        eth0_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        [eth0] = controller.current_config.interface_set.all()
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)
        eth0_addresses = list(interface.ip_addresses.all())
        self.assertCountEqual(
            [(IPADDRESS_TYPE.STICKY, ip, subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

    def test_existing_physical_removes_old_links(self):
        controller = self.create_empty_controller()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=ip,
            subnet=subnet,
            interface=interface,
        )
        extra_ips = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.AUTO,
                subnet=subnet,
                interface=interface,
            )
            for _ in range(3)
        ]
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        eth0_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        [eth0] = controller.current_config.interface_set.all()
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)
        eth0_addresses = list(interface.ip_addresses.all())
        self.assertCountEqual(
            [(IPADDRESS_TYPE.STICKY, ip, subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

        for extra_ip in extra_ips:
            self.assertIsNone(reload_object(extra_ip))

    def test_existing_physical_removes_ip_links(self):
        controller = self.create_empty_controller()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=ip,
            subnet=subnet,
            interface=interface,
        )
        other_node_interface = factory.make_Interface()
        no_node_interface = factory.make_Interface(
            iftype=INTERFACE_TYPE.UNKNOWN
        )
        static_ip.interface_set.add(other_node_interface)
        static_ip.interface_set.add(no_node_interface)
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        eth0_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        [eth0] = controller.current_config.interface_set.all()
        static_ip = StaticIPAddress.objects.get(ip=str(ip))
        self.assertEqual([eth0], list(static_ip.interface_set.all()))

    def test_existing_physical_with_links_new_vlan_no_links(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=ip,
            subnet=subnet,
            interface=interface,
        )
        vid_on_fabric = random.randint(1, 4094)

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        eth0_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]
        data.create_vlan_network(
            f"eth0.{vid_on_fabric}", parent=eth0_network, vid=vid_on_fabric
        )

        self.update_interfaces(controller, data)

        self.assertEqual(2, controller.current_config.interface_set.count())
        eth0 = Interface.objects.get(
            node_config=controller.current_config, name="eth0"
        )
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)

        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertCountEqual(
            [(IPADDRESS_TYPE.STICKY, ip, subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

        created_vlan = VLAN.objects.get(fabric=fabric, vid=vid_on_fabric)
        vlan_interface = VLANInterface.objects.get(
            node_config=controller.current_config, vlan=created_vlan
        )
        self.assertEqual(f"eth0.{vid_on_fabric}", vlan_interface.name)
        self.assertTrue(vlan_interface.enabled)
        self.assertTrue(created_vlan, vlan_interface.vlan)

    def test_existing_physical_with_links_new_vlan_new_links(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=ip,
            subnet=subnet,
            interface=interface,
        )
        vid_on_fabric = random.randint(1, 4094)
        vlan_ipnetwork = factory.make_ip4_or_6_network()
        vlan_ip = factory.pick_ip_in_network(vlan_ipnetwork)

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        eth0_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]
        vlan_network = data.create_vlan_network(
            f"eth0.{vid_on_fabric}", parent=eth0_network, vid=vid_on_fabric
        )
        vlan_network.addresses = [
            LXDAddress(vlan_ip, vlan_ipnetwork.prefixlen),
        ]

        self.update_interfaces(controller, data)

        self.assertEqual(2, controller.current_config.interface_set.count())
        eth0 = Interface.objects.get(
            node_config=controller.current_config, name="eth0"
        )
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)
        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertCountEqual(
            [(IPADDRESS_TYPE.STICKY, ip, subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

        created_vlan = VLAN.objects.get(fabric=fabric, vid=vid_on_fabric)
        vlan_interface = VLANInterface.objects.get(
            node_config=controller.current_config, vlan=created_vlan
        )
        self.assertEqual(f"eth0.{vid_on_fabric}", vlan_interface.name)
        self.assertTrue(vlan_interface.enabled)
        self.assertTrue(created_vlan, vlan_interface.vlan)

        vlan_subnet = Subnet.objects.get(cidr=str(vlan_ipnetwork.cidr))
        self.assertEqual(created_vlan, vlan_subnet.vlan)
        self.assertEqual(str(vlan_ipnetwork.cidr), vlan_subnet.name)

        vlan_addresses = list(vlan_interface.ip_addresses.all())
        vlan_addresses = list(vlan_interface.ip_addresses.all())
        self.assertCountEqual(
            [(IPADDRESS_TYPE.STICKY, vlan_ip, vlan_subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in vlan_addresses
            ],
        )

    def test_existing_physical_with_links_new_vlan_other_subnet_vid(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=ip,
            subnet=subnet,
            interface=interface,
        )
        vid_on_fabric = random.randint(1, 4094)
        other_subnet = factory.make_Subnet()
        vlan_ip = factory.pick_ip_in_Subnet(other_subnet)

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        eth0_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]
        vlan_network = data.create_vlan_network(
            f"eth0.{vid_on_fabric}", parent=eth0_network, vid=vid_on_fabric
        )
        vlan_network.addresses = [
            LXDAddress(vlan_ip, other_subnet.get_ipnetwork().prefixlen),
        ]

        maaslog = self.patch(network_module, "maaslog")
        passes = self.update_interfaces(controller, data)

        self.assertEqual(2, controller.current_config.interface_set.count())
        eth0 = Interface.objects.get(
            node_config=controller.current_config, name="eth0"
        )
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)
        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertCountEqual(
            [(IPADDRESS_TYPE.STICKY, ip, subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

        self.assertFalse(
            VLAN.objects.filter(fabric=fabric, vid=vid_on_fabric).exists()
        )
        other_vlan = other_subnet.vlan
        vlan_interface = VLANInterface.objects.get(
            node_config=controller.current_config, vlan=other_vlan
        )
        self.assertEqual(f"eth0.{vid_on_fabric}", vlan_interface.name)
        self.assertTrue(vlan_interface.enabled)
        self.assertEqual(vlan_interface.ip_addresses.count(), 1)
        self.assertEqual(
            maaslog.method_calls,
            [
                call.error(
                    f"VLAN interface '{vlan_interface.name}' reports VLAN {vid_on_fabric} "
                    f"but links are on VLAN {other_vlan.vid}"
                ),
                call.error(
                    f"Interface 'eth0' on controller '{controller.hostname}' "
                    f"is not on the same fabric as VLAN interface '{vlan_interface.name}'."
                ),
            ]
            * passes,
        )

    def test_existing_physical_with_no_links_new_vlan_no_links(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        vid_on_fabric = random.randint(1, 4094)
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        vlan_network = data.create_vlan_network(
            f"eth0.{vid_on_fabric}", vid=vid_on_fabric, parent=eth0_network
        )
        self.update_interfaces(controller, data)
        self.assertEqual(2, controller.current_config.interface_set.count())
        [physical] = controller.current_config.interface_set.filter(
            type=INTERFACE_TYPE.PHYSICAL
        )
        self.assertEqual("eth0", physical.name)
        self.assertEqual(eth0_network.hwaddr, physical.mac_address)
        self.assertEqual(vlan, physical.vlan)
        self.assertTrue(physical.enabled)

        created_vlan = VLAN.objects.get(fabric=fabric, vid=vid_on_fabric)
        vlan_interface = VLANInterface.objects.get(
            node_config=controller.current_config, vlan=created_vlan
        )
        [vlan_interface] = controller.current_config.interface_set.filter(
            type=INTERFACE_TYPE.VLAN
        )
        self.assertEqual(vlan_network.name, vlan_interface.name)
        self.assertEqual(created_vlan, vlan_interface.vlan)
        self.assertTrue(vlan_interface.enabled)

    def test_existing_physical_with_no_links_new_vlan_with_links(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        other_fabric = factory.make_Fabric()
        new_vlan = factory.make_VLAN(fabric=other_fabric)
        subnet = factory.make_Subnet(vlan=new_vlan)
        ip = str(factory.pick_ip_in_Subnet(subnet))

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        vlan_network = data.create_vlan_network(
            f"eth0.{new_vlan.vid}", parent=eth0_network, vid=new_vlan.vid
        )
        vlan_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]

        maaslog = self.patch(network_module, "maaslog")
        passes = self.update_interfaces(controller, data)

        self.assertEqual(2, controller.current_config.interface_set.count())
        eth0 = Interface.objects.get(
            node_config=controller.current_config, name="eth0"
        )
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(fabric.get_default_vlan(), eth0.vlan)

        vlan_interface = VLANInterface.objects.get(
            node_config=controller.current_config, vlan=new_vlan
        )
        self.assertEqual(f"eth0.{new_vlan.vid}", vlan_interface.name)
        self.assertTrue(vlan_interface.enabled)

        vlan_addresses = list(vlan_interface.ip_addresses.all())
        self.assertCountEqual(
            [(IPADDRESS_TYPE.STICKY, ip, subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in vlan_addresses
            ],
        )
        self.assertEqual(
            maaslog.method_calls,
            [
                call.error(
                    f"Interface 'eth0' on controller '{controller.hostname}' "
                    f"is not on the same fabric as VLAN interface '{vlan_interface.name}'."
                )
            ]
            * passes,
        )

    def test_existing_physical_with_no_links_vlan_with_other_subnet(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, name="eth0", vlan=vlan
        )
        other_vlan = factory.make_VLAN(fabric=fabric)
        vlan_interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN,
            name=f"eth0.{other_vlan.vid}",
            vlan=other_vlan,
            parents=[interface],
        )

        new_fabric = factory.make_Fabric()
        new_vlan = factory.make_VLAN(fabric=new_fabric)
        new_subnet = factory.make_Subnet(vlan=new_vlan)
        ip = str(factory.pick_ip_in_Subnet(new_subnet))
        links_to_remove = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.AUTO, interface=vlan_interface
            )
            for _ in range(3)
        ]

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        vlan_network = data.create_vlan_network(
            f"eth0.{other_vlan.vid}", parent=eth0_network, vid=other_vlan.vid
        )
        vlan_network.addresses = [
            LXDAddress(ip, new_subnet.get_ipnetwork().prefixlen),
        ]

        maaslog = self.patch(network_module, "maaslog")
        passes = self.update_interfaces(controller, data)

        self.assertEqual(2, controller.current_config.interface_set.count())
        eth0 = Interface.objects.get(
            node_config=controller.current_config, name="eth0"
        )
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)

        vlan_interface = VLANInterface.objects.get(
            node_config=controller.current_config, vlan=new_vlan
        )
        self.assertEqual(f"eth0.{other_vlan.vid}", vlan_interface.name)
        self.assertTrue(vlan_interface.enabled)

        self.assertCountEqual(
            vlan_interface.ip_addresses.values_list("ip", flat=True), [ip]
        )
        self.assertEqual(
            maaslog.method_calls,
            [
                call.error(
                    f"VLAN interface '{vlan_interface.name}' reports VLAN {other_vlan.vid} "
                    f"but links are on VLAN {new_vlan.vid}"
                ),
                call.error(
                    f"Interface 'eth0' on controller '{controller.hostname}' "
                    f"is not on the same fabric as VLAN interface '{vlan_interface.name}'."
                ),
            ]
            * passes,
        )
        for link in links_to_remove:
            self.assertIsNone(reload_object(link))

    def test_existing_vlan_interface_different_fabric_from_parent(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, name="eth0", vlan=vlan
        )
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=ip,
            subnet=subnet,
            interface=interface,
        )
        new_fabric = factory.make_Fabric()
        new_vlan = factory.make_VLAN(fabric=new_fabric)
        vlan_subnet = factory.make_Subnet(vlan=new_vlan)
        vlan_ip = str(factory.pick_ip_in_Subnet(vlan_subnet))
        vlan_interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN,
            vlan=new_vlan,
            parents=[interface],
        )
        vlan_name = vlan_interface.name

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        vlan_network = data.create_vlan_network(
            vlan_name, parent=eth0_network, vid=new_vlan.vid
        )
        vlan_network.addresses = [
            LXDAddress(vlan_ip, vlan_subnet.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        self.assertEqual(2, controller.current_config.interface_set.count())
        eth0 = Interface.objects.get(
            node_config=controller.current_config, name="eth0"
        )
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)

        vlan_interface = VLANInterface.objects.get(
            node_config=controller.current_config, vlan=new_vlan
        )
        self.assertEqual(vlan_name, vlan_interface.name)
        self.assertTrue(vlan_interface.enabled)

        vlan_addresses = list(vlan_interface.ip_addresses.all())
        self.assertCountEqual(
            [(IPADDRESS_TYPE.STICKY, vlan_ip, vlan_subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in vlan_addresses
            ],
        )

    def test_bond_with_existing_parents(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(eth0.mac_address)
        )
        eth1_network = data.create_physical_network(
            "eth1", mac_address=str(eth1.mac_address)
        )
        bond_network = data.create_bond_network(
            "bond0", parents=[eth0_network, eth1_network]
        )

        self.update_interfaces(controller, data)

        self.assertEqual(3, controller.current_config.interface_set.count())
        bond_interface = BondInterface.objects.get(
            node_config=controller.current_config,
            mac_address=bond_network.hwaddr,
        )
        self.assertEqual("bond0", bond_interface.name)
        self.assertTrue(bond_interface.enabled)
        self.assertEqual(vlan, bond_interface.vlan)
        self.assertCountEqual(
            [parent.name for parent in bond_interface.parents.all()],
            ["eth0", "eth1"],
        )

    def test_bridge_with_missing_parents(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        data.create_bridge_network("br0", parents=[])
        data.networks["br0"].bridge.upper_devices = ["tap0", "veth1"]
        self.update_interfaces(controller, data)

        self.assertEqual(1, controller.current_config.interface_set.count())
        bridge_interface = BridgeInterface.objects.get(
            node_config=controller.current_config,
            name="br0",
        )
        self.assertCountEqual(
            [parent.name for parent in bridge_interface.parents.all()],
            [],
        )

    def test_bridge_with_existing_parents(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(eth0.mac_address)
        )
        eth1_network = data.create_physical_network(
            "eth1", mac_address=str(eth1.mac_address)
        )
        bridge_network = data.create_bridge_network(
            "br0",
            mac_address=str(eth1.mac_address),
            parents=[eth0_network, eth1_network],
        )

        self.update_interfaces(controller, data)

        self.assertEqual(3, controller.current_config.interface_set.count())
        bridge_interface = BridgeInterface.objects.get(
            node_config=controller.current_config,
            mac_address=bridge_network.hwaddr,
        )
        self.assertEqual("br0", bridge_interface.name)
        self.assertEqual(vlan, bridge_interface.vlan)
        self.assertCountEqual(
            [parent.name for parent in bridge_interface.parents.all()],
            ["eth0", "eth1"],
        )

    def test_bond_updates_existing_bond(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        factory.make_Interface(
            INTERFACE_TYPE.BOND,
            vlan=vlan,
            parents=[eth0, eth1],
            node=controller,
            name="bond0",
            mac_address=factory.make_mac_address(),
        )
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(eth0.mac_address)
        )
        data.create_physical_network("eth1", mac_address=str(eth1.mac_address))
        bond_network = data.create_bond_network(
            "bond0", parents=[eth0_network]
        )

        self.update_interfaces(controller, data)

        self.assertEqual(3, controller.current_config.interface_set.count())
        bond_interface = BondInterface.objects.get(
            node_config=controller.current_config,
            mac_address=bond_network.hwaddr,
        )
        self.assertEqual("bond0", bond_interface.name)
        self.assertEqual(vlan, bond_interface.vlan)
        self.assertCountEqual(
            [parent.name for parent in bond_interface.parents.all()],
            ["eth0"],
        )

    def test_bridge_updates_existing_bridge(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        factory.make_Interface(
            INTERFACE_TYPE.BRIDGE,
            vlan=vlan,
            parents=[eth0, eth1],
            node=controller,
            name="br0",
            mac_address=factory.make_mac_address(),
        )

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(eth0.mac_address)
        )
        data.create_physical_network("eth1", mac_address=str(eth1.mac_address))
        bridge_network = data.create_bridge_network(
            "br0", parents=[eth0_network]
        )

        self.update_interfaces(controller, data)

        self.assertEqual(3, controller.current_config.interface_set.count())
        bridge_interface = BridgeInterface.objects.get(
            node_config=controller.current_config,
            mac_address=bridge_network.hwaddr,
        )
        self.assertEqual("br0", bridge_interface.name)
        self.assertEqual(vlan, bridge_interface.vlan)
        self.assertCountEqual(
            [parent.name for parent in bridge_interface.parents.all()],
            ["eth0"],
        )

    def test_bond_creates_link_updates_parent_vlan(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[eth0, eth1], vlan=vlan
        )
        other_fabric = factory.make_Fabric()
        bond0_vlan = other_fabric.get_default_vlan()
        subnet = factory.make_Subnet(vlan=bond0_vlan)
        ip = str(factory.pick_ip_in_Subnet(subnet))

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(eth0.mac_address)
        )
        eth1_network = data.create_physical_network(
            "eth1", mac_address=str(eth1.mac_address)
        )
        bond_network = data.create_bond_network(
            "bond0", parents=[eth0_network, eth1_network]
        )
        bond_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        self.assertEqual(3, controller.current_config.interface_set.count())
        eth0 = Interface.objects.get(
            node_config=controller.current_config, name="eth0"
        )
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(eth0_network.hwaddr, str(eth0.mac_address))
        self.assertEqual(bond0_vlan, eth0.vlan)

        eth1 = Interface.objects.get(
            node_config=controller.current_config, name="eth1"
        )
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth1.type)
        self.assertEqual(eth1_network.hwaddr, str(eth1.mac_address))
        self.assertEqual(bond0_vlan, eth1.vlan)
        bond0 = get_one(Interface.objects.filter_by_ip(ip))
        self.assertEqual(INTERFACE_TYPE.BOND, bond0.type)
        self.assertEqual(bond_network.hwaddr, str(bond0.mac_address))
        self.assertEqual(bond0_vlan, bond0.vlan)
        self.assertCountEqual(
            [parent.name for parent in bond0.parents.all()],
            ["eth0", "eth1"],
        )

    def test_bridge_creates_link_updates_parent_vlan(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        br0 = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE, parents=[eth0, eth1], vlan=vlan
        )
        other_fabric = factory.make_Fabric()
        br0_vlan = other_fabric.get_default_vlan()
        subnet = factory.make_Subnet(vlan=br0_vlan)
        ip = str(factory.pick_ip_in_Subnet(subnet))

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(eth0.mac_address)
        )
        eth1_network = data.create_physical_network(
            "eth1", mac_address=str(eth1.mac_address)
        )
        bridge_network = data.create_bridge_network(
            "br0",
            parents=[eth0_network, eth1_network],
            mac_address=str(br0.mac_address),
        )
        bridge_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        self.assertEqual(3, controller.current_config.interface_set.count())
        eth0 = Interface.objects.get(
            node_config=controller.current_config, name="eth0"
        )
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(eth0_network.hwaddr, str(eth0.mac_address))
        self.assertEqual(br0_vlan, eth0.vlan)

        eth1 = Interface.objects.get(
            node_config=controller.current_config, name="eth1"
        )
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth1.type)
        self.assertEqual(eth1_network.hwaddr, str(eth1.mac_address))
        self.assertEqual(br0_vlan, eth1.vlan)
        br0 = get_one(Interface.objects.filter_by_ip(ip))
        self.assertEqual(INTERFACE_TYPE.BRIDGE, br0.type)
        self.assertEqual(bridge_network.hwaddr, str(br0.mac_address))
        self.assertEqual(br0_vlan, br0.vlan)
        self.assertCountEqual(
            [parent.name for parent in br0.parents.all()],
            ["eth0", "eth1"],
        )

    def test_bridge_with_mac_as_phyisical_not_updated(self):
        controller = self.create_empty_controller(with_empty_script_sets=True)
        mac_address = factory.make_mac_address()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, mac_address=mac_address
        )
        factory.make_Interface(
            INTERFACE_TYPE.BRIDGE, parents=[eth0], mac_address=mac_address
        )

        data = FakeCommissioningData()
        card = LXDNetworkCard(
            data.allocate_pci_address(),
            vendor=factory.make_name("vendor"),
            product=factory.make_name("product"),
            firmware_version=factory.make_name("firmware_version"),
        )
        eth0_network = data.create_physical_network(
            "eth0",
            mac_address=mac_address,
            card=card,
        )
        data.create_bridge_network(
            "br0",
            parents=[eth0_network],
            mac_address=mac_address,
        )

        lxd_script = (
            controller.current_commissioning_script_set.find_script_result(
                script_name=COMMISSIONING_OUTPUT_NAME
            )
        )
        lxd_script_output = data.render(include_extra=True)
        lxd_script.store_result(
            0, stdout=json.dumps(lxd_script_output).encode("utf-8")
        )

        self.update_interfaces(controller, data)

        br0 = Interface.objects.get(
            name="br0", node_config=controller.current_config
        )
        self.assertNotEqual(card.vendor, br0.vendor)
        self.assertNotEqual(card.product, br0.product)
        self.assertNotEqual(card.firmware_version, br0.firmware_version)

    def test_removes_missing_interfaces(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[eth0, eth1], vlan=vlan
        )
        data = FakeCommissioningData()

        self.update_interfaces(controller, data)

        self.assertIsNone(reload_object(eth0))
        self.assertIsNone(reload_object(eth1))
        self.assertIsNone(reload_object(bond0))

    def test_removes_one_bond_parent(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND, name="bond0", parents=[eth0, eth1], vlan=vlan
        )

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0",
            mac_address=str(eth0.mac_address),
        )
        data.create_bond_network(
            "bond0",
            parents=[eth0_network],
            mac_address=str(bond0.mac_address),
        )

        self.update_interfaces(controller, data)

        self.assertIsNotNone(reload_object(eth0))
        self.assertIsNone(reload_object(eth1))
        self.assertIsNotNone(reload_object(bond0))

    def test_removes_one_bridge_parent(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        br0 = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE, name="br0", parents=[eth0, eth1], vlan=vlan
        )

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0",
            mac_address=str(eth0.mac_address),
        )
        data.create_bridge_network(
            "br0",
            parents=[eth0_network],
            mac_address=str(br0.mac_address),
        )

        self.update_interfaces(controller, data)

        self.assertIsNotNone(reload_object(eth0))
        self.assertIsNone(reload_object(eth1))
        self.assertIsNotNone(reload_object(br0))

    def test_physical_not_connected_marked_up(self):
        # Even if a NIC is not physically connected, LXD might still
        # mark the network as "up". In that case, the VLAN should be set
        # to None.
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        controller = self.create_empty_controller(with_empty_script_sets=True)
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        data = FakeCommissioningData()
        card = data.create_network_card()
        data.create_physical_network("eth0", mac_address=str(eth0.mac_address))
        data.create_physical_network("eth1", card=card)
        [port] = card.ports
        port.link_detected = False

        self.update_interfaces(controller, data)

        eth1 = Interface.objects.get(
            node_config=controller.current_config, name="eth1"
        )
        self.assertIsNone(eth1.vlan)
        # Check that no extra fabrics were created, since we previously
        # had a bug where the fabric/vlan was created for the interface,
        # and later the interface's vlan was set to None.
        self.assertEqual([fabric], list(Fabric.objects.all()))

    def test_removes_one_bond_and_one_parent(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[eth0, eth1], vlan=vlan
        )

        data = FakeCommissioningData()
        data.create_physical_network(
            "eth0",
            mac_address=str(eth0.mac_address),
        )

        self.update_interfaces(controller, data)

        self.assertIsNotNone(reload_object(eth0))
        self.assertIsNone(reload_object(eth1))
        self.assertIsNone(reload_object(bond0))

    def test_removes_one_bridge_and_one_parent(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        br0 = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE, parents=[eth0, eth1], vlan=vlan
        )

        data = FakeCommissioningData()
        data.create_physical_network(
            "eth0",
            mac_address=str(eth0.mac_address),
        )

        self.update_interfaces(controller, data)

        self.assertIsNotNone(reload_object(eth0))
        self.assertIsNone(reload_object(eth1))
        self.assertIsNone(reload_object(br0))

    def test_all_new_bond_with_vlan(self):
        controller = self.create_empty_controller()
        bond0_fabric = factory.make_Fabric()
        bond0_untagged = bond0_fabric.get_default_vlan()
        bond0_subnet = factory.make_Subnet(vlan=bond0_untagged)
        bond0_ip = str(factory.pick_ip_in_Subnet(bond0_subnet))
        bond0_vlan = factory.make_VLAN(fabric=bond0_fabric)
        bond0_vlan_subnet = factory.make_Subnet(vlan=bond0_vlan)
        bond0_vlan_ip = str(factory.pick_ip_in_Subnet(bond0_vlan_subnet))

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        eth1_network = data.create_physical_network("eth1")
        bond_network = data.create_bond_network(
            "bond0", parents=[eth0_network, eth1_network]
        )
        bond_network.addresses = [
            LXDAddress(bond0_ip, bond0_subnet.get_ipnetwork().prefixlen),
        ]
        bond_vlan_network = data.create_vlan_network(
            f"bond0.{bond0_vlan.vid}", parent=bond_network, vid=bond0_vlan.vid
        )
        bond_vlan_network.addresses = [
            LXDAddress(
                bond0_vlan_ip, bond0_vlan_subnet.get_ipnetwork().prefixlen
            ),
        ]

        self.update_interfaces(controller, data)

        eth0 = PhysicalInterface.objects.get(
            node_config=controller.current_config,
            mac_address=eth0_network.hwaddr,
        )
        self.assertEqual("eth0", eth0.name)
        self.assertTrue(eth0.enabled)
        self.assertEqual(bond0_untagged, eth0.vlan)
        eth1 = PhysicalInterface.objects.get(
            node_config=controller.current_config,
            mac_address=eth1_network.hwaddr,
        )
        self.assertEqual("eth1", eth1.name)
        self.assertTrue(eth1.enabled)
        self.assertEqual(bond0_untagged, eth1.vlan)
        bond0 = BondInterface.objects.get(
            node_config=controller.current_config,
            mac_address=bond_network.hwaddr,
        )
        self.assertEqual("bond0", bond0.name)
        self.assertTrue(bond0.enabled)
        self.assertEqual(bond0_untagged, bond0.vlan)
        self.assertCountEqual(
            [parent.name for parent in bond0.parents.all()],
            ["eth0", "eth1"],
        )
        bond0_addresses = [
            (address.alloc_type, address.ip, address.subnet)
            for address in bond0.ip_addresses.all()
        ]
        self.assertCountEqual(
            [(IPADDRESS_TYPE.STICKY, bond0_ip, bond0_subnet)],
            bond0_addresses,
        )
        bond0_vlan_nic = VLANInterface.objects.get(
            node_config=controller.current_config, vlan=bond0_vlan
        )
        self.assertEqual(f"bond0.{bond0_vlan.vid}", bond0_vlan_nic.name)
        self.assertTrue(bond0_vlan_nic.enabled)
        self.assertEqual(bond0_vlan, bond0_vlan_nic.vlan)
        self.assertEqual(
            [parent.name for parent in bond0_vlan_nic.parents.all()],
            ["bond0"],
        )
        bond0_vlan_nic_addresses = [
            (address.alloc_type, address.ip, address.subnet)
            for address in bond0_vlan_nic.ip_addresses.all()
        ]
        self.assertCountEqual(
            [(IPADDRESS_TYPE.STICKY, bond0_vlan_ip, bond0_vlan_subnet)],
            bond0_vlan_nic_addresses,
        )

    def test_all_new_bridge_with_vlan(self):
        controller = self.create_empty_controller()
        br0_fabric = factory.make_Fabric()
        br0_untagged = br0_fabric.get_default_vlan()
        br0_subnet = factory.make_Subnet(vlan=br0_untagged)
        br0_ip = str(factory.pick_ip_in_Subnet(br0_subnet))
        br0_vlan = factory.make_VLAN(fabric=br0_fabric)
        br0_vlan_subnet = factory.make_Subnet(vlan=br0_vlan)
        br0_vlan_ip = str(factory.pick_ip_in_Subnet(br0_vlan_subnet))

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        eth1_network = data.create_physical_network("eth1")
        bridge_network = data.create_bridge_network(
            "br0", parents=[eth0_network, eth1_network]
        )
        bridge_network.addresses = [
            LXDAddress(br0_ip, br0_subnet.get_ipnetwork().prefixlen),
        ]
        bond_vlan_network = data.create_vlan_network(
            f"br0.{br0_vlan.vid}", parent=bridge_network, vid=br0_vlan.vid
        )
        bond_vlan_network.addresses = [
            LXDAddress(br0_vlan_ip, br0_vlan_subnet.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        eth0 = PhysicalInterface.objects.get(
            node_config=controller.current_config,
            mac_address=eth0_network.hwaddr,
        )
        self.assertEqual("eth0", eth0.name)
        self.assertTrue(eth0.enabled)
        self.assertEqual(br0_untagged, eth0.vlan)
        eth1 = PhysicalInterface.objects.get(
            node_config=controller.current_config,
            mac_address=eth1_network.hwaddr,
        )
        self.assertEqual("eth1", eth1.name)
        self.assertTrue(eth1.enabled)
        self.assertEqual(br0_untagged, eth1.vlan)

        br0 = BridgeInterface.objects.get(
            node_config=controller.current_config,
            mac_address=bridge_network.hwaddr,
        )
        self.assertEqual("br0", br0.name)
        self.assertTrue(br0.enabled)
        self.assertEqual(br0_untagged, br0.vlan)
        self.assertCountEqual(
            [parent.name for parent in br0.parents.all()],
            ["eth0", "eth1"],
        )
        br0_addresses = [
            (address.alloc_type, address.ip, address.subnet)
            for address in br0.ip_addresses.all()
        ]
        self.assertCountEqual(
            [(IPADDRESS_TYPE.STICKY, br0_ip, br0_subnet)], br0_addresses
        )
        br0_vlan_nic = VLANInterface.objects.get(
            node_config=controller.current_config, vlan=br0_vlan
        )
        self.assertEqual(f"br0.{br0_vlan.vid}", br0_vlan_nic.name)
        self.assertTrue(br0_vlan_nic.enabled)
        self.assertEqual(br0_vlan, br0_vlan_nic.vlan)
        self.assertEqual(
            [parent.name for parent in br0_vlan_nic.parents.all()],
            ["br0"],
        )
        br0_vlan_nic_addresses = [
            (address.alloc_type, address.ip, address.subnet)
            for address in br0_vlan_nic.ip_addresses.all()
        ]
        self.assertCountEqual(
            [(IPADDRESS_TYPE.STICKY, br0_vlan_ip, br0_vlan_subnet)],
            br0_vlan_nic_addresses,
        )

    def test_two_controllers_with_similar_configurations_bug_1563701(self):
        data1 = FakeCommissioningData()
        ens3_network = data1.create_physical_network(
            "ens3", mac_address="52:54:00:ff:0a:cf"
        )
        ens3_network.addresses = [LXDAddress("10.2.0.2", 20)]
        ens4_network = data1.create_physical_network(
            "ens4", mac_address="52:54:00:ab:da:de"
        )
        ens4_network.addresses = [LXDAddress("192.168.35.43", 22)]
        data1.address_annotations["192.168.35.43"] = {
            "mode": "dhcp",
            "gateway": "192.168.32.2",
        }
        ens5_network = data1.create_physical_network(
            "ens5", mac_address="52:54:00:70:8f:5b"
        )
        for vid in range(10, 17):
            vlan_network = data1.create_vlan_network(
                f"ens5.{vid}", parent=ens5_network
            )
            vlan_network.addresses = [LXDAddress(f"10.{vid}.0.2", 20)]

        data2 = FakeCommissioningData()
        ens3_network = data2.create_physical_network(
            "ens3", mac_address="52:54:00:02:eb:bc"
        )
        ens3_network.addresses = [LXDAddress("10.2.0.3", 20)]
        ens4_network = data2.create_physical_network(
            "ens4", mac_address="52:54:00:bc:b0:85"
        )
        ens4_network.addresses = [LXDAddress("192.168.33.246", 22)]
        data2.address_annotations["192.168.33.246"] = {
            "mode": "dhcp",
            "gateway": "192.168.32.2",
        }
        ens5_network = data2.create_physical_network(
            "ens5", mac_address="52:54:00:cf:f3:7f"
        )
        for vid in range(10, 17):
            vlan_network = data2.create_vlan_network(
                f"ens5.{vid}", parent=ens5_network
            )
            vlan_network.addresses = [LXDAddress(f"10.{vid}.0.3", 20)]

        controller1 = self.create_empty_controller()
        controller2 = self.create_empty_controller()
        self.update_interfaces(controller1, data1)
        self.update_interfaces(controller2, data2)
        r1_ens5_16 = get_one(Interface.objects.filter_by_ip("10.16.0.2"))
        self.assertIsNotNone(r1_ens5_16)
        r2_ens5_16 = get_one(Interface.objects.filter_by_ip("10.16.0.3"))
        self.assertIsNotNone(r2_ens5_16)

    def test_all_new_bridge_on_vlan_interface_with_identical_macs(self):
        controller = self.create_empty_controller()
        default_vlan = VLAN.objects.get_default_vlan()
        br0_fabric = factory.make_Fabric()
        eth0_100_vlan = factory.make_VLAN(vid=100, fabric=br0_fabric)
        br0_subnet = factory.make_Subnet(vlan=eth0_100_vlan)
        br0_ip = str(factory.pick_ip_in_Subnet(br0_subnet))
        eth0_mac = factory.make_mac_address()
        br1_fabric = factory.make_Fabric()
        eth1_100_vlan = factory.make_VLAN(vid=100, fabric=br1_fabric)
        br1_subnet = factory.make_Subnet(vlan=eth1_100_vlan)
        br1_ip = str(factory.pick_ip_in_Subnet(br1_subnet))
        eth1_mac = factory.make_mac_address()
        eth0_101_vlan = factory.make_VLAN(vid=101, fabric=br1_fabric)
        br101_subnet = factory.make_Subnet(vlan=eth0_101_vlan)
        br101_ip = str(factory.pick_ip_in_Subnet(br101_subnet))

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=eth0_mac
        )
        eth0_100_network = data.create_vlan_network(
            "eth0.100", mac_address=eth0_mac, parent=eth0_network, vid=100
        )
        eth0_101_network = data.create_vlan_network(
            "eth0.101", mac_address=eth0_mac, parent=eth0_network, vid=101
        )
        br0_network = data.create_bridge_network(
            "br0", mac_address=eth0_mac, parents=[eth0_100_network]
        )
        br0_network.addresses = [
            LXDAddress(br0_ip, br0_subnet.get_ipnetwork().prefixlen),
        ]
        br101_network = data.create_bridge_network(
            "br101", mac_address=eth0_mac, parents=[eth0_101_network]
        )
        br101_network.addresses = [
            LXDAddress(br101_ip, br101_subnet.get_ipnetwork().prefixlen),
        ]
        data.create_physical_network("eth1", mac_address=eth1_mac)
        eth1_100_network = data.create_vlan_network(
            "eth1.100", mac_address=eth1_mac, parent=eth0_network, vid=100
        )
        br1_network = data.create_bridge_network(
            "br1", mac_address=eth1_mac, parents=[eth1_100_network]
        )
        br1_network.addresses = [
            LXDAddress(br1_ip, br1_subnet.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        eth0 = PhysicalInterface.objects.get(
            node_config=controller.current_config, mac_address=eth0_mac
        )
        self.assertEqual("eth0", eth0.name)
        self.assertTrue(eth0.enabled)
        self.assertEqual(default_vlan, eth0.vlan)
        eth0_100 = VLANInterface.objects.get(
            node_config=controller.current_config,
            name="eth0.100",
            mac_address=eth0_mac,
        )
        self.assertTrue(eth0_100.enabled)
        self.assertEqual(eth0_100_vlan, eth0_100.vlan)
        br0 = BridgeInterface.objects.get(
            node_config=controller.current_config,
            name="br0",
            mac_address=eth0_mac,
        )
        self.assertTrue(br0.enabled)
        self.assertEqual(eth0_100_vlan, br0.vlan)
        br0_addresses = [
            (address.alloc_type, address.ip, address.subnet)
            for address in br0.ip_addresses.all()
        ]
        self.assertCountEqual(
            [(IPADDRESS_TYPE.STICKY, br0_ip, br0_subnet)], br0_addresses
        )
        br0_nic = BridgeInterface.objects.get(
            node_config=controller.current_config, vlan=eth0_100_vlan
        )
        self.assertEqual("br0", br0_nic.name)
        self.assertTrue(br0_nic.enabled)
        self.assertEqual(eth0_100_vlan, br0_nic.vlan)

    def test_registers_bridge_with_disabled_parent(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        eth0_network.addresses = [LXDAddress("10.0.0.2", 24)]
        data.address_annotations["10.0.0.2"] = {"gateway": "10.0.0.1"}
        virbr_nic_network = data.create_physical_network("virbr0-nic")
        virbr_nic_network.state = "down"
        virbr_network = data.create_bridge_network(
            "virbr0",
            mac_address=virbr_nic_network.hwaddr,
            parents=[virbr_nic_network],
        )
        virbr_network.addresses = [LXDAddress("192.168.122.1", 24)]

        self.update_interfaces(controller, data)

        subnet = get_one(Subnet.objects.filter(cidr="10.0.0.0/24"))
        self.assertIsNotNone(subnet)
        subnet = get_one(Subnet.objects.filter(cidr="192.168.122.0/24"))
        self.assertIsNotNone(subnet)

    def test_registers_bridge_with_no_parents_and_links(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        data.create_physical_network("eth0")
        br0_network = data.create_bridge_network("br0", parents=[])
        br0_network.addresses = [LXDAddress("192.168.0.1", 24)]

        self.update_interfaces(controller, data)

        eth0 = get_one(
            PhysicalInterface.objects.filter(
                node_config=controller.current_config, name="eth0"
            )
        )
        br0 = get_one(
            BridgeInterface.objects.filter(
                node_config=controller.current_config, name="br0"
            )
        )
        self.assertIsNotNone(eth0)
        self.assertIsNotNone(br0)
        subnet = get_one(Subnet.objects.filter(cidr="192.168.0.0/24"))
        self.assertIsNotNone(subnet)
        self.assertEqual(subnet.vlan, br0.vlan)

    def test_registers_bridge_with_no_parents_and_no_links(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        data.create_bridge_network("br0", parents=[])
        data.create_physical_network("eth0")

        self.update_interfaces(controller, data)

        eth0 = get_one(
            PhysicalInterface.objects.filter(
                node_config=controller.current_config, name="eth0"
            )
        )
        br0 = get_one(
            BridgeInterface.objects.filter(
                node_config=controller.current_config, name="br0"
            )
        )
        self.assertIsNotNone(eth0)
        self.assertIsNotNone(br0)

    def test_disabled_interfaces_do_not_create_fabrics(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        data.create_physical_network("eth0")
        eth1_network = data.create_physical_network("eth1")
        eth1_network.state = "down"

        self.update_interfaces(controller, data)

        eth1 = get_one(
            PhysicalInterface.objects.filter(
                node_config=controller.current_config, name="eth1"
            )
        )
        self.assertIsNone(eth1.vlan)

    def test_subnet_seen_on_second_controller_does_not_create_fabric(self):
        alice = self.create_empty_controller()
        bob = self.create_empty_controller()
        alice_data = FakeCommissioningData()
        alice_eth0_network = alice_data.create_physical_network("eth0")
        alice_eth0_network.addresses = [LXDAddress("192.168.0.1", 24)]
        alice_eth1_network = alice_data.create_physical_network("eth1")
        alice_eth1_network.state = "down"

        bob_data = FakeCommissioningData()
        bob_eth0_network = bob_data.create_physical_network("eth0")
        bob_eth0_network.addresses = [LXDAddress("192.168.0.2", 24)]
        bob_eth1_network = bob_data.create_physical_network("eth1")
        bob_eth1_network.state = "down"

        self.update_interfaces(alice, alice_data)

        self.update_interfaces(bob, bob_data)
        alice_eth0 = get_one(
            PhysicalInterface.objects.filter(
                node_config=alice.current_config, name="eth0"
            )
        )
        bob_eth0 = get_one(
            PhysicalInterface.objects.filter(
                node_config=bob.current_config, name="eth0"
            )
        )
        self.assertEqual(alice_eth0.vlan, bob_eth0.vlan)

    def test_physical_network_no_card(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        data.create_physical_network_without_nic("eth0")
        data.networks["eth0"].addresses = [LXDAddress("10.0.0.2", 24)]

        self.update_interfaces(controller, data)

        eth0 = PhysicalInterface.objects.get(
            node_config=controller.current_config,
            name="eth0",
        )
        self.assertTrue(eth0.enabled)
        self.assertEqual(data.networks["eth0"].hwaddr, eth0.mac_address)
        eth0_addresses = [
            (address.alloc_type, address.ip)
            for address in eth0.ip_addresses.all()
        ]
        self.assertCountEqual(
            [(IPADDRESS_TYPE.STICKY, "10.0.0.2")],
            eth0_addresses,
        )

    def test_loopback_not_processes(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        data.create_physical_network("eth0")
        data.create_physical_network_without_nic("lo")
        data.networks["lo"].type = "loopback"

        self.update_interfaces(controller, data)

        self.assertEqual(
            ["eth0"],
            [
                iface.name
                for iface in Interface.objects.filter(
                    node_config=controller.current_config
                ).all()
            ],
        )
        eth0 = PhysicalInterface.objects.get(
            node_config=controller.current_config,
            name="eth0",
        )
        self.assertTrue(eth0.enabled)
        self.assertEqual(data.networks["eth0"].hwaddr, eth0.mac_address)

    def test_physical_not_in_extra_data(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        data.create_physical_network("eth0")

        commissioning_data = data.render(include_extra=True)
        del commissioning_data["network-extra"]["interfaces"]["eth0"]
        update_node_interfaces(controller, commissioning_data)

        self.assertEqual(
            ["eth0"],
            [
                iface.name
                for iface in Interface.objects.filter(
                    node_config=controller.current_config
                ).all()
            ],
        )
        eth0 = PhysicalInterface.objects.get(
            node_config=controller.current_config,
            name="eth0",
        )
        self.assertTrue(eth0.enabled)
        self.assertEqual(data.networks["eth0"].hwaddr, eth0.mac_address)

    def test_physical_container(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        # In containers, the NICs show up as cards, but they don't have
        # any ports.
        data.create_network_card()
        data.create_physical_network_without_nic("eth0")

        self.update_interfaces(controller, data)

        self.assertEqual(
            ["eth0"],
            [
                iface.name
                for iface in Interface.objects.filter(
                    node_config=controller.current_config
                ).all()
            ],
        )
        eth0 = PhysicalInterface.objects.get(
            node_config=controller.current_config,
            name="eth0",
        )
        self.assertTrue(eth0.enabled)
        self.assertEqual(data.networks["eth0"].hwaddr, eth0.mac_address)

    def test_fixes_link_netmasks(self):
        controller = self.create_empty_controller(with_empty_script_sets=True)
        data = FakeCommissioningData()
        card = data.create_network_card()
        card.vendor = factory.make_name("vendor")
        card.product = factory.make_name("product")
        card.firmware_version = factory.make_name("firmware_version")
        network = data.create_physical_network("eth0", card=card)
        network.addresses = [
            LXDAddress("192.168.0.1", 24),
            LXDAddress("192.168.0.2", 32),
            LXDAddress("2001::aaaa:1", 112),
            LXDAddress("2001::aaaa:2", 128),
        ]
        self.update_interfaces(controller, data)
        eth0 = Interface.objects.get(
            name="eth0", node_config=controller.current_config
        )
        self.assertCountEqual(
            eth0.ip_addresses.values_list("ip", "subnet__cidr"),
            [
                ("192.168.0.1", "192.168.0.0/24"),
                ("192.168.0.2", "192.168.0.0/24"),
                ("2001::aaaa:1", "2001::aaaa:0/112"),
                ("2001::aaaa:2", "2001::aaaa:0/112"),
            ],
        )

    def test_no_empty_fabrics(self):
        data = FakeCommissioningData()
        eth0 = data.create_physical_network(name="eth0")
        veth0 = data.create_physical_network_without_nic(name="veth0")
        data.create_bridge_network("br0", parents=[eth0, veth0])
        node = factory.make_Node()
        self.update_interfaces(node, data)
        # All interfaces are on the same fabric/vlan and no extra fabric is created
        self.assertEqual(Fabric.objects.count(), 1)
        self.assertEqual(VLAN.objects.count(), 1)

    def test_hardware_sync_added_physical_interface_is_not_marked_acquired(
        self,
    ):
        node = factory.make_Node(
            enable_hw_sync=True, status=NODE_STATUS.DEPLOYED
        )
        data = FakeCommissioningData()
        data.create_physical_network(name="eth0")
        self.update_interfaces(node, data)
        node.refresh_from_db()
        iface = node.current_config.interface_set.get(name="eth0")
        self.assertFalse(iface.acquired)


class TestUpdateInterfacesWithHints(
    MAASTransactionServerTestCase, UpdateInterfacesMixin
):
    def setUp(self):
        super().setUp()
        self.patch(hooks, "start_workflow")

    def test_seen_on_second_controller(self):
        alice = self.create_empty_controller()
        bob = self.create_empty_controller()
        factory.make_Node()
        alice_data = FakeCommissioningData()
        alice_data.create_physical_network("eth0")
        alice_data.networks["eth0"].addresses = [LXDAddress("192.168.0.1", 24)]
        alice_data.address_annotations["192.168.0.1"] = {"mode": "dhcp"}
        alice_data.create_physical_network("eth1")
        alice_data.networks["eth1"].state = "down"

        bob_data = FakeCommissioningData()
        bob_data.create_physical_network("eth0")
        bob_data.create_physical_network("eth1")
        bob_data.hints = [
            {
                "hint": "same_local_fabric_as",
                "ifname": "eth0",
                "related_ifname": "eth1",
            },
            {
                "hint": "on_remote_network",
                "ifname": "eth0",
                "related_ifname": "eth0",
                "related_mac": alice_data.networks["eth0"].hwaddr,
            },
            {
                "hint": "routable_to",
                "ifname": "eth0",
                "related_ifname": "eth0",
                "related_mac": alice_data.networks["eth0"].hwaddr,
            },
            {
                "hint": "rx_own_beacon_on_other_interface",
                "ifname": "eth1",
                "related_ifname": "eth0",
            },
        ]
        self.update_interfaces(alice, alice_data)
        self.update_interfaces(bob, bob_data)
        alice_eth0 = get_one(
            PhysicalInterface.objects.filter(
                node_config=alice.current_config, name="eth0"
            )
        )
        bob_eth0 = get_one(
            PhysicalInterface.objects.filter(
                node_config=bob.current_config, name="eth0"
            )
        )
        bob_eth1 = get_one(
            PhysicalInterface.objects.filter(
                node_config=bob.current_config, name="eth1"
            )
        )
        # Registration with beaconing; we should see all these interfaces
        # appear on the same VLAN.
        self.assertEqual(alice_eth0.vlan, bob_eth0.vlan)
        self.assertEqual(bob_eth1.vlan, bob_eth0.vlan)

    def test_bridge_seen_on_second_controller(self):
        alice = self.create_empty_controller()
        bob = self.create_empty_controller()
        factory.make_Node()
        alice_data = FakeCommissioningData()
        alice_data.create_bridge_network("br0", parents=[])
        alice_data.networks["br0"].addresses = [LXDAddress("192.168.0.1", 24)]
        alice_data.address_annotations["192.168.0.1"] = {"mode": "dhcp"}
        alice_data.create_physical_network("eth1")
        alice_data.networks["eth1"].state = "down"

        bob_data = FakeCommissioningData()
        bob_data.create_physical_network("eth0")
        bob_data.create_physical_network("eth1")
        bob_data.hints = [
            {
                "hint": "same_local_fabric_as",
                "ifname": "eth0",
                "related_ifname": "eth1",
            },
            {
                "hint": "on_remote_network",
                "ifname": "eth0",
                "related_ifname": "br0",
                "related_mac": alice_data.networks["br0"].hwaddr,
            },
            {
                "hint": "routable_to",
                "ifname": "eth0",
                "related_ifname": "br0",
                "related_mac": alice_data.networks["br0"].hwaddr,
            },
            {
                "hint": "rx_own_beacon_on_other_interface",
                "ifname": "eth1",
                "related_ifname": "eth0",
            },
        ]
        self.update_interfaces(alice, alice_data)
        self.update_interfaces(bob, bob_data)
        alice_br0 = get_one(
            BridgeInterface.objects.filter(
                node_config=alice.current_config, name="br0"
            )
        )
        bob_eth0 = get_one(
            PhysicalInterface.objects.filter(
                node_config=bob.current_config, name="eth0"
            )
        )
        bob_eth1 = get_one(
            PhysicalInterface.objects.filter(
                node_config=bob.current_config, name="eth1"
            )
        )
        # Registration with beaconing; we should see all these interfaces
        # appear on the same VLAN.
        self.assertEqual(alice_br0.vlan, bob_eth0.vlan)
        self.assertEqual(bob_eth1.vlan, bob_eth0.vlan)


class BaseUpdateInterfacesAcquire(UpdateInterfacesMixin):
    def test_node_physical_interfaces(self):
        node = self.create_empty_node()

        data = FakeCommissioningData()
        data.create_physical_network("eth0")
        data.create_physical_network("eth1")
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            node=node,
            name="eth0",
            mac_address=data.networks["eth0"].hwaddr,
        )

        self.update_interfaces(node, data)

        eth0 = PhysicalInterface.objects.get(
            node_config=node.current_config, name="eth0"
        )
        eth1 = PhysicalInterface.objects.get(
            node_config=node.current_config, name="eth1"
        )

        self.assert_physical_interfaces(eth0, eth1)

    def test_node_vlan_interfaces(self):
        node = self.create_empty_node()

        data = FakeCommissioningData()
        data.create_physical_network("eth0")
        data.create_vlan_network(
            "eth0.10", vid=10, parent=data.networks["eth0"]
        )
        data.create_physical_network("eth1")
        data.create_vlan_network(
            "eth1.11", vid=11, parent=data.networks["eth1"]
        )
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            node=node,
            name="eth0",
            mac_address=data.networks["eth0"].hwaddr,
        )
        factory.make_Interface(
            INTERFACE_TYPE.VLAN,
            node=node,
            name="eth0.10",
            parents=[eth0],
            mac_address=data.networks["eth0.10"].hwaddr,
            vlan=factory.make_VLAN(vid=10, fabric=eth0.vlan.fabric),
        )

        self.update_interfaces(node, data)

        eth0 = PhysicalInterface.objects.get(
            node_config=node.current_config, name="eth0"
        )
        eth0_10 = VLANInterface.objects.get(
            node_config=node.current_config, name="eth0.10"
        )
        eth1 = PhysicalInterface.objects.get(
            node_config=node.current_config, name="eth1"
        )
        eth1_11 = VLANInterface.objects.get(
            node_config=node.current_config, name="eth1.11"
        )

        self.assert_physical_interfaces(eth0, eth1)
        self.assert_vlan_interfaces(eth0_10, eth1_11)

    def test_node_bridge_interfaces(self):
        node = self.create_empty_node()

        data = FakeCommissioningData()
        data.create_physical_network("eth0")
        data.create_bridge_network("br0", parents=[data.networks["eth0"]])
        data.create_physical_network("eth1")
        data.create_bridge_network("br1", parents=[data.networks["eth1"]])
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            node=node,
            name="eth0",
            mac_address=data.networks["eth0"].hwaddr,
        )
        factory.make_Interface(
            INTERFACE_TYPE.BRIDGE,
            node=node,
            name="br0",
            parents=[eth0],
            mac_address=data.networks["br0"].hwaddr,
        )

        self.update_interfaces(node, data)

        eth0 = PhysicalInterface.objects.get(
            node_config=node.current_config, name="eth0"
        )
        br0 = BridgeInterface.objects.get(
            node_config=node.current_config, name="br0"
        )
        eth1 = PhysicalInterface.objects.get(
            node_config=node.current_config, name="eth1"
        )
        br1 = BridgeInterface.objects.get(
            node_config=node.current_config, name="br1"
        )

        self.assert_physical_interfaces(eth0, eth1)
        self.assert_bridge_interfaces(br0, br1)

    def test_node_bond_interfaces(self):
        node = self.create_empty_node()

        data = FakeCommissioningData()
        data.create_physical_network("eth0")
        data.create_physical_network("eth1")
        data.create_bond_network(
            "bond0", parents=[data.networks["eth0"], data.networks["eth1"]]
        )
        data.create_physical_network("eth2")
        data.create_physical_network("eth3")
        data.create_bond_network(
            "bond1", parents=[data.networks["eth2"], data.networks["eth3"]]
        )
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            node=node,
            name="eth0",
            mac_address=data.networks["eth0"].hwaddr,
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            node=node,
            name="eth1",
            mac_address=data.networks["eth1"].hwaddr,
        )
        factory.make_Interface(
            INTERFACE_TYPE.BOND,
            node=node,
            name="bond0",
            parents=[eth0, eth1],
            mac_address=data.networks["bond0"].hwaddr,
        )

        self.update_interfaces(node, data)

        eth0 = PhysicalInterface.objects.get(
            node_config=node.current_config, name="eth0"
        )
        eth1 = PhysicalInterface.objects.get(
            node_config=node.current_config, name="eth1"
        )
        bond0 = BondInterface.objects.get(
            node_config=node.current_config, name="bond0"
        )
        eth2 = PhysicalInterface.objects.get(
            node_config=node.current_config, name="eth2"
        )
        eth3 = PhysicalInterface.objects.get(
            node_config=node.current_config, name="eth3"
        )
        bond1 = BondInterface.objects.get(
            node_config=node.current_config, name="bond1"
        )

        self.assert_physical_interfaces(eth0, eth2)
        self.assert_physical_interfaces(eth1, eth3)
        self.assert_bond_interfaces(bond0, bond1)


class TestUpdateInterfacesAcquiredNonDeployedNode(
    MAASServerTestCase, BaseUpdateInterfacesAcquire
):
    def setUp(self):
        super().setUp()
        self.patch(hooks, "start_workflow")

    def create_empty_node(self):
        return factory.make_Machine(
            status=factory.pick_choice(
                NODE_STATUS_CHOICES,
                but_not=(NODE_STATUS.DEPLOYING, NODE_STATUS.DEPLOYED),
            )
        )

    def assert_physical_interfaces(self, existing_eth0, new_eth1):
        self.assertFalse(existing_eth0.acquired)
        self.assertFalse(new_eth1.acquired)

    def assert_vlan_interfaces(self, existing_eth0_10, new_eth1_11):
        self.assertFalse(existing_eth0_10.acquired)
        self.assertTrue(new_eth1_11.acquired)

    def assert_bridge_interfaces(self, existing_br0, new_br1):
        self.assertFalse(existing_br0.acquired)
        self.assertTrue(new_br1.acquired)

    def assert_bond_interfaces(self, existing_bond0, new_bond1):
        self.assertFalse(existing_bond0.acquired)
        self.assertTrue(new_bond1.acquired)


class TestUpdateInterfacesAcquiredDeployedNode(
    MAASServerTestCase, BaseUpdateInterfacesAcquire
):
    def setUp(self):
        super().setUp()
        self.patch(hooks, "start_workflow")

    def create_empty_node(self):
        return factory.make_Machine(status=NODE_STATUS.DEPLOYED)

    def assert_physical_interfaces(self, existing_eth0, new_eth1):
        self.assertFalse(existing_eth0.acquired)
        self.assertTrue(new_eth1.acquired)

    def assert_vlan_interfaces(self, existing_eth0_10, new_eth1_11):
        self.assertFalse(existing_eth0_10.acquired)
        self.assertTrue(new_eth1_11.acquired)

    def assert_bridge_interfaces(self, existing_br0, new_br1):
        self.assertFalse(existing_br0.acquired)
        self.assertTrue(new_br1.acquired)

    def assert_bond_interfaces(self, existing_bond0, new_bond1):
        self.assertFalse(existing_bond0.acquired)
        self.assertTrue(new_bond1.acquired)


class TestUpdateInterfacesAcquiredController(
    TestUpdateInterfacesAcquiredDeployedNode
):
    def create_empty_node(self):
        return self.create_empty_controller()


class TestGetInterfaceDependencies(MAASTestCase):
    def test_all_physical(self):
        data = FakeCommissioningData()
        data.create_physical_network("eth0")
        data.create_physical_network("eno0")
        dependencies = get_interface_dependencies(data.render())
        self.assertEqual(
            {
                "eth0": [],
                "eno0": [],
            },
            dependencies,
        )

    def test_bridge(self):
        data = FakeCommissioningData()
        data.create_physical_network("eth0")
        data.create_physical_network("eth1")
        data.create_bridge_network("br0", parents=[data.networks["eth1"]])
        dependencies = get_interface_dependencies(data.render())
        self.assertEqual(
            {
                "eth0": [],
                "eth1": [],
                "br0": ["eth1"],
            },
            dependencies,
        )

    def test_bond(self):
        data = FakeCommissioningData()
        data.create_physical_network("eth0")
        data.create_physical_network("eth1")
        data.create_physical_network("eth2")
        data.create_bond_network(
            "bond0", parents=[data.networks["eth0"], data.networks["eth1"]]
        )
        dependencies = get_interface_dependencies(data.render())
        self.assertEqual(
            {
                "eth0": [],
                "eth1": [],
                "eth2": [],
                "bond0": ["eth0", "eth1"],
            },
            dependencies,
        )

    def test_vlan(self):
        data = FakeCommissioningData()
        data.create_physical_network("eth0")
        data.create_physical_network("eth1")
        data.create_vlan_network(
            "eth0.10", vid=10, parent=data.networks["eth0"]
        )
        dependencies = get_interface_dependencies(data.render())
        self.assertEqual(
            {
                "eth0": [],
                "eth1": [],
                "eth0.10": ["eth0"],
            },
            dependencies,
        )

    def test_complex(self):
        data = FakeCommissioningData()
        data.create_physical_network("eth0")
        data.create_physical_network("eth1")
        data.create_physical_network("eth2")
        data.create_physical_network("eth3")
        data.create_bridge_network("br0", parents=[data.networks["eth0"]])
        data.create_bond_network(
            "bond0", parents=[data.networks["eth1"], data.networks["eth2"]]
        )
        data.create_vlan_network(
            "bond0.10", vid=10, parent=data.networks["bond0"]
        )
        data.create_bridge_network(
            "br1", parents=[data.networks["bond0.10"], data.networks["eth3"]]
        )
        dependencies = get_interface_dependencies(data.render())
        self.assertEqual(
            {
                "eth0": [],
                "eth1": [],
                "eth2": [],
                "eth3": [],
                "br0": ["eth0"],
                "bond0": ["eth1", "eth2"],
                "bond0.10": ["bond0"],
                "br1": ["bond0.10", "eth3"],
            },
            dependencies,
        )

    def test_ignores_missing_parents(self):
        data = FakeCommissioningData()
        data.create_physical_network("eth0")
        data.create_physical_network("eth1")
        data.create_physical_network("eth2")
        data.create_physical_network("eth3")
        data.create_bridge_network("br0", parents=[data.networks["eth0"]])
        data.create_bond_network(
            "bond0", parents=[data.networks["eth1"], data.networks["eth2"]]
        )
        data.networks["bond0"].bond.lower_devices.append("missing1")
        data.create_vlan_network(
            "bond0.10", vid=10, parent=data.networks["bond0"]
        )
        data.networks["bond0.10"].vlan.lower_device = "missing2"
        data.create_bridge_network(
            "br1", parents=[data.networks["bond0.10"], data.networks["eth3"]]
        )
        data.networks["br1"].bridge.upper_devices.append("missing3")
        dependencies = get_interface_dependencies(data.render())
        self.assertEqual(
            {
                "eth0": [],
                "eth1": [],
                "eth2": [],
                "eth3": [],
                "br0": ["eth0"],
                "bond0": ["eth1", "eth2"],
                "bond0.10": [],
                "br1": ["bond0.10", "eth3"],
            },
            dependencies,
        )


class TestUpdateInterface(MAASServerTestCase):
    def test_update_interface_skips_ipoib_mac(self):
        node = factory.make_Node(with_boot_disk=False, interface=True)
        data = FakeCommissioningData()
        data.create_physical_network(
            "ibp4s0",
            mac_address="a0:00:02:20:fe:80:00:00:00:00:00:00:e4:1d:2d:03:00:4f:06:e1",
        )
        result = update_interface(
            node, "ibp4s0", data.render(), address_extra={}
        )
        self.assertIsNone(result)


class TestHardwareSyncNetworkDeviceNotify(MAASServerTestCase):
    def setup(self):
        details = EVENT_DETAILS[EVENT_TYPES.NODE_HARDWARE_SYNC_INTERFACE]
        EventType.objects.register(
            details.name, details.description, details.level
        )

    def test_hardware_sync_network_device_notify(self):
        node = factory.make_Node(
            enable_hw_sync=True, status=NODE_STATUS.DEPLOYED
        )
        interface = factory.make_Interface(node=node)
        _hardware_sync_network_device_notify(node, interface, "added")
        event = Event.objects.get(
            type__name=EVENT_TYPES.NODE_HARDWARE_SYNC_INTERFACE
        )
        self.assertEqual(event.action, "added")
        self.assertEqual(
            event.description,
            f"interface {interface.name} was added on node {node.system_id}",
        )
