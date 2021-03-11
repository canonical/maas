import json
import random
from unittest.mock import call

from testtools.matchers import (
    Contains,
    Equals,
    HasLength,
    Is,
    MatchesSetwise,
    MatchesStructure,
    Not,
)

from maasserver.enum import INTERFACE_TYPE, IPADDRESS_TYPE, NODE_TYPE
from maasserver.models.fabric import Fabric
from maasserver.models.interface import (
    BondInterface,
    BridgeInterface,
    Interface,
    PhysicalInterface,
    VLANInterface,
)
from maasserver.models.subnet import Subnet
from maasserver.models.vlan import VLAN
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import get_one, reload_object
from maastesting.matchers import MockCallsMatch
from metadataserver.builtin_scripts import network as network_module
from metadataserver.builtin_scripts.tests import test_hooks
from provisioningserver.refresh.node_info_scripts import LXD_OUTPUT_NAME


class UpdateInterfacesMixin:

    scenarios = (
        (
            "rack",
            dict(
                node_type=NODE_TYPE.RACK_CONTROLLER,
                with_beaconing=False,
                passes=1,
            ),
        ),
        (
            "region",
            dict(
                node_type=NODE_TYPE.REGION_CONTROLLER,
                with_beaconing=False,
                passes=2,
            ),
        ),
        (
            "region+rack",
            dict(
                node_type=NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                with_beaconing=False,
                passes=1,
            ),
        ),
        (
            "rack_with_beaconing",
            dict(
                node_type=NODE_TYPE.RACK_CONTROLLER,
                with_beaconing=True,
                passes=2,
            ),
        ),
        (
            "region_with_beaconing",
            dict(
                node_type=NODE_TYPE.REGION_CONTROLLER,
                with_beaconing=True,
                passes=1,
            ),
        ),
        (
            "region+rack_with_beaconing",
            dict(
                node_type=NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                with_beaconing=True,
                passes=2,
            ),
        ),
    )

    def create_empty_controller(self, **kwargs):
        return factory.make_Node(node_type=self.node_type, **kwargs).as_self()

    def update_interfaces(self, controller, interfaces, topology_hints=None):
        for _ in range(self.passes):
            if not self.with_beaconing:
                controller.update_interfaces(interfaces)
            else:
                controller.update_interfaces(
                    interfaces, topology_hints=None, create_fabrics=False
                )
                controller.update_interfaces(
                    interfaces,
                    topology_hints=topology_hints,
                    create_fabrics=True,
                )


class TestUpdateInterfaces(MAASServerTestCase, UpdateInterfacesMixin):

    scenarios = UpdateInterfacesMixin.scenarios

    def test_order_of_calls_to_update_interface_is_always_the_same(self):
        controller = self.create_empty_controller()
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "bond0": {
                "type": "bond",
                "mac_address": factory.make_mac_address(),
                "parents": ["eth1", "eth0"],
                "links": [],
                "enabled": True,
            },
            "bond0.10": {
                "type": "vlan",
                "vid": 10,
                "parents": ["bond0"],
                "links": [],
                "enabled": True,
            },
            "eth2": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            },
        }
        if not self.with_beaconing:
            expected_call_order = [
                call(
                    controller,
                    "eth0",
                    interfaces["eth0"],
                    create_fabrics=True,
                    hints=None,
                ),
                call(
                    controller,
                    "eth1",
                    interfaces["eth1"],
                    create_fabrics=True,
                    hints=None,
                ),
                call(
                    controller,
                    "eth2",
                    interfaces["eth2"],
                    create_fabrics=True,
                    hints=None,
                ),
                call(
                    controller,
                    "bond0",
                    interfaces["bond0"],
                    create_fabrics=True,
                    hints=None,
                ),
                call(
                    controller,
                    "bond0.10",
                    interfaces["bond0.10"],
                    create_fabrics=True,
                    hints=None,
                ),
            ] * self.passes
        else:
            expected_call_order = [
                call(
                    controller,
                    "eth0",
                    interfaces["eth0"],
                    create_fabrics=False,
                    hints=None,
                ),
                call(
                    controller,
                    "eth1",
                    interfaces["eth1"],
                    create_fabrics=False,
                    hints=None,
                ),
                call(
                    controller,
                    "eth2",
                    interfaces["eth2"],
                    create_fabrics=False,
                    hints=None,
                ),
                call(
                    controller,
                    "bond0",
                    interfaces["bond0"],
                    create_fabrics=False,
                    hints=None,
                ),
                call(
                    controller,
                    "bond0.10",
                    interfaces["bond0.10"],
                    create_fabrics=False,
                    hints=None,
                ),
                call(
                    controller,
                    "eth0",
                    interfaces["eth0"],
                    create_fabrics=True,
                    hints=None,
                ),
                call(
                    controller,
                    "eth1",
                    interfaces["eth1"],
                    create_fabrics=True,
                    hints=None,
                ),
                call(
                    controller,
                    "eth2",
                    interfaces["eth2"],
                    create_fabrics=True,
                    hints=None,
                ),
                call(
                    controller,
                    "bond0",
                    interfaces["bond0"],
                    create_fabrics=True,
                    hints=None,
                ),
                call(
                    controller,
                    "bond0.10",
                    interfaces["bond0.10"],
                    create_fabrics=True,
                    hints=None,
                ),
            ] * self.passes
        # Perform multiple times to make sure the call order is always
        # the same.
        for _ in range(5):
            mock_update_interface = self.patch(
                network_module, "update_interface"
            )
            self.update_interfaces(controller, interfaces)
            self.assertThat(
                mock_update_interface, MockCallsMatch(*expected_call_order)
            )

    def test_all_new_physical_interfaces_no_links(self):
        controller = self.create_empty_controller()
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": False,
            },
        }
        self.update_interfaces(controller, interfaces)
        eth0 = Interface.objects.get(name="eth0", node=controller)
        self.assertThat(
            eth0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
            ),
        )
        self.assertThat(list(eth0.parents.all()), Equals([]))
        eth1 = Interface.objects.get(name="eth1", node=controller)
        self.assertThat(
            eth1,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth1",
                mac_address=interfaces["eth1"]["mac_address"],
                enabled=False,
            ),
        )
        self.assertThat(list(eth1.parents.all()), Equals([]))
        # Since order is not kept in dictionary and it doesn't matter in this
        # case, we check that at least two different VLANs and one is the
        # default from the default fabric.
        observed_vlans = {eth0.vlan, eth1.vlan}
        self.assertThat(observed_vlans, HasLength(2))
        self.assertThat(
            observed_vlans,
            Contains(Fabric.objects.get_default_fabric().get_default_vlan()),
        )

    def test_vlans_with_alternate_naming_conventions(self):
        controller = self.create_empty_controller()
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "vlan0100": {
                "type": "vlan",
                "vid": 100,
                "mac_address": factory.make_mac_address(),
                "parents": ["eth0"],
                "links": [{"address": "192.168.0.1/24", "mode": "static"}],
                "enabled": True,
            },
            "vlan101": {
                "type": "vlan",
                "vid": 101,
                "mac_address": factory.make_mac_address(),
                "parents": ["eth0"],
                "links": [{"address": "192.168.0.2/24", "mode": "static"}],
                "enabled": True,
            },
            "eth0.0102": {
                "type": "vlan",
                "vid": 102,
                "mac_address": factory.make_mac_address(),
                "parents": ["eth0"],
                "links": [],
                "enabled": True,
            },
        }
        # Do this twice so we make sure we can both create and update.
        # And duplicate the code so it's easy to tell from a traceback which
        # failed.
        self._test_vlans_with_alternate_naming_conventions(
            controller, interfaces
        )
        self._test_vlans_with_alternate_naming_conventions(
            controller, interfaces
        )

    def _test_vlans_with_alternate_naming_conventions(
        self, controller, interfaces
    ):
        self.update_interfaces(controller, interfaces)
        eth0 = Interface.objects.get(name="eth0", node=controller)
        self.assertThat(
            eth0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                # Note: we expect the VLAN MAC to be ignored; VLAN interfaces
                # always inherit the parent MAC address.
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
            ),
        )
        self.assertThat(list(eth0.parents.all()), Equals([]))
        vlan0100 = Interface.objects.get(name="vlan0100", node=controller)
        self.assertThat(
            vlan0100,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="vlan0100",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
            ),
        )
        self.assertThat(list(vlan0100.parents.all()), Equals([eth0]))
        vlan101 = Interface.objects.get(name="vlan101", node=controller)
        self.assertThat(
            vlan101,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="vlan101",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
            ),
        )
        self.assertThat(list(vlan101.parents.all()), Equals([eth0]))
        eth0_0102 = Interface.objects.get(name="eth0.0102", node=controller)
        self.assertThat(
            eth0_0102,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.0102",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
            ),
        )
        self.assertThat(list(eth0_0102.parents.all()), Equals([eth0]))
        self.update_interfaces(controller, interfaces)
        eth0 = Interface.objects.get(name="eth0", node=controller)
        self.assertThat(
            eth0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                # Note: we expect the VLAN MAC to be ignored; VLAN interfaces
                # always inherit the parent MAC address.
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
            ),
        )
        self.assertThat(list(eth0.parents.all()), Equals([]))
        vlan0100 = Interface.objects.get(name="vlan0100", node=controller)
        self.assertThat(
            vlan0100,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="vlan0100",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
            ),
        )
        self.assertThat(list(vlan0100.parents.all()), Equals([eth0]))
        vlan101 = Interface.objects.get(name="vlan101", node=controller)
        self.assertThat(
            vlan101,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="vlan101",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
            ),
        )
        self.assertThat(list(vlan101.parents.all()), Equals([eth0]))
        eth0_0102 = Interface.objects.get(name="eth0.0102", node=controller)
        self.assertThat(
            eth0_0102,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.0102",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
            ),
        )
        self.assertThat(list(eth0_0102.parents.all()), Equals([eth0]))

    def test_sets_discovery_parameters(self):
        controller = self.create_empty_controller()
        eth0_mac = factory.make_mac_address()
        bond_mac = factory.make_mac_address()
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0_mac,
                "parents": [],
                "links": [],
                "enabled": True,
                "monitored": True,
            },
            "eth0.100": {
                "type": "vlan",
                "mac_address": eth0_mac,
                "parents": ["eth0"],
                "vid": 100,
                "links": [],
                "enabled": True,
                "monitored": False,
            },
            "bond0": {
                "type": "bond",
                "mac_address": bond_mac,
                "parents": [],
                "links": [],
                "enabled": False,
                "monitored": False,
            },
        }
        self.update_interfaces(controller, interfaces)
        eth0 = Interface.objects.get(name="eth0", node=controller)
        self.assertThat(
            eth0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                neighbour_discovery_state=True,
                mdns_discovery_state=True,
            ),
        )
        self.assertThat(list(eth0.parents.all()), Equals([]))
        eth0_vlan = Interface.objects.get(name="eth0.100", node=controller)
        self.assertThat(
            eth0_vlan,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.100",
                mac_address=interfaces["eth0.100"]["mac_address"],
                enabled=True,
                neighbour_discovery_state=False,
                mdns_discovery_state=True,
            ),
        )

    def test_clears_discovery_parameters(self):
        controller = self.create_empty_controller()
        eth0_mac = factory.make_mac_address()
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0_mac,
                "parents": [],
                "links": [],
                "enabled": True,
                "monitored": True,
            },
            "eth0.100": {
                "type": "vlan",
                "mac_address": eth0_mac,
                "parents": ["eth0"],
                "vid": 100,
                "links": [],
                "enabled": True,
                "monitored": False,
            },
        }
        self.update_interfaces(controller, interfaces)
        # Disable the interfaces so that we can make sure neighbour discovery
        # is properly disabled on update.
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0_mac,
                "parents": [],
                "links": [],
                "enabled": False,
                "monitored": False,
            },
            "eth0.100": {
                "type": "vlan",
                "mac_address": eth0_mac,
                "parents": ["eth0"],
                "vid": 100,
                "links": [],
                "enabled": False,
                "monitored": False,
            },
        }
        self.update_interfaces(controller, interfaces)
        eth0 = Interface.objects.get(name="eth0", node=controller)
        self.assertThat(
            eth0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=False,
                neighbour_discovery_state=False,
                mdns_discovery_state=True,
            ),
        )
        self.assertThat(list(eth0.parents.all()), Equals([]))
        eth0_vlan = Interface.objects.get(name="eth0.100", node=controller)
        self.assertThat(
            eth0_vlan,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.100",
                mac_address=interfaces["eth0.100"]["mac_address"],
                enabled=False,
                neighbour_discovery_state=False,
                mdns_discovery_state=True,
            ),
        )

    def test_new_physical_with_new_subnet_link(self):
        controller = self.create_empty_controller()
        network = factory.make_ip4_or_6_network()
        ip = factory.pick_ip_in_network(network)
        gateway_ip = factory.pick_ip_in_network(network, but_not=[ip])
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d" % (str(ip), network.prefixlen),
                        "gateway": str(gateway_ip),
                    }
                ],
                "enabled": True,
            }
        }
        self.update_interfaces(controller, interfaces)
        eth0 = Interface.objects.get(name="eth0", node=controller)
        default_vlan = Fabric.objects.get_default_fabric().get_default_vlan()
        self.assertThat(
            eth0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                vlan=default_vlan,
            ),
        )
        subnet = Subnet.objects.get(cidr=str(network.cidr))
        self.assertThat(
            subnet,
            MatchesStructure.byEquality(
                name=str(network.cidr),
                cidr=str(network.cidr),
                vlan=default_vlan,
                gateway_ip=gateway_ip,
            ),
        )
        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertThat(eth0_addresses, HasLength(1))
        self.assertThat(
            eth0_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet
            ),
        )

    def test_new_physical_with_dhcp_link(self):
        controller = self.create_empty_controller()
        network = factory.make_ip4_or_6_network()
        ip = factory.pick_ip_in_network(network)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [
                    {
                        "mode": "dhcp",
                        "address": "%s/%d" % (str(ip), network.prefixlen),
                    }
                ],
                "enabled": True,
            }
        }
        self.update_interfaces(controller, interfaces)
        eth0 = Interface.objects.get(name="eth0", node=controller)
        default_vlan = Fabric.objects.get_default_fabric().get_default_vlan()
        self.assertThat(
            eth0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                vlan=default_vlan,
            ),
        )
        dhcp_addresses = list(
            eth0.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.DHCP)
        )
        self.assertThat(dhcp_addresses, HasLength(1))
        self.assertThat(
            dhcp_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DHCP, ip=None
            ),
        )
        subnet = Subnet.objects.get(cidr=str(network.cidr))
        self.assertThat(
            subnet,
            MatchesStructure.byEquality(
                name=str(network.cidr),
                cidr=str(network.cidr),
                vlan=default_vlan,
            ),
        )
        discovered_addresses = list(
            eth0.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.DISCOVERED)
        )
        self.assertThat(discovered_addresses, HasLength(1))
        self.assertThat(
            discovered_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=ip, subnet=subnet
            ),
        )

    def test_new_physical_with_multiple_dhcp_link(self):
        controller = self.create_empty_controller()
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [{"mode": "dhcp"}, {"mode": "dhcp"}],
                "enabled": True,
            }
        }
        self.update_interfaces(controller, interfaces)
        eth0 = Interface.objects.get(name="eth0", node=controller)
        default_vlan = Fabric.objects.get_default_fabric().get_default_vlan()
        self.assertThat(
            eth0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                vlan=default_vlan,
            ),
        )
        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertThat(eth0_addresses, HasLength(2))
        self.assertThat(
            eth0_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DHCP, ip=None
            ),
        )
        self.assertThat(
            eth0_addresses[1],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DHCP, ip=None
            ),
        )

    def test_new_physical_with_multiple_dhcp_link_with_resource_info(self):
        controller = self.create_empty_controller(with_empty_script_sets=True)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": "00:00:00:00:00:01",
                "parents": [],
                "links": [{"mode": "dhcp"}, {"mode": "dhcp"}],
                "enabled": True,
            }
        }
        vendor = factory.make_name("vendor")
        product = factory.make_name("product")
        firmware_version = factory.make_name("firmware_version")

        lxd_script = (
            controller.current_commissioning_script_set.find_script_result(
                script_name=LXD_OUTPUT_NAME
            )
        )
        lxd_script_output = test_hooks.make_lxd_output()
        lxd_script_output["resources"]["network"] = {
            "cards": [
                {
                    "ports": [
                        {
                            "id": "eth0",
                            "address": "00:00:00:00:00:01",
                            "port": 0,
                        }
                    ],
                    "vendor": vendor,
                    "product": product,
                    "firmware_version": firmware_version,
                }
            ]
        }
        lxd_script.store_result(
            0, stdout=json.dumps(lxd_script_output).encode("utf-8")
        )
        self.update_interfaces(controller, interfaces)
        eth0 = Interface.objects.get(name="eth0", node=controller)
        self.assertEqual(vendor, eth0.vendor)
        self.assertEqual(product, eth0.product)
        self.assertEqual(firmware_version, eth0.firmware_version)

    def test_new_physical_with_existing_subnet_link_with_gateway(self):
        controller = self.create_empty_controller()
        subnet = factory.make_Subnet()
        network = subnet.get_ipnetwork()
        gateway_ip = factory.pick_ip_in_network(network)
        subnet.gateway_ip = gateway_ip
        subnet.save()
        ip = factory.pick_ip_in_network(network, but_not=[gateway_ip])
        diff_gateway_ip = factory.pick_ip_in_network(
            network, but_not=[gateway_ip, ip]
        )
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d" % (str(ip), network.prefixlen),
                        "gateway": str(diff_gateway_ip),
                    }
                ],
                "enabled": True,
            }
        }
        self.update_interfaces(controller, interfaces)
        eth0 = Interface.objects.get(name="eth0", node=controller)
        self.assertThat(
            eth0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                vlan=subnet.vlan,
            ),
        )
        # Check that the gateway IP didn't change.
        self.assertThat(
            subnet, MatchesStructure.byEquality(gateway_ip=gateway_ip)
        )
        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertThat(eth0_addresses, HasLength(1))
        self.assertThat(
            eth0_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet
            ),
        )

    def test_new_physical_with_existing_subnet_link_without_gateway(self):
        controller = self.create_empty_controller()
        subnet = factory.make_Subnet()
        subnet.gateway_ip = None
        subnet.save()
        network = subnet.get_ipnetwork()
        gateway_ip = factory.pick_ip_in_network(network)
        ip = factory.pick_ip_in_network(network, but_not=[gateway_ip])
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d" % (str(ip), network.prefixlen),
                        "gateway": str(gateway_ip),
                    }
                ],
                "enabled": True,
            }
        }
        self.update_interfaces(controller, interfaces)
        eth0 = Interface.objects.get(name="eth0", node=controller)
        self.assertThat(
            eth0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                vlan=subnet.vlan,
            ),
        )
        # Check that the gateway IP did get set.
        self.assertThat(
            reload_object(subnet),
            MatchesStructure.byEquality(gateway_ip=gateway_ip),
        )
        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertThat(eth0_addresses, HasLength(1))
        self.assertThat(
            eth0_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet
            ),
        )

    def test_new_physical_with_multiple_subnets(self):
        controller = self.create_empty_controller()
        vlan = factory.make_VLAN()
        subnet1 = factory.make_Subnet(vlan=vlan)
        ip1 = factory.pick_ip_in_Subnet(subnet1)
        subnet2 = factory.make_Subnet(vlan=vlan)
        ip2 = factory.pick_ip_in_Subnet(subnet2)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (str(ip1), subnet1.get_ipnetwork().prefixlen),
                    },
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (str(ip2), subnet2.get_ipnetwork().prefixlen),
                    },
                ],
                "enabled": True,
            }
        }
        self.update_interfaces(controller, interfaces)
        eth0 = Interface.objects.get(name="eth0", node=controller)
        self.assertThat(
            eth0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                vlan=vlan,
            ),
        )
        eth0_addresses = list(eth0.ip_addresses.order_by("id"))
        self.assertThat(eth0_addresses, HasLength(2))
        self.assertThat(
            eth0_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=ip1, subnet=subnet1
            ),
        )
        self.assertThat(
            eth0_addresses[1],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=ip2, subnet=subnet2
            ),
        )

    def test_existing_physical_with_existing_static_link(self):
        controller = self.create_empty_controller()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=ip,
            subnet=subnet,
            interface=interface,
        )
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (str(ip), subnet.get_ipnetwork().prefixlen),
                    }
                ],
                "enabled": True,
            }
        }
        self.update_interfaces(controller, interfaces)
        self.assertThat(controller.interface_set.count(), Equals(1))
        self.assertThat(
            reload_object(interface),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=vlan,
            ),
        )
        addresses = list(interface.ip_addresses.all())
        self.assertThat(addresses, HasLength(1))
        self.assertThat(
            addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet
            ),
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
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (str(ip), subnet.get_ipnetwork().prefixlen),
                    }
                ],
                "enabled": True,
            }
        }
        self.update_interfaces(controller, interfaces)
        self.assertThat(controller.interface_set.count(), Equals(1))
        self.assertThat(
            reload_object(interface),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=vlan,
            ),
        )
        addresses = list(interface.ip_addresses.all())
        self.assertThat(addresses, HasLength(1))
        self.assertThat(
            addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet
            ),
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
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (str(ip), subnet.get_ipnetwork().prefixlen),
                    }
                ],
                "enabled": True,
            }
        }
        self.update_interfaces(controller, interfaces)
        self.assertThat(controller.interface_set.count(), Equals(1))
        self.assertThat(
            reload_object(interface),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=vlan,
            ),
        )
        addresses = list(interface.ip_addresses.all())
        self.assertThat(addresses, HasLength(1))
        self.assertThat(
            addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet
            ),
        )
        for extra_ip in extra_ips:
            self.expectThat(reload_object(extra_ip), Is(None))

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
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (str(ip), subnet.get_ipnetwork().prefixlen),
                    }
                ],
                "enabled": True,
            }
        }
        interfaces["eth0.%d" % vid_on_fabric] = {
            "type": "vlan",
            "parents": ["eth0"],
            "links": [],
            "enabled": True,
            "vid": vid_on_fabric,
        }
        self.update_interfaces(controller, interfaces)
        self.assertThat(controller.interface_set.count(), Equals(2))
        self.assertThat(
            reload_object(interface),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=vlan,
            ),
        )
        addresses = list(interface.ip_addresses.all())
        self.assertThat(addresses, HasLength(1))
        self.assertThat(
            addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet
            ),
        )
        created_vlan = VLAN.objects.get(fabric=fabric, vid=vid_on_fabric)
        vlan_interface = VLANInterface.objects.get(
            node=controller, vlan=created_vlan
        )
        self.assertThat(
            vlan_interface,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.%d" % vid_on_fabric,
                enabled=True,
                vlan=created_vlan,
            ),
        )

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
        vlan_network = factory.make_ip4_or_6_network()
        vlan_ip = factory.pick_ip_in_network(vlan_network)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (str(ip), subnet.get_ipnetwork().prefixlen),
                    }
                ],
                "enabled": True,
            }
        }
        interfaces["eth0.%d" % vid_on_fabric] = {
            "type": "vlan",
            "parents": ["eth0"],
            "links": [
                {
                    "mode": "static",
                    "address": "%s/%d"
                    % (str(vlan_ip), vlan_network.prefixlen),
                }
            ],
            "enabled": True,
            "vid": vid_on_fabric,
        }
        self.update_interfaces(controller, interfaces)
        self.assertThat(controller.interface_set.count(), Equals(2))
        self.assertThat(
            reload_object(interface),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=vlan,
            ),
        )
        parent_addresses = list(interface.ip_addresses.all())
        self.assertThat(parent_addresses, HasLength(1))
        self.assertThat(
            parent_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet
            ),
        )
        created_vlan = VLAN.objects.get(fabric=fabric, vid=vid_on_fabric)
        vlan_interface = VLANInterface.objects.get(
            node=controller, vlan=created_vlan
        )
        self.assertThat(
            vlan_interface,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.%d" % vid_on_fabric,
                enabled=True,
                vlan=created_vlan,
            ),
        )
        vlan_subnet = Subnet.objects.get(cidr=str(vlan_network.cidr))
        self.assertThat(
            vlan_subnet,
            MatchesStructure.byEquality(
                name=str(vlan_network.cidr),
                cidr=str(vlan_network.cidr),
                vlan=created_vlan,
            ),
        )
        vlan_addresses = list(vlan_interface.ip_addresses.all())
        self.assertThat(vlan_addresses, HasLength(1))
        self.assertThat(
            vlan_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=vlan_ip,
                subnet=vlan_subnet,
            ),
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
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (str(ip), subnet.get_ipnetwork().prefixlen),
                    }
                ],
                "enabled": True,
            }
        }
        interfaces["eth0.%d" % vid_on_fabric] = {
            "type": "vlan",
            "parents": ["eth0"],
            "links": [
                {
                    "mode": "static",
                    "address": "%s/%d"
                    % (str(vlan_ip), other_subnet.get_ipnetwork().prefixlen),
                }
            ],
            "enabled": True,
            "vid": vid_on_fabric,
        }
        maaslog = self.patch(network_module, "maaslog")
        self.update_interfaces(controller, interfaces)
        self.assertThat(controller.interface_set.count(), Equals(2))
        self.assertThat(
            reload_object(interface),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=vlan,
            ),
        )
        parent_addresses = list(interface.ip_addresses.all())
        self.assertThat(parent_addresses, HasLength(1))
        self.assertThat(
            parent_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet
            ),
        )
        self.assertFalse(
            VLAN.objects.filter(fabric=fabric, vid=vid_on_fabric).exists()
        )
        other_vlan = other_subnet.vlan
        vlan_interface = VLANInterface.objects.get(
            node=controller, vlan=other_vlan
        )
        self.assertThat(
            vlan_interface,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.%d" % vid_on_fabric,
                enabled=True,
                vlan=other_vlan,
            ),
        )
        self.assertEqual(vlan_interface.ip_addresses.count(), 1)
        self.assertThat(
            maaslog.error,
            MockCallsMatch(
                *[
                    call(
                        f"Interface 'eth0' on controller '{controller.hostname}' "
                        f"is not on the same fabric as VLAN interface '{vlan_interface.name}'."
                    ),
                    call(
                        f"VLAN interface '{vlan_interface.name}' reports VLAN {vid_on_fabric} "
                        f"but links are on VLAN {other_vlan.vid}"
                    ),
                ]
                * self.passes
            ),
        )

    def test_existing_physical_with_no_links_new_vlan_no_links(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        vid_on_fabric = random.randint(1, 4094)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            }
        }
        interfaces["eth0.%d" % vid_on_fabric] = {
            "type": "vlan",
            "parents": ["eth0"],
            "links": [],
            "enabled": True,
            "vid": vid_on_fabric,
        }
        self.update_interfaces(controller, interfaces)
        self.assertThat(controller.interface_set.count(), Equals(2))
        self.assertThat(
            reload_object(interface),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=vlan,
            ),
        )
        created_vlan = VLAN.objects.get(fabric=fabric, vid=vid_on_fabric)
        vlan_interface = VLANInterface.objects.get(
            node=controller, vlan=created_vlan
        )
        self.assertThat(
            vlan_interface,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.%d" % vid_on_fabric,
                enabled=True,
                vlan=created_vlan,
            ),
        )

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
        ip = factory.pick_ip_in_Subnet(subnet)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            }
        }
        interfaces["eth0.%d" % new_vlan.vid] = {
            "type": "vlan",
            "parents": ["eth0"],
            "links": [
                {
                    "mode": "static",
                    "address": "%s/%d"
                    % (str(ip), subnet.get_ipnetwork().prefixlen),
                }
            ],
            "enabled": True,
            "vid": new_vlan.vid,
        }
        maaslog = self.patch(network_module, "maaslog")
        self.update_interfaces(controller, interfaces)
        self.assertThat(controller.interface_set.count(), Equals(2))
        self.assertThat(
            reload_object(interface),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=fabric.get_default_vlan(),
            ),
        )
        vlan_interface = VLANInterface.objects.get(
            node=controller, vlan=new_vlan
        )
        self.assertThat(
            vlan_interface,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.%d" % new_vlan.vid,
                enabled=True,
                vlan=new_vlan,
            ),
        )
        vlan_addresses = list(vlan_interface.ip_addresses.all())
        self.assertThat(vlan_addresses, HasLength(1))
        self.assertThat(
            vlan_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet
            ),
        )
        self.assertThat(
            maaslog.error,
            MockCallsMatch(
                *[
                    call(
                        f"Interface 'eth0' on controller '{controller.hostname}' "
                        f"is not on the same fabric as VLAN interface '{vlan_interface.name}'."
                    )
                ]
                * self.passes
            ),
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
        ip = factory.pick_ip_in_Subnet(new_subnet)
        links_to_remove = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.STICKY, interface=vlan_interface
            )
            for _ in range(3)
        ]
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            }
        }
        interfaces["eth0.%d" % other_vlan.vid] = {
            "type": "vlan",
            "parents": ["eth0"],
            "links": [
                {
                    "mode": "static",
                    "address": "%s/%d"
                    % (str(ip), new_subnet.get_ipnetwork().prefixlen),
                }
            ],
            "enabled": True,
            "vid": other_vlan.vid,
        }
        maaslog = self.patch(network_module, "maaslog")
        self.update_interfaces(controller, interfaces)
        self.assertThat(controller.interface_set.count(), Equals(2))
        self.assertThat(
            reload_object(interface),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=vlan,
            ),
        )
        self.assertThat(
            reload_object(vlan_interface),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.%d" % other_vlan.vid,
                enabled=True,
                vlan=new_vlan,
            ),
        )
        self.assertCountEqual(
            vlan_interface.ip_addresses.values_list("ip", flat=True), [ip]
        )
        self.assertThat(
            maaslog.error,
            MockCallsMatch(
                *[
                    call(
                        f"Interface 'eth0' on controller '{controller.hostname}' "
                        f"is not on the same fabric as VLAN interface '{vlan_interface.name}'."
                    ),
                    call(
                        f"VLAN interface '{vlan_interface.name}' reports VLAN {other_vlan.vid} "
                        f"but links are on VLAN {new_vlan.vid}"
                    ),
                ]
                * self.passes
            ),
        )
        for link in links_to_remove:
            self.expectThat(reload_object(link), Is(None))

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
        vlan_ip = factory.pick_ip_in_Subnet(vlan_subnet)
        vlan_interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN,
            vlan=new_vlan,
            parents=[interface],
        )
        vlan_name = vlan_interface.name

        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            vlan_name: {
                "type": "vlan",
                "parents": ["eth0"],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (
                            str(vlan_ip),
                            vlan_subnet.get_ipnetwork().prefixlen,
                        ),
                    }
                ],
                "enabled": True,
                "vid": new_vlan.vid,
            },
        }
        self.update_interfaces(controller, interfaces)
        self.assertThat(controller.interface_set.count(), Equals(2))
        self.assertThat(
            reload_object(interface),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=vlan,
            ),
        )
        self.assertThat(
            reload_object(vlan_interface),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name=vlan_name,
                enabled=True,
                vlan=new_vlan,
            ),
        )
        vlan_addresses = list(vlan_interface.ip_addresses.all())
        self.assertThat(vlan_addresses, HasLength(1))
        self.assertThat(
            vlan_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=vlan_ip,
                subnet=vlan_subnet,
            ),
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
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": eth1.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "bond0": {
                "type": "bond",
                "mac_address": factory.make_mac_address(),
                "parents": ["eth0", "eth1"],
                "links": [],
                "enabled": True,
            },
        }
        self.update_interfaces(controller, interfaces)
        self.assertThat(controller.interface_set.count(), Equals(3))
        bond_interface = BondInterface.objects.get(
            node=controller, mac_address=interfaces["bond0"]["mac_address"]
        )
        self.assertThat(
            bond_interface,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.BOND,
                name="bond0",
                mac_address=interfaces["bond0"]["mac_address"],
                enabled=True,
                vlan=vlan,
            ),
        )
        self.assertThat(
            [parent.name for parent in bond_interface.parents.all()],
            MatchesSetwise(Equals("eth0"), Equals("eth1")),
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
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": eth1.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "br0": {
                "type": "bridge",
                "mac_address": factory.make_mac_address(),
                "parents": ["eth0", "eth1"],
                "links": [],
                "enabled": True,
            },
        }
        self.update_interfaces(controller, interfaces)
        self.assertThat(controller.interface_set.count(), Equals(3))
        bond_interface = BridgeInterface.objects.get(
            node=controller, mac_address=interfaces["br0"]["mac_address"]
        )
        self.assertThat(
            bond_interface,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.BRIDGE,
                name="br0",
                mac_address=interfaces["br0"]["mac_address"],
                enabled=True,
                vlan=vlan,
            ),
        )
        self.assertThat(
            [parent.name for parent in bond_interface.parents.all()],
            MatchesSetwise(Equals("eth0"), Equals("eth1")),
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
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND,
            vlan=vlan,
            parents=[eth0, eth1],
            node=controller,
            name="bond0",
            mac_address=factory.make_mac_address(),
        )
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": eth1.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "bond0": {
                "type": "bond",
                "mac_address": factory.make_mac_address(),
                "parents": ["eth0"],
                "links": [],
                "enabled": True,
            },
        }
        self.update_interfaces(controller, interfaces)
        self.assertThat(controller.interface_set.count(), Equals(3))
        self.assertThat(
            reload_object(bond0),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.BOND,
                name="bond0",
                mac_address=interfaces["bond0"]["mac_address"],
                enabled=True,
                vlan=vlan,
            ),
        )
        self.assertThat(
            [parent.name for parent in bond0.parents.all()], Equals(["eth0"])
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
        br0 = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE,
            vlan=vlan,
            parents=[eth0, eth1],
            node=controller,
            name="br0",
            mac_address=factory.make_mac_address(),
        )
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": eth1.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "br0": {
                "type": "bridge",
                "mac_address": factory.make_mac_address(),
                "parents": ["eth0"],
                "links": [],
                "enabled": True,
            },
        }
        self.update_interfaces(controller, interfaces)
        self.assertThat(controller.interface_set.count(), Equals(3))
        self.assertThat(
            reload_object(br0),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.BRIDGE,
                name="br0",
                mac_address=interfaces["br0"]["mac_address"],
                enabled=True,
                vlan=vlan,
            ),
        )
        self.assertThat(
            [parent.name for parent in br0.parents.all()], Equals(["eth0"])
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
        ip = factory.pick_ip_in_Subnet(subnet)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": eth1.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "bond0": {
                "type": "bond",
                "mac_address": bond0.mac_address,
                "parents": ["eth0", "eth1"],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (str(ip), subnet.get_ipnetwork().prefixlen),
                    }
                ],
                "enabled": True,
            },
        }
        self.update_interfaces(controller, interfaces)
        self.assertThat(controller.interface_set.count(), Equals(3))
        self.assertThat(
            reload_object(eth0),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=eth0.mac_address,
                enabled=True,
                vlan=bond0_vlan,
            ),
        )
        self.assertThat(
            reload_object(eth1),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth1",
                mac_address=eth1.mac_address,
                enabled=True,
                vlan=bond0_vlan,
            ),
        )
        bond0 = get_one(Interface.objects.filter_by_ip(str(ip)))
        self.assertThat(
            bond0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.BOND,
                name="bond0",
                mac_address=bond0.mac_address,
                enabled=True,
                node=controller,
                vlan=bond0_vlan,
            ),
        )
        self.assertThat(
            [parent.name for parent in bond0.parents.all()],
            MatchesSetwise(Equals("eth0"), Equals("eth1")),
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
        ip = factory.pick_ip_in_Subnet(subnet)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": eth1.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "br0": {
                "type": "bridge",
                "mac_address": br0.mac_address,
                "parents": ["eth0", "eth1"],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (str(ip), subnet.get_ipnetwork().prefixlen),
                    }
                ],
                "enabled": True,
            },
        }
        self.update_interfaces(controller, interfaces)
        self.assertThat(controller.interface_set.count(), Equals(3))
        self.assertThat(
            reload_object(eth0),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=eth0.mac_address,
                enabled=True,
                vlan=br0_vlan,
            ),
        )
        self.assertThat(
            reload_object(eth1),
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth1",
                mac_address=eth1.mac_address,
                enabled=True,
                vlan=br0_vlan,
            ),
        )
        br0 = get_one(Interface.objects.filter_by_ip(str(ip)))
        self.assertThat(
            br0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.BRIDGE,
                name="br0",
                mac_address=br0.mac_address,
                enabled=True,
                node=controller,
                vlan=br0_vlan,
            ),
        )
        self.assertThat(
            [parent.name for parent in br0.parents.all()],
            MatchesSetwise(Equals("eth0"), Equals("eth1")),
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
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "br0": {
                "type": "bridge",
                "mac_address": mac_address,
                "parents": ["eth0"],
                "links": [],
                "enabled": True,
            },
        }

        vendor = factory.make_name("vendor")
        product = factory.make_name("product")
        firmware_version = factory.make_name("firmware_version")

        lxd_script = (
            controller.current_commissioning_script_set.find_script_result(
                script_name=LXD_OUTPUT_NAME
            )
        )
        lxd_script_output = {
            "network": {
                "cards": [
                    {
                        "ports": [
                            {"id": "eth0", "address": mac_address, "port": 0}
                        ],
                        "vendor": vendor,
                        "product": product,
                        "firmware_version": firmware_version,
                    }
                ]
            }
        }
        lxd_script.store_result(
            0, stdout=json.dumps(lxd_script_output).encode("utf-8")
        )
        self.update_interfaces(controller, interfaces)
        br0 = Interface.objects.get(name="br0", node=controller)
        self.assertNotEqual(vendor, br0.vendor)
        self.assertNotEqual(product, br0.product)
        self.assertNotEqual(firmware_version, br0.firmware_version)

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
        controller.update_interfaces({})
        self.assertThat(reload_object(eth0), Is(None))
        self.assertThat(reload_object(eth1), Is(None))
        self.assertThat(reload_object(bond0), Is(None))

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
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "bond0": {
                "type": "bond",
                "mac_address": bond0.mac_address,
                "parents": ["eth0"],
                "links": [],
                "enabled": True,
            },
        }
        self.update_interfaces(controller, interfaces)
        self.assertThat(reload_object(eth0), Not(Is(None)))
        self.assertThat(reload_object(eth1), Is(None))
        self.assertThat(reload_object(bond0), Not(Is(None)))

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
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "br0": {
                "type": "bridge",
                "mac_address": br0.mac_address,
                "parents": ["eth0"],
                "links": [],
                "enabled": True,
            },
        }
        self.update_interfaces(controller, interfaces)
        self.assertThat(reload_object(eth0), Not(Is(None)))
        self.assertThat(reload_object(eth1), Is(None))
        self.assertThat(reload_object(br0), Not(Is(None)))

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
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            }
        }
        self.update_interfaces(controller, interfaces)
        self.assertThat(reload_object(eth0), Not(Is(None)))
        self.assertThat(reload_object(eth1), Is(None))
        self.assertThat(reload_object(bond0), Is(None))

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
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            }
        }
        self.update_interfaces(controller, interfaces)
        self.assertThat(reload_object(eth0), Not(Is(None)))
        self.assertThat(reload_object(eth1), Is(None))
        self.assertThat(reload_object(br0), Is(None))

    def test_all_new_bond_with_vlan(self):
        controller = self.create_empty_controller()
        bond0_fabric = factory.make_Fabric()
        bond0_untagged = bond0_fabric.get_default_vlan()
        bond0_subnet = factory.make_Subnet(vlan=bond0_untagged)
        bond0_ip = factory.pick_ip_in_Subnet(bond0_subnet)
        bond0_vlan = factory.make_VLAN(fabric=bond0_fabric)
        bond0_vlan_subnet = factory.make_Subnet(vlan=bond0_vlan)
        bond0_vlan_ip = factory.pick_ip_in_Subnet(bond0_vlan_subnet)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "bond0": {
                "type": "bond",
                "mac_address": factory.make_mac_address(),
                "parents": ["eth0", "eth1"],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (
                            str(bond0_ip),
                            bond0_subnet.get_ipnetwork().prefixlen,
                        ),
                    }
                ],
                "enabled": True,
            },
        }
        interfaces["bond0.%d" % bond0_vlan.vid] = {
            "type": "vlan",
            "parents": ["bond0"],
            "links": [
                {
                    "mode": "static",
                    "address": "%s/%d"
                    % (
                        str(bond0_vlan_ip),
                        bond0_vlan_subnet.get_ipnetwork().prefixlen,
                    ),
                }
            ],
            "vid": bond0_vlan.vid,
            "enabled": True,
        }
        self.update_interfaces(controller, interfaces)
        eth0 = PhysicalInterface.objects.get(
            node=controller, mac_address=interfaces["eth0"]["mac_address"]
        )
        self.assertThat(
            eth0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                vlan=bond0_untagged,
            ),
        )
        eth1 = PhysicalInterface.objects.get(
            node=controller, mac_address=interfaces["eth1"]["mac_address"]
        )
        self.assertThat(
            eth1,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth1",
                mac_address=interfaces["eth1"]["mac_address"],
                enabled=True,
                vlan=bond0_untagged,
            ),
        )
        bond0 = BondInterface.objects.get(
            node=controller, mac_address=interfaces["bond0"]["mac_address"]
        )
        self.assertThat(
            bond0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.BOND,
                name="bond0",
                mac_address=interfaces["bond0"]["mac_address"],
                enabled=True,
                vlan=bond0_untagged,
            ),
        )
        self.assertThat(
            [parent.name for parent in bond0.parents.all()],
            MatchesSetwise(Equals("eth0"), Equals("eth1")),
        )
        bond0_addresses = list(bond0.ip_addresses.all())
        self.assertThat(bond0_addresses, HasLength(1))
        self.assertThat(
            bond0_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=bond0_ip,
                subnet=bond0_subnet,
            ),
        )
        bond0_vlan_nic = VLANInterface.objects.get(
            node=controller, vlan=bond0_vlan
        )
        self.assertThat(
            bond0_vlan_nic,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="bond0.%d" % bond0_vlan.vid,
                enabled=True,
                vlan=bond0_vlan,
            ),
        )
        self.assertThat(
            [parent.name for parent in bond0_vlan_nic.parents.all()],
            Equals(["bond0"]),
        )
        bond0_vlan_nic_addresses = list(bond0_vlan_nic.ip_addresses.all())
        self.assertThat(bond0_vlan_nic_addresses, HasLength(1))
        self.assertThat(
            bond0_vlan_nic_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=bond0_vlan_ip,
                subnet=bond0_vlan_subnet,
            ),
        )

    def test_all_new_bridge_with_vlan(self):
        controller = self.create_empty_controller()
        br0_fabric = factory.make_Fabric()
        br0_untagged = br0_fabric.get_default_vlan()
        br0_subnet = factory.make_Subnet(vlan=br0_untagged)
        br0_ip = factory.pick_ip_in_Subnet(br0_subnet)
        br0_vlan = factory.make_VLAN(fabric=br0_fabric)
        br0_vlan_subnet = factory.make_Subnet(vlan=br0_vlan)
        br0_vlan_ip = factory.pick_ip_in_Subnet(br0_vlan_subnet)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "br0": {
                "type": "bridge",
                "mac_address": factory.make_mac_address(),
                "parents": ["eth0", "eth1"],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (str(br0_ip), br0_subnet.get_ipnetwork().prefixlen),
                    }
                ],
                "enabled": True,
            },
        }
        interfaces["br0.%d" % br0_vlan.vid] = {
            "type": "vlan",
            "parents": ["br0"],
            "links": [
                {
                    "mode": "static",
                    "address": "%s/%d"
                    % (
                        str(br0_vlan_ip),
                        br0_vlan_subnet.get_ipnetwork().prefixlen,
                    ),
                }
            ],
            "vid": br0_vlan.vid,
            "enabled": True,
        }
        self.update_interfaces(controller, interfaces)
        eth0 = PhysicalInterface.objects.get(
            node=controller, mac_address=interfaces["eth0"]["mac_address"]
        )
        self.assertThat(
            eth0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                vlan=br0_untagged,
            ),
        )
        eth1 = PhysicalInterface.objects.get(
            node=controller, mac_address=interfaces["eth1"]["mac_address"]
        )
        self.assertThat(
            eth1,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth1",
                mac_address=interfaces["eth1"]["mac_address"],
                enabled=True,
                vlan=br0_untagged,
            ),
        )
        br0 = BridgeInterface.objects.get(
            node=controller, mac_address=interfaces["br0"]["mac_address"]
        )
        self.assertThat(
            br0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.BRIDGE,
                name="br0",
                mac_address=interfaces["br0"]["mac_address"],
                enabled=True,
                vlan=br0_untagged,
            ),
        )
        self.assertThat(
            [parent.name for parent in br0.parents.all()],
            MatchesSetwise(Equals("eth0"), Equals("eth1")),
        )
        br0_addresses = list(br0.ip_addresses.all())
        self.assertThat(br0_addresses, HasLength(1))
        self.assertThat(
            br0_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=br0_ip, subnet=br0_subnet
            ),
        )
        br0_vlan_nic = VLANInterface.objects.get(
            node=controller, vlan=br0_vlan
        )
        self.assertThat(
            br0_vlan_nic,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="br0.%d" % br0_vlan.vid,
                enabled=True,
                vlan=br0_vlan,
            ),
        )
        self.assertThat(
            [parent.name for parent in br0_vlan_nic.parents.all()],
            Equals(["br0"]),
        )
        br0_vlan_nic_addresses = list(br0_vlan_nic.ip_addresses.all())
        self.assertThat(br0_vlan_nic_addresses, HasLength(1))
        self.assertThat(
            br0_vlan_nic_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=br0_vlan_ip,
                subnet=br0_vlan_subnet,
            ),
        )

    def test_two_controllers_with_similar_configurations_bug_1563701(self):
        interfaces1 = {
            "ens3": {
                "enabled": True,
                "links": [{"address": "10.2.0.2/20", "mode": "static"}],
                "mac_address": "52:54:00:ff:0a:cf",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
            "ens4": {
                "enabled": True,
                "links": [
                    {
                        "address": "192.168.35.43/22",
                        "gateway": "192.168.32.2",
                        "mode": "dhcp",
                    }
                ],
                "mac_address": "52:54:00:ab:da:de",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
            "ens5": {
                "enabled": True,
                "links": [],
                "mac_address": "52:54:00:70:8f:5b",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
            "ens5.10": {
                "enabled": True,
                "links": [{"address": "10.10.0.2/20", "mode": "static"}],
                "parents": ["ens5"],
                "source": "ipaddr",
                "type": "vlan",
                "vid": 10,
            },
            "ens5.11": {
                "enabled": True,
                "links": [{"address": "10.11.0.2/20", "mode": "static"}],
                "parents": ["ens5"],
                "source": "ipaddr",
                "type": "vlan",
                "vid": 11,
            },
            "ens5.12": {
                "enabled": True,
                "links": [{"address": "10.12.0.2/20", "mode": "static"}],
                "parents": ["ens5"],
                "source": "ipaddr",
                "type": "vlan",
                "vid": 12,
            },
            "ens5.13": {
                "enabled": True,
                "links": [{"address": "10.13.0.2/20", "mode": "static"}],
                "parents": ["ens5"],
                "source": "ipaddr",
                "type": "vlan",
                "vid": 13,
            },
            "ens5.14": {
                "enabled": True,
                "links": [{"address": "10.14.0.2/20", "mode": "static"}],
                "parents": ["ens5"],
                "source": "ipaddr",
                "type": "vlan",
                "vid": 14,
            },
            "ens5.15": {
                "enabled": True,
                "links": [{"address": "10.15.0.2/20", "mode": "static"}],
                "parents": ["ens5"],
                "source": "ipaddr",
                "type": "vlan",
                "vid": 15,
            },
            "ens5.16": {
                "enabled": True,
                "links": [{"address": "10.16.0.2/20", "mode": "static"}],
                "parents": ["ens5"],
                "source": "ipaddr",
                "type": "vlan",
                "vid": 16,
            },
        }

        interfaces2 = {
            "ens3": {
                "enabled": True,
                "links": [{"address": "10.2.0.3/20", "mode": "static"}],
                "mac_address": "52:54:00:02:eb:bc",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
            "ens4": {
                "enabled": True,
                "links": [
                    {
                        "address": "192.168.33.246/22",
                        "gateway": "192.168.32.2",
                        "mode": "dhcp",
                    }
                ],
                "mac_address": "52:54:00:bc:b0:85",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
            "ens5": {
                "enabled": True,
                "links": [],
                "mac_address": "52:54:00:cf:f3:7f",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
            "ens5.10": {
                "enabled": True,
                "links": [{"address": "10.10.0.3/20", "mode": "static"}],
                "parents": ["ens5"],
                "source": "ipaddr",
                "type": "vlan",
                "vid": 10,
            },
            "ens5.11": {
                "enabled": True,
                "links": [{"address": "10.11.0.3/20", "mode": "static"}],
                "parents": ["ens5"],
                "source": "ipaddr",
                "type": "vlan",
                "vid": 11,
            },
            "ens5.12": {
                "enabled": True,
                "links": [{"address": "10.12.0.3/20", "mode": "static"}],
                "parents": ["ens5"],
                "source": "ipaddr",
                "type": "vlan",
                "vid": 12,
            },
            "ens5.13": {
                "enabled": True,
                "links": [{"address": "10.13.0.3/20", "mode": "static"}],
                "parents": ["ens5"],
                "source": "ipaddr",
                "type": "vlan",
                "vid": 13,
            },
            "ens5.14": {
                "enabled": True,
                "links": [{"address": "10.14.0.3/20", "mode": "static"}],
                "parents": ["ens5"],
                "source": "ipaddr",
                "type": "vlan",
                "vid": 14,
            },
            "ens5.15": {
                "enabled": True,
                "links": [{"address": "10.15.0.3/20", "mode": "static"}],
                "parents": ["ens5"],
                "source": "ipaddr",
                "type": "vlan",
                "vid": 15,
            },
            "ens5.16": {
                "enabled": True,
                "links": [{"address": "10.16.0.3/20", "mode": "static"}],
                "parents": ["ens5"],
                "source": "ipaddr",
                "type": "vlan",
                "vid": 16,
            },
        }
        controller1 = self.create_empty_controller()
        controller2 = self.create_empty_controller()
        controller1.update_interfaces(interfaces1)
        controller2.update_interfaces(interfaces2)
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
        br0_ip = factory.pick_ip_in_Subnet(br0_subnet)
        eth0_mac = factory.make_mac_address()
        br1_fabric = factory.make_Fabric()
        eth1_100_vlan = factory.make_VLAN(vid=100, fabric=br1_fabric)
        br1_subnet = factory.make_Subnet(vlan=eth1_100_vlan)
        br1_ip = factory.pick_ip_in_Subnet(br1_subnet)
        eth1_mac = factory.make_mac_address()
        eth0_101_vlan = factory.make_VLAN(vid=101, fabric=br1_fabric)
        br101_subnet = factory.make_Subnet(vlan=eth0_101_vlan)
        br101_ip = factory.pick_ip_in_Subnet(br101_subnet)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0_mac,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth0.100": {
                "type": "vlan",
                "vid": 100,
                "mac_address": eth0_mac,
                "parents": ["eth0"],
                "links": [],
                "enabled": True,
            },
            "eth0.101": {
                "type": "vlan",
                "vid": 101,
                "mac_address": eth0_mac,
                "parents": ["eth0"],
                "links": [],
                "enabled": True,
            },
            "br0": {
                "type": "bridge",
                "mac_address": eth0_mac,
                "parents": ["eth0.100"],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (str(br0_ip), br0_subnet.get_ipnetwork().prefixlen),
                    }
                ],
                "enabled": True,
            },
            "br101": {
                "type": "bridge",
                "mac_address": eth0_mac,
                "parents": ["eth0.101"],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (
                            str(br101_ip),
                            br101_subnet.get_ipnetwork().prefixlen,
                        ),
                    }
                ],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": eth1_mac,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1.100": {
                "type": "vlan",
                "vid": 100,
                "mac_address": eth1_mac,
                "parents": ["eth1"],
                "links": [],
                "enabled": True,
            },
            "br1": {
                "type": "bridge",
                "mac_address": eth1_mac,
                "parents": ["eth1.100"],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (str(br1_ip), br1_subnet.get_ipnetwork().prefixlen),
                    }
                ],
                "enabled": True,
            },
        }
        self.update_interfaces(controller, interfaces)
        eth0 = PhysicalInterface.objects.get(
            node=controller, mac_address=interfaces["eth0"]["mac_address"]
        )
        self.assertThat(
            eth0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                vlan=default_vlan,
            ),
        )
        eth0_100 = VLANInterface.objects.get(
            node=controller,
            name="eth0.100",
            mac_address=interfaces["eth0.100"]["mac_address"],
        )
        self.assertThat(
            eth0_100,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.100",
                mac_address=interfaces["eth0.100"]["mac_address"],
                enabled=True,
                vlan=eth0_100_vlan,
            ),
        )
        br0 = BridgeInterface.objects.get(
            node=controller,
            name="br0",
            mac_address=interfaces["br0"]["mac_address"],
        )
        self.assertThat(
            br0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.BRIDGE,
                name="br0",
                mac_address=interfaces["br0"]["mac_address"],
                enabled=True,
                vlan=eth0_100_vlan,
            ),
        )
        br0_addresses = list(br0.ip_addresses.all())
        self.assertThat(br0_addresses, HasLength(1))
        self.assertThat(
            br0_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=br0_ip, subnet=br0_subnet
            ),
        )
        br0_nic = BridgeInterface.objects.get(
            node=controller, vlan=eth0_100_vlan
        )
        self.assertThat(
            br0_nic,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.BRIDGE,
                name="br0",
                enabled=True,
                vlan=eth0_100_vlan,
            ),
        )

    def test_bridge_on_vlan_interface_with_identical_macs_replacing_phy(self):
        controller = self.create_empty_controller()
        br0_fabric = factory.make_Fabric()
        eth0_100_vlan = factory.make_VLAN(vid=100, fabric=br0_fabric)
        br0_subnet = factory.make_Subnet(vlan=eth0_100_vlan)
        br0_ip = factory.pick_ip_in_Subnet(br0_subnet)
        eth0_mac = factory.make_mac_address()
        # Before the fix for bug #1555679, bridges were modeled as "physical".
        # Therefore, MAAS users needed to change the MAC of their bridge
        # interfaces, rather than using the common practice of making it the
        # same as the MAC of the parent interface.
        bogus_br0_mac = factory.make_mac_address()
        bogus_br1_mac = factory.make_mac_address()
        bogus_br101_mac = factory.make_mac_address()
        br1_fabric = factory.make_Fabric()
        eth1_100_vlan = factory.make_VLAN(vid=100, fabric=br1_fabric)
        br1_subnet = factory.make_Subnet(vlan=eth1_100_vlan)
        br1_ip = factory.pick_ip_in_Subnet(br1_subnet)
        eth1_mac = factory.make_mac_address()
        eth0_101_vlan = factory.make_VLAN(vid=101, fabric=br1_fabric)
        br101_subnet = factory.make_Subnet(vlan=eth0_101_vlan)
        br101_ip = factory.pick_ip_in_Subnet(br101_subnet)
        interfaces_old = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0_mac,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth0.100": {
                "type": "vlan",
                "vid": 100,
                "mac_address": eth0_mac,
                "parents": ["eth0"],
                "links": [],
                "enabled": True,
            },
            "eth0.101": {
                "type": "vlan",
                "vid": 101,
                "mac_address": eth0_mac,
                "parents": ["eth0"],
                "links": [],
                "enabled": True,
            },
            "br0": {
                "type": "physical",
                "mac_address": bogus_br0_mac,
                "parents": [],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (str(br0_ip), br0_subnet.get_ipnetwork().prefixlen),
                    }
                ],
                "enabled": True,
            },
            "br101": {
                "type": "bridge",
                "mac_address": bogus_br101_mac,
                "parents": ["eth0.101"],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (
                            str(br101_ip),
                            br101_subnet.get_ipnetwork().prefixlen,
                        ),
                    }
                ],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": eth1_mac,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1.100": {
                "type": "vlan",
                "vid": 100,
                "mac_address": eth1_mac,
                "parents": ["eth1"],
                "links": [],
                "enabled": True,
            },
            "br1": {
                "type": "bridge",
                "mac_address": bogus_br1_mac,
                "parents": ["eth1.100"],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (str(br1_ip), br1_subnet.get_ipnetwork().prefixlen),
                    }
                ],
                "enabled": True,
            },
        }
        controller.update_interfaces(interfaces_old)
        eth0 = PhysicalInterface.objects.get(
            node=controller, mac_address=interfaces_old["eth0"]["mac_address"]
        )
        self.assertThat(
            eth0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces_old["eth0"]["mac_address"],
                enabled=True,
                vlan=eth0.vlan,
            ),
        )
        # This is weird because it results in a model where eth0.100 is not
        # on the same VLAN as br0. But it's something that the admin will need
        # to fix after-the-fact, unfortunately...
        br0 = get_one(Interface.objects.filter_by_ip(br0_ip))
        br0_vlan = br0.vlan
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0_mac,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth0.100": {
                "type": "vlan",
                "vid": 100,
                "mac_address": eth0_mac,
                "parents": ["eth0"],
                "links": [],
                "enabled": True,
            },
            "eth0.101": {
                "type": "vlan",
                "vid": 101,
                "mac_address": eth0_mac,
                "parents": ["eth0"],
                "links": [],
                "enabled": True,
            },
            "br0": {
                "type": "bridge",
                "mac_address": eth0_mac,
                "parents": ["eth0.100"],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (str(br0_ip), br0_subnet.get_ipnetwork().prefixlen),
                    }
                ],
                "enabled": True,
            },
            "br101": {
                "type": "bridge",
                "mac_address": eth0_mac,
                "parents": ["eth0.101"],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (
                            str(br101_ip),
                            br101_subnet.get_ipnetwork().prefixlen,
                        ),
                    }
                ],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": eth1_mac,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1.100": {
                "type": "vlan",
                "vid": 100,
                "mac_address": eth1_mac,
                "parents": ["eth1"],
                "links": [],
                "enabled": True,
            },
            "br1": {
                "type": "bridge",
                "mac_address": eth1_mac,
                "parents": ["eth1.100"],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d"
                        % (str(br1_ip), br1_subnet.get_ipnetwork().prefixlen),
                    }
                ],
                "enabled": True,
            },
        }
        self.update_interfaces(controller, interfaces)
        eth0 = PhysicalInterface.objects.get(
            node=controller, mac_address=interfaces["eth0"]["mac_address"]
        )
        self.assertThat(
            eth0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                vlan=eth0.vlan,
            ),
        )
        eth0_100 = VLANInterface.objects.get(
            node=controller,
            name="eth0.100",
            mac_address=interfaces["eth0.100"]["mac_address"],
        )
        self.assertThat(
            eth0_100,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.100",
                mac_address=interfaces["eth0.100"]["mac_address"],
                enabled=True,
                vlan=eth0_100_vlan,
            ),
        )
        br0 = BridgeInterface.objects.get(
            node=controller,
            name="br0",
            mac_address=interfaces["br0"]["mac_address"],
        )
        self.assertThat(
            br0,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.BRIDGE,
                name="br0",
                mac_address=interfaces["br0"]["mac_address"],
                enabled=True,
                vlan=br0_vlan,
            ),
        )
        br0_addresses = list(br0.ip_addresses.all())
        self.assertThat(br0_addresses, HasLength(1))
        self.assertThat(
            br0_addresses[0],
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=br0_ip, subnet=br0_subnet
            ),
        )
        br0_nic = BridgeInterface.objects.get(
            node=controller, vlan=eth0_100_vlan
        )
        self.assertThat(
            br0_nic,
            MatchesStructure.byEquality(
                type=INTERFACE_TYPE.BRIDGE,
                name="br0",
                enabled=True,
                vlan=br0_vlan,
            ),
        )

    def test_registers_bridge_with_disabled_parent(self):
        controller = self.create_empty_controller()
        interfaces = {
            "eth0": {
                "enabled": True,
                "links": [
                    {
                        "address": "10.0.0.2/24",
                        "gateway": "10.0.0.1",
                        "mode": "static",
                    }
                ],
                "mac_address": "52:54:00:3a:01:35",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
            "virbr0": {
                "enabled": True,
                "links": [{"address": "192.168.122.1/24", "mode": "static"}],
                "mac_address": "52:54:00:3a:01:36",
                "parents": ["virbr0-nic"],
                "source": "ipaddr",
                "type": "bridge",
            },
            "virbr0-nic": {
                "enabled": False,
                "mac_address": "52:54:00:3a:01:36",
                "links": [],
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
        }
        self.update_interfaces(controller, interfaces)
        subnet = get_one(Subnet.objects.filter(cidr="10.0.0.0/24"))
        self.assertIsNotNone(subnet)
        subnet = get_one(Subnet.objects.filter(cidr="192.168.122.0/24"))
        self.assertIsNotNone(subnet)

    def test_registers_bridge_with_no_parents_and_links(self):
        controller = self.create_empty_controller()
        interfaces = {
            "br0": {
                "enabled": True,
                "mac_address": "4e:4d:9a:a8:a5:5f",
                "parents": [],
                "source": "ipaddr",
                "type": "bridge",
                "links": [{"mode": "static", "address": "192.168.0.1/24"}],
            },
            "eth0": {
                "enabled": True,
                "mac_address": "52:54:00:77:15:e3",
                "links": [],
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
        }
        self.update_interfaces(controller, interfaces)
        eth0 = get_one(
            PhysicalInterface.objects.filter(node=controller, name="eth0")
        )
        br0 = get_one(
            BridgeInterface.objects.filter(node=controller, name="br0")
        )
        self.assertIsNotNone(eth0)
        self.assertIsNotNone(br0)
        subnet = get_one(Subnet.objects.filter(cidr="192.168.0.0/24"))
        self.assertIsNotNone(subnet)
        self.assertThat(subnet.vlan, Equals(br0.vlan))

    def test_registers_bridge_with_no_parents_and_no_links(self):
        controller = self.create_empty_controller()
        interfaces = {
            "br0": {
                "enabled": True,
                "links": [],
                "mac_address": "4e:4d:9a:a8:a5:5f",
                "parents": [],
                "source": "ipaddr",
                "type": "bridge",
            },
            "eth0": {
                "enabled": True,
                "links": [],
                "mac_address": "52:54:00:77:15:e3",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
        }
        self.update_interfaces(controller, interfaces)
        eth0 = get_one(
            PhysicalInterface.objects.filter(node=controller, name="eth0")
        )
        br0 = get_one(
            BridgeInterface.objects.filter(node=controller, name="br0")
        )
        self.assertIsNotNone(eth0)
        self.assertIsNotNone(br0)

    def test_disabled_interfaces_do_not_create_fabrics(self):
        controller = self.create_empty_controller()
        interfaces = {
            "eth0": {
                "enabled": True,
                "links": [],
                "mac_address": "52:54:00:77:15:e3",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
            "eth1": {
                "enabled": False,
                "links": [],
                "mac_address": "52:54:00:77:15:e4",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
        }
        self.update_interfaces(controller, interfaces)
        eth0 = get_one(
            PhysicalInterface.objects.filter(node=controller, name="eth0")
        )
        eth1 = get_one(
            PhysicalInterface.objects.filter(node=controller, name="eth1")
        )
        self.assertIsNotNone(eth0.vlan)
        self.assertIsNone(eth1.vlan)

    def test_subnet_seen_on_second_controller_does_not_create_fabric(self):
        alice = self.create_empty_controller()
        bob = self.create_empty_controller()
        alice_interfaces = {
            "eth0": {
                "enabled": True,
                "links": [{"address": "192.168.0.1/24", "mode": "dhcp"}],
                "mac_address": "52:54:00:77:15:e3",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
            "eth1": {
                "enabled": False,
                "links": [],
                "mac_address": "52:54:00:77:15:e4",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
        }
        bob_interfaces = {
            "eth0": {
                "enabled": True,
                "links": [{"address": "192.168.0.2/24", "mode": "dhcp"}],
                "mac_address": "52:54:00:87:25:f3",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
            "eth1": {
                "enabled": False,
                "links": [],
                "mac_address": "52:54:00:87:25:f4",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
        }
        self.update_interfaces(alice, alice_interfaces)
        self.update_interfaces(bob, bob_interfaces)
        alice_eth0 = get_one(
            PhysicalInterface.objects.filter(node=alice, name="eth0")
        )
        bob_eth0 = get_one(
            PhysicalInterface.objects.filter(node=bob, name="eth0")
        )
        self.assertThat(alice_eth0.vlan, Equals(bob_eth0.vlan))


class TestUpdateInterfacesWithHints(
    MAASTransactionServerTestCase, UpdateInterfacesMixin
):

    scenarios = UpdateInterfacesMixin.scenarios

    def test_seen_on_second_controller_with_hints(self):
        alice = self.create_empty_controller()
        bob = self.create_empty_controller()
        factory.make_Node()
        alice_interfaces = {
            "eth0": {
                "enabled": True,
                "links": [{"address": "192.168.0.1/24", "mode": "dhcp"}],
                "mac_address": "52:54:00:77:15:e3",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
            "eth1": {
                "enabled": False,
                "links": [],
                "mac_address": "52:54:00:77:15:e4",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
        }
        bob_interfaces = {
            "eth0": {
                "enabled": True,
                "links": [],
                "mac_address": "52:54:00:87:25:f3",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
            "eth1": {
                "enabled": True,
                "links": [],
                "mac_address": "52:54:00:87:25:f4",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
        }
        bob_hints = [
            {
                "hint": "same_local_fabric_as",
                "ifname": "eth0",
                "related_ifname": "eth1",
            },
            {
                "hint": "on_remote_network",
                "ifname": "eth0",
                "related_ifname": "eth0",
                "related_mac": "52:54:00:77:15:e3",
            },
            {
                "hint": "routable_to",
                "ifname": "eth0",
                "related_ifname": "eth0",
                "related_mac": "52:54:00:77:15:e3",
            },
            {
                "hint": "rx_own_beacon_on_other_interface",
                "ifname": "eth1",
                "related_ifname": "eth0",
            },
        ]
        self.update_interfaces(alice, alice_interfaces)
        self.update_interfaces(bob, bob_interfaces, bob_hints)
        alice_eth0 = get_one(
            PhysicalInterface.objects.filter(node=alice, name="eth0")
        )
        bob_eth0 = get_one(
            PhysicalInterface.objects.filter(node=bob, name="eth0")
        )
        bob_eth1 = get_one(
            PhysicalInterface.objects.filter(node=bob, name="eth1")
        )
        if not self.with_beaconing:
            # Legacy mode; we'll see lots of VLANs and fabrics if an older
            # rack registers with this configuration.
            self.assertThat(alice_eth0.vlan, Not(Equals(bob_eth0.vlan)))
            self.assertThat(bob_eth1.vlan, Not(Equals(bob_eth0.vlan)))
        else:
            # Registration with beaconing; we should see all these interfaces
            # appear on the same VLAN.
            self.assertThat(alice_eth0.vlan, Equals(bob_eth0.vlan))
            self.assertThat(bob_eth1.vlan, Equals(bob_eth0.vlan))

    def test_bridge_seen_on_second_controller_with_hints(self):
        alice = self.create_empty_controller()
        bob = self.create_empty_controller()
        factory.make_Node()
        alice_interfaces = {
            "br0": {
                "enabled": True,
                "links": [{"address": "192.168.0.1/24", "mode": "dhcp"}],
                "mac_address": "52:54:00:77:15:e3",
                "parents": [],
                "source": "ipaddr",
                "type": "bridge",
            },
            "eth1": {
                "enabled": False,
                "links": [],
                "mac_address": "52:54:00:77:15:e4",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
        }
        bob_interfaces = {
            "eth0": {
                "enabled": True,
                "links": [],
                "mac_address": "52:54:00:87:25:f3",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
            "eth1": {
                "enabled": True,
                "links": [],
                "mac_address": "52:54:00:87:25:f4",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            },
        }
        bob_hints = [
            {
                "hint": "same_local_fabric_as",
                "ifname": "eth0",
                "related_ifname": "eth1",
            },
            {
                "hint": "on_remote_network",
                "ifname": "eth0",
                "related_ifname": "br0",
                "related_mac": "52:54:00:77:15:e3",
            },
            {
                "hint": "routable_to",
                "ifname": "eth0",
                "related_ifname": "br0",
                "related_mac": "52:54:00:77:15:e3",
            },
            {
                "hint": "rx_own_beacon_on_other_interface",
                "ifname": "eth1",
                "related_ifname": "eth0",
            },
        ]
        self.update_interfaces(alice, alice_interfaces)
        self.update_interfaces(bob, bob_interfaces, bob_hints)
        alice_br0 = get_one(
            BridgeInterface.objects.filter(node=alice, name="br0")
        )
        bob_eth0 = get_one(
            PhysicalInterface.objects.filter(node=bob, name="eth0")
        )
        bob_eth1 = get_one(
            PhysicalInterface.objects.filter(node=bob, name="eth1")
        )
        if not self.with_beaconing:
            # Legacy mode; we'll see lots of VLANs and fabrics if an older
            # rack registers with this configuration.
            self.assertThat(alice_br0.vlan, Not(Equals(bob_eth0.vlan)))
            self.assertThat(bob_eth1.vlan, Not(Equals(bob_eth0.vlan)))
        else:
            # Registration with beaconing; we should see all these interfaces
            # appear on the same VLAN.
            self.assertThat(alice_br0.vlan, Equals(bob_eth0.vlan))
            self.assertThat(bob_eth1.vlan, Equals(bob_eth0.vlan))

    def test_update_interfaces_iface_changed_mac(self):
        node = self.create_empty_controller()
        interfaces = {
            "eth1": {
                "enabled": True,
                "links": [],
                "mac_address": "aa:bb:cc:dd:ee:ff",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            }
        }
        self.update_interfaces(node, interfaces)
        interfaces = {
            "eth1": {
                "enabled": True,
                "links": [],
                "mac_address": "aa:bb:cc:dd:ee:00",
                "parents": [],
                "source": "ipaddr",
                "type": "physical",
            }
        }
        self.update_interfaces(node, interfaces)
