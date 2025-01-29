# Copyright 2012-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import base64
from operator import itemgetter
import random
from unittest.mock import ANY

from django.utils import timezone
from netaddr import IPAddress, IPNetwork
import pytest
from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread

from maascommon.workflows.dhcp import CONFIGURE_DHCP_WORKFLOW_NAME
from maasserver import dhcp
from maasserver import server_address as server_address_module
import maasserver.dhcp as dhcp_module
from maasserver.dhcp import _get_dhcp_rackcontrollers, get_default_dns_servers
from maasserver.enum import INTERFACE_TYPE, IPADDRESS_TYPE, SERVICE_STATUS
from maasserver.models import Config, DHCPSnippet, Domain, Service
from maasserver.rpc import getClientFor
from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.secrets import SecretManager
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import post_commit_hooks, transactional
from maasserver.utils.threads import deferToDatabase
from maastemporalworker.workflow.dhcp import ConfigureDHCPParam
from maastesting.crochet import wait_for
from maastesting.djangotestcase import count_queries
from maastesting.twisted import always_fail_with, always_succeed_with
from provisioningserver.rpc import exceptions
from provisioningserver.rpc.cluster import ConfigureDHCPv4, ConfigureDHCPv6
from provisioningserver.rpc.exceptions import CannotConfigureDHCP
from provisioningserver.utils.twisted import synchronous

wait_for_reactor = wait_for()


class TestGetOMAPIKey(MAASServerTestCase):
    """Tests for `get_omapi_key`."""

    def test_returns_key_in_global_config(self):
        key = factory.make_name("omapi")
        SecretManager().set_simple_secret("omapi-key", key)
        self.assertEqual(key, dhcp.get_omapi_key())

    def test_sets_new_omapi_key_in_global_config(self):
        key = factory.make_name("omapi")
        mock_generate_omapi_key = self.patch(dhcp, "generate_omapi_key")
        mock_generate_omapi_key.return_value = key
        self.assertEqual(key, dhcp.get_omapi_key())
        self.assertEqual(key, SecretManager().get_simple_secret("omapi-key"))
        mock_generate_omapi_key.assert_called_once_with()


class TestSplitIPv4IPv6Subnets(MAASServerTestCase):
    """Tests for `split_ipv4_ipv6_subnets`."""

    def test_separates_IPv4_from_IPv6_subnets(self):
        ipv4_subnets = [
            factory.make_Subnet(cidr=str(factory.make_ipv4_network().cidr))
            for _ in range(random.randint(0, 2))
        ]
        ipv6_subnets = [
            factory.make_Subnet(cidr=str(factory.make_ipv6_network().cidr))
            for _ in range(random.randint(0, 2))
        ]
        subnets = sorted(
            ipv4_subnets + ipv6_subnets,
            key=lambda *args: random.randint(0, 10),
        )

        ipv4_result, ipv6_result = dhcp.split_managed_ipv4_ipv6_subnets(
            subnets
        )

        self.assertCountEqual(ipv4_subnets, ipv4_result)
        self.assertCountEqual(ipv6_subnets, ipv6_result)

    def test_skips_unmanaged_subnets(self):
        ipv4_subnets = [
            factory.make_Subnet(
                cidr=str(factory.make_ipv4_network().cidr),
                managed=random.choice([True, False]),
            )
            for _ in range(random.randint(0, 2))
        ]
        ipv6_subnets = [
            factory.make_Subnet(
                cidr=str(factory.make_ipv6_network().cidr),
                managed=random.choice([True, False]),
            )
            for _ in range(random.randint(0, 2))
        ]
        subnets = sorted(
            ipv4_subnets + ipv6_subnets,
            key=lambda *args: random.randint(0, 10),
        )

        ipv4_result, ipv6_result = dhcp.split_managed_ipv4_ipv6_subnets(
            subnets
        )

        self.assertCountEqual(
            [s for s in ipv4_subnets if s.managed is True], ipv4_result
        )
        self.assertCountEqual(
            [s for s in ipv6_subnets if s.managed is True], ipv6_result
        )


class TestIPIsStickyOrAuto(MAASServerTestCase):
    """Tests for `ip_is_sticky_or_auto`."""

    scenarios = (
        ("sticky", {"alloc_type": IPADDRESS_TYPE.STICKY, "result": True}),
        ("auto", {"alloc_type": IPADDRESS_TYPE.AUTO, "result": True}),
        (
            "discovered",
            {"alloc_type": IPADDRESS_TYPE.DISCOVERED, "result": False},
        ),
        (
            "user_reserved",
            {"alloc_type": IPADDRESS_TYPE.USER_RESERVED, "result": False},
        ),
    )

    def test_returns_correct_result(self):
        ip_address = factory.make_StaticIPAddress(alloc_type=self.alloc_type)
        self.assertEqual(self.result, dhcp.ip_is_sticky_or_auto(ip_address))


class TestGetBestInterface(MAASServerTestCase):
    """Tests for `get_best_interface`."""

    def test_returns_bond_over_physical(self):
        rack_controller = factory.make_RackController()
        physical = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller
        )
        nic0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller
        )
        nic1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller
        )
        bond = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=rack_controller, parents=[nic0, nic1]
        )
        self.assertEqual(bond, dhcp.get_best_interface([physical, bond]))

    def test_returns_physical_over_vlan(self):
        rack_controller = factory.make_RackController()
        physical = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller
        )
        vlan = factory.make_Interface(
            INTERFACE_TYPE.VLAN, node=rack_controller, parents=[physical]
        )
        self.assertEqual(physical, dhcp.get_best_interface([physical, vlan]))

    def test_returns_first_interface_when_all_physical(self):
        rack_controller = factory.make_RackController()
        interfaces = [
            factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=rack_controller
            )
            for _ in range(3)
        ]
        self.assertEqual(interfaces[0], dhcp.get_best_interface(interfaces))

    def test_returns_first_interface_when_all_vlan(self):
        rack_controller = factory.make_RackController()
        physical = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller
        )
        interfaces = [
            factory.make_Interface(
                INTERFACE_TYPE.VLAN, node=rack_controller, parents=[physical]
            )
            for _ in range(3)
        ]
        self.assertEqual(interfaces[0], dhcp.get_best_interface(interfaces))


class TestGetInterfacesWithIPOnVLAN(MAASServerTestCase):
    """Tests for `get_interfaces_with_ip_on_vlan`."""

    def test_always_same_number_of_queries(self):
        rack_controller = factory.make_RackController()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(cidr="10.0.0.0/8", vlan=vlan)
        factory.make_IPRange(
            subnet=subnet, start_ip="10.0.1.0", end_ip="10.0.1.254"
        )
        factory.make_IPRange(
            subnet=subnet, start_ip="10.0.2.0", end_ip="10.0.2.254"
        )
        factory.make_IPRange(
            subnet=subnet, start_ip="10.0.3.0", end_ip="10.0.3.254"
        )
        # Make a multiple interfaces.
        for _ in range(10):
            interface = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
            )
            for _ in range(random.randint(1, 3)):
                factory.make_StaticIPAddress(
                    alloc_type=IPADDRESS_TYPE.AUTO,
                    ip=factory.pick_ip_in_Subnet(subnet),
                    subnet=subnet,
                    interface=interface,
                )
        query_10_count, _ = count_queries(
            dhcp.get_interfaces_with_ip_on_vlan,
            rack_controller,
            vlan,
            subnet.get_ipnetwork().version,
        )
        # Add more interfaces and count the queries again.
        for _ in range(10):
            interface = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
            )
            for _ in range(random.randint(1, 3)):
                factory.make_StaticIPAddress(
                    alloc_type=IPADDRESS_TYPE.AUTO,
                    ip=factory.pick_ip_in_Subnet(subnet),
                    subnet=subnet,
                    interface=interface,
                )
        query_20_count, _ = count_queries(
            dhcp.get_interfaces_with_ip_on_vlan,
            rack_controller,
            vlan,
            subnet.get_ipnetwork().version,
        )

        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when performing this
        # operation. It is important to keep this number as low as possible.
        self.assertEqual(
            query_10_count,
            6,
            "Number of queries has changed; make sure this is expected.",
        )
        self.assertEqual(
            query_10_count,
            query_20_count,
            "Number of queries is not independent to the number of objects.",
        )

    def test_returns_interface_with_static_ip(self):
        rack_controller = factory.make_RackController()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, subnet=subnet, interface=interface
        )
        self.assertEqual(
            [interface],
            dhcp.get_interfaces_with_ip_on_vlan(
                rack_controller, vlan, subnet.get_ipnetwork().version
            ),
        )

    def test_returns_interfaces_with_ips(self):
        rack_controller = factory.make_RackController()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        interface_one = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet,
            interface=interface_one,
        )
        interface_two = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet,
            interface=interface_two,
        )
        self.assertCountEqual(
            [interface_one, interface_two],
            dhcp.get_interfaces_with_ip_on_vlan(
                rack_controller, vlan, subnet.get_ipnetwork().version
            ),
        )

    def test_returns_interfaces_with_dynamic_ranges_first(self):
        rack_controller = factory.make_RackController()
        vlan = factory.make_VLAN()
        network = factory.make_ipv4_network()
        subnet = factory.make_Subnet(cidr=str(network.cidr), vlan=vlan)
        interface_one = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet,
            interface=interface_one,
        )
        interface_two = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        subnet_with_dynamic_range = factory.make_ipv4_Subnet_with_IPRanges(
            vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet_with_dynamic_range,
            interface=interface_two,
        )
        self.assertEqual(
            [interface_two, interface_one],
            dhcp.get_interfaces_with_ip_on_vlan(
                rack_controller, vlan, subnet.get_ipnetwork().version
            ),
        )

    def test_returns_interfaces_with_discovered_ips(self):
        rack_controller = factory.make_RackController()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        interface_one = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            subnet=subnet,
            interface=interface_one,
        )
        interface_two = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            subnet=subnet,
            interface=interface_two,
        )
        self.assertCountEqual(
            [interface_one, interface_two],
            dhcp.get_interfaces_with_ip_on_vlan(
                rack_controller, vlan, subnet.get_ipnetwork().version
            ),
        )

    def test_returns_interfaces_with_static_over_discovered(self):
        rack_controller = factory.make_RackController()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        interface_one = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet,
            interface=interface_one,
        )
        interface_two = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            subnet=subnet,
            interface=interface_two,
        )
        self.assertEqual(
            [interface_one],
            dhcp.get_interfaces_with_ip_on_vlan(
                rack_controller, vlan, subnet.get_ipnetwork().version
            ),
        )

    def test_returns_no_interfaces_if_ip_empty(self):
        rack_controller = factory.make_RackController()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=subnet,
            interface=interface,
        )
        self.assertEqual(
            [],
            dhcp.get_interfaces_with_ip_on_vlan(
                rack_controller, vlan, subnet.get_ipnetwork().version
            ),
        )

    def test_returns_only_interfaces_on_vlan_ipv4(self):
        rack_controller = factory.make_RackController()
        vlan = factory.make_VLAN()
        network = factory.make_ipv4_network()
        subnet = factory.make_Subnet(cidr=str(network.cidr), vlan=vlan)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet,
            interface=interface,
        )
        other_vlan = factory.make_VLAN()
        other_network = factory.make_ipv4_network()
        other_subnet = factory.make_Subnet(
            cidr=str(other_network.cidr), vlan=other_vlan
        )
        other_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=other_vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=other_subnet,
            interface=other_interface,
        )
        self.assertEqual(
            [interface],
            dhcp.get_interfaces_with_ip_on_vlan(
                rack_controller, vlan, subnet.get_ipnetwork().version
            ),
        )

    def test_returns_only_interfaces_on_vlan_ipv6(self):
        rack_controller = factory.make_RackController()
        vlan = factory.make_VLAN()
        network = factory.make_ipv6_network()
        subnet = factory.make_Subnet(cidr=str(network.cidr), vlan=vlan)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet,
            interface=interface,
        )
        other_vlan = factory.make_VLAN()
        other_network = factory.make_ipv6_network()
        other_subnet = factory.make_Subnet(
            cidr=str(other_network.cidr), vlan=other_vlan
        )
        other_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=other_vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=other_subnet,
            interface=other_interface,
        )
        self.assertEqual(
            [interface],
            dhcp.get_interfaces_with_ip_on_vlan(
                rack_controller, vlan, subnet.get_ipnetwork().version
            ),
        )

    def test_returns_interface_with_static_ip_on_vlan_from_relay(self):
        rack_controller = factory.make_RackController()
        vlan = factory.make_VLAN()
        relayed_to_another = factory.make_VLAN(relay_vlan=vlan)
        subnet = factory.make_Subnet(vlan=vlan)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, subnet=subnet, interface=interface
        )
        self.assertEqual(
            [interface],
            dhcp.get_interfaces_with_ip_on_vlan(
                rack_controller,
                relayed_to_another,
                subnet.get_ipnetwork().version,
            ),
        )

    def test_returns_interfaces_with_discovered_ips_on_vlan_from_relay(self):
        rack_controller = factory.make_RackController()
        vlan = factory.make_VLAN()
        relayed_to_another = factory.make_VLAN(relay_vlan=vlan)
        subnet = factory.make_Subnet(vlan=vlan)
        interface_one = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            subnet=subnet,
            interface=interface_one,
        )
        interface_two = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            subnet=subnet,
            interface=interface_two,
        )
        self.assertCountEqual(
            [interface_one, interface_two],
            dhcp.get_interfaces_with_ip_on_vlan(
                rack_controller,
                relayed_to_another,
                subnet.get_ipnetwork().version,
            ),
        )


class TestGenManagedVLANsFor(MAASServerTestCase):
    """Tests for `gen_managed_vlans_for`."""

    def test_returns_all_managed_vlans(self):
        rack_controller = factory.make_RackController()

        # Two interfaces on one IPv4 and one IPv6 subnet where the VLAN is
        # being managed by the rack controller as the primary.
        vlan_one = factory.make_VLAN(
            dhcp_on=True, primary_rack=rack_controller, name="1"
        )
        primary_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan_one
        )
        bond_parent_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan_one
        )
        bond_interface = factory.make_Interface(
            INTERFACE_TYPE.BOND,
            node=rack_controller,
            parents=[bond_parent_interface],
            vlan=vlan_one,
        )
        managed_ipv4_subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr), vlan=vlan_one
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=managed_ipv4_subnet,
            interface=primary_interface,
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=managed_ipv4_subnet,
            interface=bond_interface,
        )
        managed_ipv6_subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv6_network().cidr), vlan=vlan_one
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=managed_ipv6_subnet,
            interface=primary_interface,
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=managed_ipv6_subnet,
            interface=bond_interface,
        )

        # Interface on one IPv4 and one IPv6 subnet where the VLAN is being
        # managed by the rack controller as the secondary.
        vlan_two = factory.make_VLAN(
            dhcp_on=True, secondary_rack=rack_controller, name="2"
        )
        secondary_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan_two
        )
        sec_managed_ipv4_subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr), vlan=vlan_two
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=sec_managed_ipv4_subnet,
            interface=secondary_interface,
        )
        sec_managed_ipv6_subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv6_network().cidr), vlan=vlan_two
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=sec_managed_ipv6_subnet,
            interface=secondary_interface,
        )

        # Interface on one IPv4 and one IPv6 subnet where the VLAN is not
        # managed by the rack controller.
        vlan_three = factory.make_VLAN(dhcp_on=True, name="3")
        not_managed_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan_three
        )
        not_managed_ipv4_subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr), vlan=vlan_three
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=not_managed_ipv4_subnet,
            interface=not_managed_interface,
        )
        not_managed_ipv6_subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv6_network().cidr), vlan=vlan_three
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=not_managed_ipv6_subnet,
            interface=not_managed_interface,
        )

        # Interface on one IPv4 and one IPv6 subnet where the VLAN dhcp is off.
        vlan_four = factory.make_VLAN(dhcp_on=False, name="4")
        dhcp_off_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan_four
        )
        dhcp_off_ipv4_subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr), vlan=vlan_four
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=dhcp_off_ipv4_subnet,
            interface=dhcp_off_interface,
        )
        dhcp_off_ipv6_subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv6_network().cidr), vlan=vlan_four
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=dhcp_off_ipv6_subnet,
            interface=dhcp_off_interface,
        )

        # Should only contain the subnets that are managed by the rack
        # controller and the best interface should have been selected.
        self.assertEqual(
            {vlan_one, vlan_two},
            set(dhcp.gen_managed_vlans_for(rack_controller)),
        )

    def test_returns_managed_vlan_with_relay_vlans(self):
        rack_controller = factory.make_RackController()
        vlan_one = factory.make_VLAN(
            dhcp_on=True, primary_rack=rack_controller, name="1"
        )
        primary_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan_one
        )
        managed_ipv4_subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr), vlan=vlan_one
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=managed_ipv4_subnet,
            interface=primary_interface,
        )

        # Relay VLANs atteched to the vlan.
        relay_vlans = {
            factory.make_VLAN(relay_vlan=vlan_one) for _ in range(3)
        }

        # Should only contain the subnets that are managed by the rack
        # controller and the best interface should have been selected.
        self.assertEqual(
            relay_vlans.union({vlan_one}),
            set(dhcp.gen_managed_vlans_for(rack_controller)),
        )


class TestIPIsOnVLAN(MAASServerTestCase):
    """Tests for `ip_is_on_vlan`."""

    scenarios = (
        (
            "sticky_on_vlan_with_ip",
            {
                "alloc_type": IPADDRESS_TYPE.STICKY,
                "has_ip": True,
                "on_vlan": True,
                "on_subnet": True,
                "result": True,
            },
        ),
        (
            "sticky_not_on_vlan_with_ip",
            {
                "alloc_type": IPADDRESS_TYPE.STICKY,
                "has_ip": True,
                "on_vlan": False,
                "on_subnet": True,
                "result": False,
            },
        ),
        (
            "auto_on_vlan_with_ip",
            {
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "has_ip": True,
                "on_vlan": True,
                "on_subnet": True,
                "result": True,
            },
        ),
        (
            "auto_on_vlan_without_ip",
            {
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "has_ip": False,
                "on_vlan": True,
                "on_subnet": True,
                "result": False,
            },
        ),
        (
            "auto_not_on_vlan_with_ip",
            {
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "has_ip": True,
                "on_vlan": False,
                "on_subnet": True,
                "result": False,
            },
        ),
        (
            "discovered",
            {
                "alloc_type": IPADDRESS_TYPE.DISCOVERED,
                "has_ip": True,
                "on_vlan": True,
                "on_subnet": True,
                "result": False,
            },
        ),
        (
            "user_reserved",
            {
                "alloc_type": IPADDRESS_TYPE.USER_RESERVED,
                "has_ip": True,
                "on_vlan": True,
                "on_subnet": True,
                "result": False,
            },
        ),
        (
            "not_on_subnet",
            {
                "alloc_type": IPADDRESS_TYPE.STICKY,
                "has_ip": True,
                "on_vlan": False,
                "on_subnet": False,
                "result": False,
            },
        ),
    )

    def test_returns_correct_result(self):
        expected_vlan = factory.make_VLAN()
        set_vlan = expected_vlan
        if not self.on_vlan:
            set_vlan = factory.make_VLAN()
        ip = ""
        subnet = factory.make_Subnet(vlan=set_vlan)
        if self.has_ip:
            ip = factory.pick_ip_in_Subnet(subnet)
        ip_address = factory.make_StaticIPAddress(
            alloc_type=self.alloc_type, ip=ip, subnet=subnet
        )
        if not self.on_subnet:
            # make_StaticIPAddress always creates a subnet so set it to None.
            ip_address.subnet = None
            with post_commit_hooks:
                ip_address.save()
        self.assertEqual(
            self.result, dhcp.ip_is_on_vlan(ip_address, expected_vlan)
        )


class TestGetIPAddressForInterface(MAASServerTestCase):
    """Tests for `get_ip_address_for_interface`."""

    def test_returns_ip_address_on_vlan(self):
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, vlan=vlan)
        subnet = factory.make_Subnet(vlan=vlan)
        ip_address = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet),
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet,
            interface=interface,
        )
        self.assertEqual(
            ip_address,
            dhcp.get_ip_address_for_interface(
                interface, vlan, subnet.get_ip_version()
            ),
        )

    def test_returns_None(self):
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, vlan=vlan)
        subnet = factory.make_Subnet(vlan=vlan)
        factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet),
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet,
            interface=interface,
        )
        self.assertIsNone(
            dhcp.get_ip_address_for_interface(
                interface, factory.make_VLAN(), subnet.get_ip_version()
            )
        )


class TestGetIPAddressForRackController(MAASServerTestCase):
    """Tests for `get_ip_address_for_rack_controller`."""

    def test_returns_ip_address_for_rack_controller_on_vlan(self):
        vlan = factory.make_VLAN()
        rack_controller = factory.make_RackController()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        subnet = factory.make_Subnet(vlan=vlan)
        ip_address = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet),
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet,
            interface=interface,
        )
        self.assertEqual(
            ip_address,
            dhcp.get_ip_address_for_rack_controller(
                rack_controller, vlan, subnet.get_ip_version()
            ),
        )

    def test_returns_ip_address_from_best_interface_on_rack_controller(self):
        vlan = factory.make_VLAN()
        rack_controller = factory.make_RackController()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        parent_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=vlan
        )
        bond_interface = factory.make_Interface(
            INTERFACE_TYPE.BOND,
            node=rack_controller,
            parents=[parent_interface],
            vlan=vlan,
        )
        subnet = factory.make_Subnet(vlan=vlan)
        factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet),
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet,
            interface=interface,
        )
        bond_ip_address = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet,
            interface=bond_interface,
        )
        self.assertEqual(
            bond_ip_address,
            dhcp.get_ip_address_for_rack_controller(
                rack_controller, vlan, subnet.get_ip_version()
            ),
        )


class TestGetNTPServerAddressesForRack(MAASServerTestCase):
    """Tests for `get_ntp_server_addresses_for_rack`."""

    def test_returns_empty_dict_for_unconnected_rack(self):
        rack = factory.make_RackController()
        self.assertEqual({}, dhcp.get_ntp_server_addresses_for_rack(rack))

    def test_returns_dict_with_rack_addresses(self):
        rack = factory.make_RackController()
        space = factory.make_Space()
        subnet = factory.make_Subnet(space=space)
        interface = factory.make_Interface(node=rack)
        address = factory.make_StaticIPAddress(
            interface=interface,
            subnet=subnet,
            alloc_type=IPADDRESS_TYPE.STICKY,
        )

        self.assertEqual(
            {(space.id, subnet.get_ipnetwork().version): address.ip},
            dhcp.get_ntp_server_addresses_for_rack(rack),
        )

    def test_handles_blank_subnet(self):
        rack = factory.make_RackController()
        ip = factory.make_ip_address()
        interface = factory.make_Interface(node=rack)
        factory.make_StaticIPAddress(
            interface=interface, alloc_type=IPADDRESS_TYPE.USER_RESERVED, ip=ip
        )

        self.assertEqual({}, dhcp.get_ntp_server_addresses_for_rack(rack))

    def test_returns_dict_grouped_by_space_and_address_family(self):
        rack = factory.make_RackController()
        space1 = factory.make_Space()
        space2 = factory.make_Space()
        subnet1 = factory.make_Subnet(space=space1)
        subnet2 = factory.make_Subnet(space=space2)
        interface = factory.make_Interface(node=rack)
        address1 = factory.make_StaticIPAddress(
            interface=interface,
            subnet=subnet1,
            alloc_type=IPADDRESS_TYPE.STICKY,
        )
        address2 = factory.make_StaticIPAddress(
            interface=interface,
            subnet=subnet2,
            alloc_type=IPADDRESS_TYPE.STICKY,
        )

        self.assertEqual(
            dhcp.get_ntp_server_addresses_for_rack(rack),
            {
                (space1.id, subnet1.get_ipnetwork().version): address1.ip,
                (space2.id, subnet2.get_ipnetwork().version): address2.ip,
            },
        )

    def test_returned_dict_chooses_minimum_address(self):
        rack = factory.make_RackController()
        space = factory.make_Space()
        cidr = factory.make_ip4_or_6_network(host_bits=16)
        subnet = factory.make_Subnet(space=space, cidr=cidr)
        interface = factory.make_Interface(node=rack)
        addresses = {
            factory.make_StaticIPAddress(
                interface=interface,
                subnet=subnet,
                alloc_type=IPADDRESS_TYPE.STICKY,
            )
            for _ in range(10)
        }

        self.assertEqual(
            dhcp.get_ntp_server_addresses_for_rack(rack),
            {
                (space.id, subnet.get_ipnetwork().version): min(
                    (address.ip for address in addresses), key=IPAddress
                )
            },
        )

    def test_returned_dict_prefers_vlans_with_dhcp_on(self):
        rack = factory.make_RackController()
        space = factory.make_Space()
        ip_version = random.choice([4, 6])
        cidr1 = factory.make_ip4_or_6_network(version=ip_version, host_bits=16)
        cidr2 = factory.make_ip4_or_6_network(version=ip_version, host_bits=16)
        subnet1 = factory.make_Subnet(space=space, cidr=cidr1)
        subnet2 = factory.make_Subnet(space=space, cidr=cidr2)
        # Expect subnet2 to be selected, since DHCP is enabled.
        subnet2.vlan.dhcp_on = True

        with post_commit_hooks:
            subnet2.vlan.save()

        interface = factory.make_Interface(node=rack)
        # Make some addresses that won't be selected since they're on the
        # incorrect VLAN (without DHCP enabled).
        for _ in range(3):
            factory.make_StaticIPAddress(
                interface=interface,
                subnet=subnet1,
                alloc_type=IPADDRESS_TYPE.STICKY,
            )
        expected_address = factory.make_StaticIPAddress(
            interface=interface,
            subnet=subnet2,
            alloc_type=IPADDRESS_TYPE.STICKY,
        )
        self.assertEqual(
            dhcp.get_ntp_server_addresses_for_rack(rack),
            {
                (
                    space.id,
                    subnet2.get_ipnetwork().version,
                ): expected_address.ip
            },
        )

    def test_constant_query_count(self):
        rack = factory.make_RackController()
        interface = factory.make_Interface(node=rack)

        count, result = count_queries(
            dhcp.get_ntp_server_addresses_for_rack, rack
        )
        self.assertEqual(1, count)
        self.assertEqual({}, result)

        for _ in (1, 2):
            space = factory.make_Space()
            for family in (4, 6):
                cidr = factory.make_ip4_or_6_network(family, host_bits=8)
                subnet = factory.make_Subnet(space=space, cidr=cidr)
                for _ in (1, 2):
                    factory.make_StaticIPAddress(
                        interface=interface,
                        subnet=subnet,
                        alloc_type=IPADDRESS_TYPE.STICKY,
                    )

        count, result = count_queries(
            dhcp.get_ntp_server_addresses_for_rack, rack
        )
        self.assertEqual(1, count)
        self.assertNotEqual({}, result)


class TestGetDefaultDNSServers(MAASServerTestCase):
    """Tests for `get_default_dns_servers`."""

    def test_returns_default_region_ip_if_no_url_found(self):
        mock_get_source_address = self.patch(dhcp, "get_source_address")
        mock_get_source_address.return_value = "10.0.0.1"
        vlan = factory.make_VLAN()
        rack_controller = factory.make_RackController(interface=False, url="")
        subnet = factory.make_Subnet(vlan=vlan, cidr="10.0.0.0/24")
        servers = get_default_dns_servers(rack_controller, subnet)
        self.assertEqual([IPAddress("10.0.0.1")], servers)

    def test_returns_address_from_region_url_if_url_specified(self):
        mock_get_source_address = self.patch(dhcp, "get_source_address")
        mock_get_source_address.return_value = "10.0.0.1"
        vlan = factory.make_VLAN()
        rack_controller = factory.make_RackController(
            interface=False, url="http://192.168.0.1:5240/MAAS/"
        )
        subnet = factory.make_Subnet(vlan=vlan, cidr="10.0.0.0/24")
        servers = get_default_dns_servers(rack_controller, subnet)
        self.assertEqual([IPAddress("192.168.0.1")], servers)

    def test_chooses_alternate_from_known_reachable_subnet_no_proxy(self):
        mock_get_source_address = self.patch(dhcp, "get_source_address")
        mock_get_source_address.return_value = "10.0.0.1"
        vlan = factory.make_VLAN()
        r1 = factory.make_RegionRackController(interface=False)
        self.patch(server_address_module.MAAS_ID, "get").return_value = (
            r1.system_id
        )
        r2 = factory.make_RegionRackController(interface=False)
        subnet = factory.make_Subnet(vlan=vlan, cidr="10.0.0.0/24")
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=r2
        )
        address = factory.make_StaticIPAddress(
            interface=interface,
            subnet=subnet,
            alloc_type=IPADDRESS_TYPE.STICKY,
        )
        servers = get_default_dns_servers(r1, subnet, False)
        self.assertEqual(
            [IPAddress(address.ip), IPAddress("10.0.0.1")], servers
        )

    def test_racks_on_subnet_comes_before_region(self):
        mock_get_source_address = self.patch(dhcp, "get_source_address")
        mock_get_source_address.return_value = "10.0.0.1"
        vlan = factory.make_VLAN()
        r1 = factory.make_RegionRackController(interface=False)
        self.patch(server_address_module.MAAS_ID, "get").return_value = (
            r1.system_id
        )
        subnet = factory.make_Subnet(vlan=vlan, cidr="10.0.0.0/24")
        r1_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=r1
        )
        r1_address = factory.make_StaticIPAddress(
            interface=r1_interface,
            subnet=subnet,
            alloc_type=IPADDRESS_TYPE.STICKY,
        )
        r2 = factory.make_RegionRackController(interface=False)
        r2_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=r2
        )
        r2_address = factory.make_StaticIPAddress(
            interface=r2_interface,
            subnet=subnet,
            alloc_type=IPADDRESS_TYPE.STICKY,
        )
        servers = get_default_dns_servers(r1, subnet, False)
        self.assertCountEqual(
            servers[0:-1], [IPAddress(r1_address.ip), IPAddress(r2_address.ip)]
        )
        self.assertEqual(IPAddress("10.0.0.1"), servers[-1])

    def test_doesnt_include_remote_region_ip(self):
        # Regression test for LP:1881133
        mock_get_source_address = self.patch(dhcp, "get_source_address")
        mock_get_source_address.return_value = "192.168.122.209"
        rack = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN(dhcp_on=True, primary_rack=rack)
        subnet = factory.make_Subnet(vlan=vlan, cidr="192.168.200.0/24")
        iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack
        )
        factory.make_StaticIPAddress(
            interface=iface,
            subnet=subnet,
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip="192.168.200.1",
        )

        servers = get_default_dns_servers(rack, subnet)
        self.assertEqual([IPAddress("192.168.200.1")], servers)

    def test_dns_servers_when_relaying(self):
        mock_get_source_address = self.patch(dhcp, "get_source_address")
        mock_get_source_address.return_value = "10.20.30.1"
        rack = factory.make_RackController(interface=False)
        vlan1_primary = factory.make_VLAN(dhcp_on=True, primary_rack=rack)
        vlan2_secondary = factory.make_VLAN(
            primary_rack=rack, dhcp_on=False, relay_vlan=vlan1_primary
        )
        subnet1 = factory.make_Subnet(
            vlan=vlan1_primary, vid=10, cidr="10.20.40.0/24"
        )
        subnet2 = factory.make_Subnet(
            vlan=vlan2_secondary, vid=20, cidr="10.20.50.0/24"
        )
        rack_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack
        )
        rack_interface_vlan1 = factory.make_Interface(
            INTERFACE_TYPE.VLAN,
            vlan=vlan1_primary,
            parents=[rack_interface],
            node=rack,
        )
        factory.make_Interface(
            INTERFACE_TYPE.VLAN,
            vlan=vlan2_secondary,
            parents=[rack_interface],
            node=rack,
        )
        factory.make_StaticIPAddress(
            interface=rack_interface_vlan1,
            subnet=subnet1,
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip="10.20.40.1",
        )
        dns_servers = dhcp.get_default_dns_servers(
            rack, subnet2, use_rack_proxy=True
        )
        self.assertEqual(dns_servers, [IPAddress("10.20.40.1")])

    def test_no_default_region_ip(self):
        self.patch(dhcp, "get_source_address").return_value = None
        vlan = factory.make_VLAN()
        rack_controller = factory.make_RackController(
            interface=False, url="http://unknown:5240/MAAS/"
        )
        subnet = factory.make_Subnet(vlan=vlan, cidr="10.0.0.0/24")
        servers = get_default_dns_servers(rack_controller, subnet)
        self.assertEqual(servers, [])


class TestMakeSubnetConfig(MAASServerTestCase):
    """Tests for `make_subnet_config`."""

    def test_includes_all_parameters(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller,
            subnet,
            [factory.make_ipv4_address()],
            [factory.make_name("ntp")],
            default_domain,
            search_list=default_domain.name,
        )
        self.assertIsInstance(config, dict)
        self.assertGreaterEqual(
            config.keys(),
            {
                "subnet",
                "subnet_mask",
                "subnet_cidr",
                "broadcast_ip",
                "router_ip",
                "dns_servers",
                "ntp_servers",
                "domain_name",
                "search_list",
                "pools",
                "dhcp_snippets",
                "disabled_boot_architectures",
            },
        )

    def test_sets_ipv4_dns_from_arguments(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan, dns_servers=[], version=4)
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        maas_dns = IPAddress(factory.make_ipv4_address())
        ntp_servers = [factory.make_name("ntp")]
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller, subnet, [maas_dns], ntp_servers, default_domain
        )
        self.assertEqual([maas_dns], config["dns_servers"])

    def test_sets_ipv6_dns_from_arguments(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan, dns_servers=[], version=6)
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        maas_dns = IPAddress(factory.make_ipv6_address())
        ntp_servers = [factory.make_name("ntp")]
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller, subnet, [maas_dns], ntp_servers, default_domain
        )
        self.assertEqual([maas_dns], config["dns_servers"])

    def test_sets_ntp_from_list_argument(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan, dns_servers=[])
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        ntp_servers = [factory.make_name("ntp")]
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller, subnet, [""], ntp_servers, default_domain
        )
        self.assertEqual(config["ntp_servers"], ntp_servers)

    def test_sets_ntp_from_empty_dict_argument(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan, dns_servers=[])
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller, subnet, [""], {}, default_domain
        )
        self.assertEqual(config["ntp_servers"], [])

    def test_sets_ntp_from_dict_argument(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan, dns_servers=[], space=None)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        address = factory.make_StaticIPAddress(
            interface=interface,
            subnet=subnet,
            alloc_type=IPADDRESS_TYPE.STICKY,
        )
        ntp_servers = {
            (vlan.space_id, subnet.get_ipnetwork().version): address.ip
        }
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller, subnet, [""], ntp_servers, default_domain
        )
        self.assertEqual(config["ntp_servers"], [address.ip])

    def test_sets_ntp_from_dict_argument_with_alternates(self):
        r1 = factory.make_RackController(interface=False)
        r2 = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN(primary_rack=r1, secondary_rack=r2)
        subnet = factory.make_Subnet(vlan=vlan, dns_servers=[], space=None)
        r1_eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=r1
        )
        r2_eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=r2
        )
        a1 = factory.make_StaticIPAddress(
            interface=r1_eth0, subnet=subnet, alloc_type=IPADDRESS_TYPE.STICKY
        )
        a2 = factory.make_StaticIPAddress(
            interface=r2_eth0, subnet=subnet, alloc_type=IPADDRESS_TYPE.STICKY
        )
        r1_ntp_servers = {
            (vlan.space_id, subnet.get_ipnetwork().version): a1.ip
        }
        r2_ntp_servers = {
            (vlan.space_id, subnet.get_ipnetwork().version): a2.ip
        }
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            r1, subnet, [""], r1_ntp_servers, default_domain, peer_rack=r2
        )
        self.assertEqual(config["ntp_servers"], [a1.ip, a2.ip])
        config = dhcp.make_subnet_config(
            r2, subnet, [""], r2_ntp_servers, default_domain, peer_rack=r1
        )
        self.assertEqual(config["ntp_servers"], [a2.ip, a1.ip])

    def test_ipv4_dns_from_subnet(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(
            vlan=vlan, version=4, dns_servers=["8.8.8.8", "8.8.4.4"]
        )
        maas_dns = IPAddress(factory.make_ipv4_address())
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        ntp_servers = [factory.make_name("ntp")]
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller, subnet, [maas_dns], ntp_servers, default_domain
        )
        self.assertEqual(
            [maas_dns, IPAddress("8.8.8.8"), IPAddress("8.8.4.4")],
            config["dns_servers"],
        )

    def test_ipv4_rack_dns_from_subnet(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan, version=4, dns_servers=[])
        maas_dns = IPAddress(factory.make_ipv4_address())
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        ntp_servers = [factory.make_name("ntp")]
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller, subnet, [maas_dns], ntp_servers, default_domain
        )
        self.assertEqual([maas_dns], config["dns_servers"])

    def test_ipv4_user_dns_from_subnet(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(
            vlan=vlan,
            version=4,
            allow_dns=False,
            dns_servers=["8.8.8.8", "8.8.4.4"],
        )
        maas_dns = IPAddress(factory.make_ipv4_address())
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        ntp_servers = [factory.make_name("ntp")]
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller, subnet, [maas_dns], ntp_servers, default_domain
        )
        self.assertEqual(
            [IPAddress("8.8.8.8"), IPAddress("8.8.4.4")],
            config["dns_servers"],
        )

    def test_ipv4_no_dns_from_subnet(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(
            vlan=vlan, version=4, allow_dns=False, dns_servers=[]
        )
        maas_dns = IPAddress(factory.make_ipv4_address())
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        ntp_servers = [factory.make_name("ntp")]
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller, subnet, [maas_dns], ntp_servers, default_domain
        )
        self.assertEqual([], config["dns_servers"])

    def test_ipv6_dns_from_subnet(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(
            vlan=vlan, version=6, dns_servers=["2001:db8::1", "2001:db8::2"]
        )
        maas_dns = IPAddress(factory.make_ipv6_address())
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        ntp_servers = [factory.make_name("ntp")]
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller, subnet, [maas_dns], ntp_servers, default_domain
        )
        self.assertEqual(
            config["dns_servers"],
            [maas_dns, IPAddress("2001:db8::1"), IPAddress("2001:db8::2")],
        )

    def test_ipv6_rack_dns_from_subnet(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan, version=6, dns_servers=[])
        maas_dns = IPAddress(factory.make_ipv6_address())
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        ntp_servers = [factory.make_name("ntp")]
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller, subnet, [maas_dns], ntp_servers, default_domain
        )
        self.assertEqual([maas_dns], config["dns_servers"])

    def test_ipv6_user_dns_from_subnet(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(
            vlan=vlan,
            version=6,
            allow_dns=False,
            dns_servers=["2001:db8::1", "2001:db8::2"],
        )
        maas_dns = IPAddress(factory.make_ipv6_address())
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        ntp_servers = [factory.make_name("ntp")]
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller, subnet, [maas_dns], ntp_servers, default_domain
        )
        self.assertEqual(
            [IPAddress("2001:db8::1"), IPAddress("2001:db8::2")],
            config["dns_servers"],
        )

    def test_ipv6_no_dns_from_subnet(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(
            vlan=vlan, version=6, allow_dns=False, dns_servers=[]
        )
        maas_dns = IPAddress(factory.make_ipv6_address())
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        ntp_servers = [factory.make_name("ntp")]
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller, subnet, [maas_dns], ntp_servers, default_domain
        )
        self.assertEqual([], config["dns_servers"])

    def test_sets_domain_name_from_passed_domain(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller,
            subnet,
            [factory.make_ipv4_address()],
            [factory.make_name("ntp")],
            default_domain,
        )
        self.assertEqual(config["domain_name"], default_domain.name)

    def test_sets_other_items_from_subnet_and_interface(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller,
            subnet,
            [factory.make_ipv4_address()],
            [factory.make_name("ntp")],
            default_domain,
        )
        self.assertEqual(
            config["broadcast_ip"],
            str(subnet.get_ipnetwork().broadcast),
        )
        self.assertEqual(config["router_ip"], subnet.gateway_ip)

    def test_passes_IP_addresses_as_strings(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller,
            subnet,
            [factory.make_ipv4_address()],
            [factory.make_name("ntp")],
            default_domain,
        )
        self.assertIsInstance(config["subnet"], str)
        self.assertIsInstance(config["subnet_mask"], str)
        self.assertIsInstance(config["subnet_cidr"], str)
        self.assertIsInstance(config["broadcast_ip"], str)
        self.assertIsInstance(config["router_ip"], str)

    def test_defines_IPv4_subnet(self):
        network = IPNetwork("10.9.8.7/24")
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(cidr=str(network.cidr), vlan=vlan)
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        default_domain = Domain.objects.get_default_domain()
        search_list = [default_domain.name, "foo.example.com"]
        config = dhcp.make_subnet_config(
            rack_controller,
            subnet,
            [factory.make_ipv4_address()],
            [factory.make_name("ntp")],
            default_domain,
            search_list=search_list,
        )
        self.assertEqual(config["subnet"], "10.9.8.0")
        self.assertEqual(config["subnet_mask"], "255.255.255.0")
        self.assertEqual(config["subnet_cidr"], "10.9.8.0/24")
        self.assertEqual(config["broadcast_ip"], "10.9.8.255")
        self.assertEqual(config["domain_name"], default_domain.name)
        self.assertEqual(
            config["search_list"],
            [default_domain.name, "foo.example.com"],
        )

    def test_defines_IPv6_subnet(self):
        network = IPNetwork("fd38:c341:27da:c831::/64")
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(cidr=str(network.cidr), vlan=vlan)
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        default_domain = Domain.objects.get_default_domain()
        search_list = [default_domain.name, "foo.example.com"]
        config = dhcp.make_subnet_config(
            rack_controller,
            subnet,
            [factory.make_ipv6_address()],
            [factory.make_name("ntp")],
            default_domain,
            search_list=search_list,
        )
        # Don't expect a specific literal value, like we do for IPv4; there
        # are different spellings.
        self.assertEqual(
            IPAddress(config["subnet"]),
            IPAddress("fd38:c341:27da:c831::"),
        )
        # (Netmask is not used for the IPv6 config, so ignore it.)
        self.assertEqual(
            IPNetwork(config["subnet_cidr"]),
            IPNetwork("fd38:c341:27da:c831::/64"),
        )
        self.assertEqual(
            config["search_list"],
            [default_domain.name, "foo.example.com"],
        )

    def test_returns_multiple_pools(self):
        network = IPNetwork("10.9.8.0/24")
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(cidr=str(network.cidr), vlan=vlan)
        factory.make_IPRange(subnet, "10.9.8.11", "10.9.8.20")
        factory.make_IPRange(subnet, "10.9.8.21", "10.9.8.30")
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller,
            subnet,
            [factory.make_ipv4_address()],
            [factory.make_name("ntp")],
            default_domain,
        )
        self.assertEqual(
            [
                {
                    "ip_range_low": "10.9.8.11",
                    "ip_range_high": "10.9.8.20",
                    "dhcp_snippets": [],
                },
                {
                    "ip_range_low": "10.9.8.21",
                    "ip_range_high": "10.9.8.30",
                    "dhcp_snippets": [],
                },
            ],
            config["pools"],
        )
        self.assertEqual(config["domain_name"], default_domain.name)

    def test_returns_multiple_pools_with_failover_peer(self):
        network = IPNetwork("10.9.8.0/24")
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(cidr=str(network.cidr), vlan=vlan)
        factory.make_IPRange(subnet, "10.9.8.11", "10.9.8.20")
        factory.make_IPRange(subnet, "10.9.8.21", "10.9.8.30")
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        default_domain = Domain.objects.get_default_domain()
        failover_peer = factory.make_name("peer")
        config = dhcp.make_subnet_config(
            rack_controller,
            subnet,
            [factory.make_ipv4_address()],
            [factory.make_name("ntp")],
            default_domain,
            failover_peer=failover_peer,
        )
        self.assertEqual(
            [
                {
                    "ip_range_low": "10.9.8.11",
                    "ip_range_high": "10.9.8.20",
                    "failover_peer": failover_peer,
                    "dhcp_snippets": [],
                },
                {
                    "ip_range_low": "10.9.8.21",
                    "ip_range_high": "10.9.8.30",
                    "failover_peer": failover_peer,
                    "dhcp_snippets": [],
                },
            ],
            config["pools"],
        )

    def test_doesnt_convert_None_router_ip(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        default_domain = Domain.objects.get_default_domain()
        subnet.gateway_ip = None
        subnet.save()
        config = dhcp.make_subnet_config(
            rack_controller,
            subnet,
            [factory.make_ipv4_address()],
            [factory.make_name("ntp")],
            default_domain,
        )
        self.assertEqual("", config["router_ip"])

    def test_returns_dhcp_snippets(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        default_domain = Domain.objects.get_default_domain()
        dhcp_snippets = [
            factory.make_DHCPSnippet(subnet=subnet, enabled=True)
            for _ in range(3)
        ]
        config = dhcp.make_subnet_config(
            rack_controller,
            subnet,
            [factory.make_ipv4_address()],
            [factory.make_name("ntp")],
            default_domain,
            subnets_dhcp_snippets=dhcp_snippets,
        )
        self.assertCountEqual(
            [
                {
                    "name": dhcp_snippet.name,
                    "description": dhcp_snippet.description,
                    "value": dhcp_snippet.value.data,
                }
                for dhcp_snippet in dhcp_snippets
            ],
            config["dhcp_snippets"],
        )

    def test_returns_disabled_boot_architectures(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller,
            subnet,
            [factory.make_ipv4_address()],
            [factory.make_name("ntp")],
            default_domain,
        )
        self.assertEqual(
            subnet.disabled_boot_architectures,
            config["disabled_boot_architectures"],
        )

    def test_returns_iprange_dhcp_snippets(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_ipv4_Subnet_with_IPRanges(vlan=vlan)
        iprange = subnet.get_dynamic_ranges().first()
        iprange.save()
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        default_domain = Domain.objects.get_default_domain()
        subnet_snippets = [
            factory.make_DHCPSnippet(subnet=subnet, enabled=True)
            for _ in range(3)
        ]
        iprange_snippets = [
            factory.make_DHCPSnippet(
                subnet=subnet, iprange=iprange, enabled=True
            )
            for _ in range(3)
        ]
        dhcp_snippets = subnet_snippets + iprange_snippets
        config = dhcp.make_subnet_config(
            rack_controller,
            subnet,
            [factory.make_ipv4_address()],
            [factory.make_name("ntp")],
            default_domain,
            subnets_dhcp_snippets=dhcp_snippets,
        )
        self.assertCountEqual(
            [
                {
                    "name": dhcp_snippet.name,
                    "description": dhcp_snippet.description,
                    "value": dhcp_snippet.value.data,
                }
                for dhcp_snippet in subnet_snippets
            ],
            config["dhcp_snippets"],
        )
        self.assertCountEqual(
            [
                {
                    "name": dhcp_snippet.name,
                    "description": dhcp_snippet.description,
                    "value": dhcp_snippet.value.data,
                }
                for dhcp_snippet in iprange_snippets
            ],
            config["pools"][0]["dhcp_snippets"],
        )

    def test_subnet_without_gateway_restricts_nameservers(self):
        network1 = IPNetwork("10.9.8.0/24")
        network2 = IPNetwork("10.9.9.0/24")
        rackip1 = "10.9.8.1"
        rackip2 = "10.9.9.1"
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet1 = factory.make_Subnet(cidr=str(network1.cidr), vlan=vlan)
        subnet2 = factory.make_Subnet(
            cidr=str(network2.cidr), vlan=vlan, gateway_ip=None
        )
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        default_domain = Domain.objects.get_default_domain()
        config = dhcp.make_subnet_config(
            rack_controller,
            subnet1,
            [rackip1, rackip2],
            [factory.make_name("ntp")],
            default_domain,
        )
        self.assertIn(rackip1, config["dns_servers"])
        self.assertIn(rackip2, config["dns_servers"])
        config = dhcp.make_subnet_config(
            rack_controller,
            subnet2,
            [rackip1, rackip2],
            [factory.make_name("ntp")],
            default_domain,
        )
        self.assertNotIn(rackip1, config["dns_servers"])
        self.assertIn(rackip2, config["dns_servers"])


class TestMakeHostsForSubnet(MAASServerTestCase):
    def tests__returns_defined_hosts(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        node = factory.make_Node(interface=False)

        # Make AUTO IP without an IP. Should not be in output.
        auto_no_ip_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=subnet.vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=subnet,
            interface=auto_no_ip_interface,
        )

        # Make AUTO IP with an IP. Should be in the output.
        auto_with_ip_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=subnet.vlan
        )
        auto_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet,
            interface=auto_with_ip_interface,
        )

        # Make temp AUTO IP with an IP. Should not be in the output.
        auto_no_temp_ip_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=subnet.vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet,
            interface=auto_no_temp_ip_interface,
            temp_expires_on=timezone.now(),
        )

        # Make STICKY IP. Should be in the output.
        sticky_ip_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=subnet.vlan
        )
        sticky_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet,
            interface=sticky_ip_interface,
        )

        # Make DISCOVERED IP. Should not be in the output.
        discovered_ip_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=subnet.vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            subnet=subnet,
            interface=discovered_ip_interface,
        )

        # Make USER_RESERVED IP on Device. Should be in the output.
        device = factory.make_Device(interface=False)
        device_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device, vlan=subnet.vlan
        )
        device_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            subnet=subnet,
            interface=device_interface,
        )

        # Make USER_RESERVED IP on Unknown interface. Should be in the output.
        unknown_interface = factory.make_Interface(
            INTERFACE_TYPE.UNKNOWN, vlan=subnet.vlan
        )
        unknown_reserved_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            subnet=subnet,
            interface=unknown_interface,
        )

        # Add DHCP some DHCP snippets
        node_dhcp_snippets = [
            factory.make_DHCPSnippet(node=node, enabled=True) for _ in range(3)
        ]
        device_dhcp_snippets = [
            factory.make_DHCPSnippet(node=device, enabled=True)
            for _ in range(3)
        ]

        # Make an IP reservation
        reserved_ip = factory.make_ReservedIP(
            factory.pick_ip_in_network(
                IPNetwork(subnet.cidr),
                but_not=factory._get_exclude_list(subnet),
            ),
            subnet,
            factory.make_mac_address(),
        )

        expected_hosts = [
            {
                "host": f"{node.hostname}-{auto_with_ip_interface.name}",
                "mac": str(auto_with_ip_interface.mac_address),
                "ip": str(auto_ip.ip),
                "dhcp_snippets": [
                    {
                        "name": dhcp_snippet.name,
                        "description": dhcp_snippet.description,
                        "value": dhcp_snippet.value.data,
                    }
                    for dhcp_snippet in node_dhcp_snippets
                ],
            },
            {
                "host": f"{node.hostname}-{sticky_ip_interface.name}",
                "mac": str(sticky_ip_interface.mac_address),
                "ip": str(sticky_ip.ip),
                "dhcp_snippets": [
                    {
                        "name": dhcp_snippet.name,
                        "description": dhcp_snippet.description,
                        "value": dhcp_snippet.value.data,
                    }
                    for dhcp_snippet in node_dhcp_snippets
                ],
            },
            {
                "host": f"{device.hostname}-{device_interface.name}",
                "mac": str(device_interface.mac_address),
                "ip": str(device_ip.ip),
                "dhcp_snippets": [
                    {
                        "name": dhcp_snippet.name,
                        "description": dhcp_snippet.description,
                        "value": dhcp_snippet.value.data,
                    }
                    for dhcp_snippet in device_dhcp_snippets
                ],
            },
            {
                "host": "unknown-%s-%s"
                % (unknown_interface.id, unknown_interface.name),
                "mac": str(unknown_interface.mac_address),
                "ip": str(unknown_reserved_ip.ip),
                "dhcp_snippets": [],
            },
            {
                "host": "",
                "mac": str(reserved_ip.mac_address),
                "ip": str(reserved_ip.ip),
                "dhcp_snippets": [],
            },
        ]
        self.assertCountEqual(
            expected_hosts,
            dhcp.make_hosts_for_subnets(
                [subnet], node_dhcp_snippets + device_dhcp_snippets
            ),
        )

    def tests__returns_hosts_interface_once_when_on_multiple_subnets(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        node = factory.make_Node(interface=False)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=node
        )
        subnet_one = factory.make_Subnet(vlan=vlan)
        ip_one = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet_one,
            interface=interface,
        )
        subnet_two = factory.make_Subnet(vlan=vlan)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet_two,
            interface=interface,
        )

        expected_hosts = [
            {
                "host": f"{node.hostname}-{interface.name}",
                "mac": str(interface.mac_address),
                "ip": str(ip_one.ip),
                "dhcp_snippets": [],
            }
        ]
        self.assertCountEqual(
            expected_hosts,
            dhcp.make_hosts_for_subnets([subnet_one, subnet_two]),
        )

    def tests__returns_hosts_for_bond(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        node = factory.make_Node(interface=False)

        # Create a bond with an IP address, to make sure all MAC address in
        # that bond get the same address.
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, name="eth0", vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, name="eth1", vlan=vlan
        )
        eth2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, name="eth2", vlan=vlan
        )
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND,
            node=node,
            name="bond0",
            mac_address=eth2.mac_address,
            parents=[eth0, eth1, eth2],
            vlan=vlan,
        )
        auto_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, subnet=subnet, interface=bond0
        )

        expected_hosts = [
            {
                "host": "%s-bond0" % node.hostname,
                "mac": str(bond0.mac_address),
                "ip": str(auto_ip.ip),
                "dhcp_snippets": [],
            },
            {
                "host": "%s-eth0" % node.hostname,
                "mac": str(eth0.mac_address),
                "ip": str(auto_ip.ip),
                "dhcp_snippets": [],
            },
            {
                "host": "%s-eth1" % node.hostname,
                "mac": str(eth1.mac_address),
                "ip": str(auto_ip.ip),
                "dhcp_snippets": [],
            },
        ]

        self.assertCountEqual(
            expected_hosts, dhcp.make_hosts_for_subnets([subnet])
        )

    def tests__returns_hosts_first_created_ip_address(self):
        rack_controller = factory.make_RackController(interface=False)
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=rack_controller
        )
        node = factory.make_Node(interface=False)

        # Add two IP address to interface. Only the first should be added.
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan
        )
        auto_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, subnet=subnet, interface=eth0
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, subnet=subnet, interface=eth0
        )

        expected_hosts = [
            {
                "host": f"{node.hostname}-{eth0.name}",
                "mac": str(eth0.mac_address),
                "ip": str(auto_ip.ip),
                "dhcp_snippets": [],
            }
        ]

        self.assertEqual(expected_hosts, dhcp.make_hosts_for_subnets([subnet]))


class TestMakeFailoverPeerConfig(MAASServerTestCase):
    """Tests for `make_failover_peer_config`."""

    def test_renders_config_for_primary(self):
        primary_rack = factory.make_RackController()
        secondary_rack = factory.make_RackController()
        vlan = factory.make_VLAN(
            dhcp_on=True,
            primary_rack=primary_rack,
            secondary_rack=secondary_rack,
        )
        subnet = factory.make_Subnet(vlan=vlan, version=4)
        primary_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=primary_rack, vlan=vlan
        )
        primary_ip = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet),
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet,
            interface=primary_interface,
        )
        secondary_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=secondary_rack, vlan=vlan
        )
        secondary_ip = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet),
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet,
            interface=secondary_interface,
        )
        failover_peer_name = "failover-vlan-%d" % vlan.id
        self.assertEqual(
            (
                failover_peer_name,
                {
                    "name": failover_peer_name,
                    "mode": "primary",
                    "address": str(primary_ip.ip),
                    "peer_address": str(secondary_ip.ip),
                },
                secondary_rack,
            ),
            dhcp.make_failover_peer_config(vlan, primary_rack, 4),
        )

    def test_renders_config_for_secondary(self):
        primary_rack = factory.make_RackController()
        secondary_rack = factory.make_RackController()
        vlan = factory.make_VLAN(
            dhcp_on=True,
            primary_rack=primary_rack,
            secondary_rack=secondary_rack,
        )
        subnet = factory.make_Subnet(vlan=vlan, version=4)
        primary_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=primary_rack, vlan=vlan
        )
        primary_ip = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet),
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet,
            interface=primary_interface,
        )
        secondary_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=secondary_rack, vlan=vlan
        )
        secondary_ip = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet),
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet,
            interface=secondary_interface,
        )
        failover_peer_name = "failover-vlan-%d" % vlan.id
        self.assertEqual(
            (
                failover_peer_name,
                {
                    "name": failover_peer_name,
                    "mode": "secondary",
                    "address": str(secondary_ip.ip),
                    "peer_address": str(primary_ip.ip),
                },
                primary_rack,
            ),
            dhcp.make_failover_peer_config(vlan, secondary_rack, 4),
        )

    # See https://bugs.launchpad.net/maas/+bug/2027621
    def test_renders_config_for_secondary_should_not_mix_v4_and_v6_addresses(
        self,
    ):
        primary_rack = factory.make_RackController()
        secondary_rack = factory.make_RackController()
        vlan = factory.make_VLAN(
            dhcp_on=True,
            primary_rack=primary_rack,
            secondary_rack=secondary_rack,
        )
        subnet_v4 = factory.make_Subnet(vlan=vlan, version=4)
        subnet_v6 = factory.make_Subnet(vlan=vlan, version=6)
        primary_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=primary_rack, vlan=vlan
        )
        primary_ip_v4 = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet_v4),
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet_v4,
            interface=primary_interface,
        )
        primary_ip_v6 = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet_v6),
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet_v6,
            interface=primary_interface,
        )
        secondary_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=secondary_rack, vlan=vlan
        )
        secondary_ip_v4 = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet_v4),
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet_v4,
            interface=secondary_interface,
        )
        secondary_ip_v6 = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet_v6),
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet_v6,
            interface=secondary_interface,
        )
        failover_peer_name = "failover-vlan-%d" % vlan.id
        self.assertEqual(
            (
                failover_peer_name,
                {
                    "name": failover_peer_name,
                    "mode": "secondary",
                    "address": str(secondary_ip_v4.ip),
                    "peer_address": str(primary_ip_v4.ip),
                },
                primary_rack,
            ),
            dhcp.make_failover_peer_config(vlan, secondary_rack, 4),
        )
        self.assertEqual(
            (
                failover_peer_name,
                {
                    "name": failover_peer_name,
                    "mode": "secondary",
                    "address": str(secondary_ip_v6.ip),
                    "peer_address": str(primary_ip_v6.ip),
                },
                primary_rack,
            ),
            dhcp.make_failover_peer_config(vlan, secondary_rack, 6),
        )


class TestGetDHCPConfigureFor(MAASServerTestCase):
    """Tests for `get_dhcp_configure_for`."""

    def test_returns_for_ipv4(self):
        primary_rack = factory.make_RackController()
        secondary_rack = factory.make_RackController()

        # VLAN for primary that has a secondary with multiple subnets.
        ha_vlan = factory.make_VLAN(
            dhcp_on=True,
            primary_rack=primary_rack,
            secondary_rack=secondary_rack,
        )
        ha_subnet = factory.make_ipv4_Subnet_with_IPRanges(
            vlan=ha_vlan, allow_dns=False, dns_servers=["127.0.0.1"]
        )
        ha_network = ha_subnet.get_ipnetwork()
        ha_dhcp_snippets = [
            factory.make_DHCPSnippet(subnet=ha_subnet, enabled=True)
            for _ in range(3)
        ]
        primary_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=primary_rack, vlan=ha_vlan
        )
        primary_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=ha_subnet,
            interface=primary_interface,
        )
        secondary_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=secondary_rack, vlan=ha_vlan
        )
        secondary_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=ha_subnet,
            interface=secondary_interface,
        )
        other_subnet = factory.make_ipv4_Subnet_with_IPRanges(
            vlan=ha_vlan, allow_dns=False, dns_servers=["127.0.0.1"]
        )
        other_network = other_subnet.get_ipnetwork()
        other_dhcp_snippets = [
            factory.make_DHCPSnippet(subnet=other_subnet, enabled=True)
            for _ in range(3)
        ]
        factory.make_ReservedIP(
            factory.pick_ip_in_network(
                IPNetwork(ha_subnet.cidr),
                but_not=factory._get_exclude_list(ha_subnet),
            ),
            ha_subnet,
            factory.make_mac_address(),
        )

        ntp_servers = [factory.make_name("ntp")]
        default_domain = Domain.objects.get_default_domain()
        search_list = [default_domain.name, "foo.example.com"]
        (
            observed_failover,
            observed_subnets,
            observed_hosts,
            observed_interface,
        ) = dhcp.get_dhcp_configure_for(
            4,
            primary_rack,
            ha_vlan,
            [ha_subnet, other_subnet],
            ntp_servers,
            default_domain,
            search_list=search_list,
            dhcp_snippets=DHCPSnippet.objects.all(),
        )

        self.assertEqual(
            {
                "name": "failover-vlan-%d" % ha_vlan.id,
                "mode": "primary",
                "address": str(primary_ip.ip),
                "peer_address": str(secondary_ip.ip),
            },
            observed_failover,
        )
        self.assertEqual(
            sorted(
                [
                    {
                        "subnet": str(ha_network.network),
                        "subnet_mask": str(ha_network.netmask),
                        "subnet_cidr": str(ha_network.cidr),
                        "broadcast_ip": str(ha_network.broadcast),
                        "router_ip": str(ha_subnet.gateway_ip),
                        "dns_servers": [IPAddress("127.0.0.1")],
                        "ntp_servers": ntp_servers,
                        "domain_name": default_domain.name,
                        "search_list": [
                            default_domain.name,
                            "foo.example.com",
                        ],
                        "dhcp_snippets": [
                            {
                                "name": dhcp_snippet.name,
                                "description": dhcp_snippet.description,
                                "value": dhcp_snippet.value.data,
                            }
                            for dhcp_snippet in ha_dhcp_snippets
                        ],
                        "disabled_boot_architectures": ha_subnet.disabled_boot_architectures,
                        "pools": [
                            {
                                "ip_range_low": str(ip_range.start_ip),
                                "ip_range_high": str(ip_range.end_ip),
                                "failover_peer": "failover-vlan-%d"
                                % ha_vlan.id,
                                "dhcp_snippets": [],
                            }
                            for ip_range in (
                                ha_subnet.get_dynamic_ranges().order_by("id")
                            )
                        ],
                    },
                    {
                        "subnet": str(other_network.network),
                        "subnet_mask": str(other_network.netmask),
                        "subnet_cidr": str(other_network.cidr),
                        "broadcast_ip": str(other_network.broadcast),
                        "router_ip": str(other_subnet.gateway_ip),
                        "dns_servers": [IPAddress("127.0.0.1")],
                        "ntp_servers": ntp_servers,
                        "domain_name": default_domain.name,
                        "search_list": [
                            default_domain.name,
                            "foo.example.com",
                        ],
                        "dhcp_snippets": [
                            {
                                "name": dhcp_snippet.name,
                                "description": dhcp_snippet.description,
                                "value": dhcp_snippet.value.data,
                            }
                            for dhcp_snippet in other_dhcp_snippets
                        ],
                        "disabled_boot_architectures": other_subnet.disabled_boot_architectures,
                        "pools": [
                            {
                                "ip_range_low": str(ip_range.start_ip),
                                "ip_range_high": str(ip_range.end_ip),
                                "failover_peer": "failover-vlan-%d"
                                % ha_vlan.id,
                                "dhcp_snippets": [],
                            }
                            for ip_range in (
                                other_subnet.get_dynamic_ranges().order_by(
                                    "id"
                                )
                            )
                        ],
                    },
                ],
                key=itemgetter("subnet"),
            ),
            observed_subnets,
        )
        self.assertCountEqual(
            dhcp.make_hosts_for_subnets([ha_subnet]), observed_hosts
        )
        self.assertEqual(primary_interface.name, observed_interface)

    def test_returns_for_ipv6(self):
        primary_rack = factory.make_RackController()
        secondary_rack = factory.make_RackController()

        # VLAN for primary that has a secondary with multiple subnets.
        ha_vlan = factory.make_VLAN(
            dhcp_on=True,
            primary_rack=primary_rack,
            secondary_rack=secondary_rack,
        )
        ha_subnet = factory.make_Subnet(
            vlan=ha_vlan, cidr="fd38:c341:27da:c831::/64"
        )
        ha_network = ha_subnet.get_ipnetwork()
        factory.make_IPRange(
            ha_subnet,
            "fd38:c341:27da:c831:0:1::",
            "fd38:c341:27da:c831:0:1:ffff:0",
        )
        ha_dhcp_snippets = [
            factory.make_DHCPSnippet(subnet=ha_subnet, enabled=True)
            for _ in range(3)
        ]
        primary_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=primary_rack, vlan=ha_vlan
        )
        primary_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=ha_subnet,
            interface=primary_interface,
        )
        secondary_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=secondary_rack, vlan=ha_vlan
        )
        secondary_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=ha_subnet,
            interface=secondary_interface,
        )
        other_subnet = factory.make_Subnet(
            vlan=ha_vlan, cidr="fd38:c341:27da:c832::/64"
        )
        other_network = other_subnet.get_ipnetwork()
        other_dhcp_snippets = [
            factory.make_DHCPSnippet(subnet=other_subnet, enabled=True)
            for _ in range(3)
        ]
        factory.make_ReservedIP(
            factory.pick_ip_in_network(
                IPNetwork(ha_subnet.cidr),
                but_not=factory._get_exclude_list(ha_subnet),
            ),
            ha_subnet,
            factory.make_mac_address(),
        )

        ntp_servers = [factory.make_name("ntp")]
        default_domain = Domain.objects.get_default_domain()
        (
            observed_failover,
            observed_subnets,
            observed_hosts,
            observed_interface,
        ) = dhcp.get_dhcp_configure_for(
            6,
            primary_rack,
            ha_vlan,
            [ha_subnet, other_subnet],
            ntp_servers,
            default_domain,
            dhcp_snippets=DHCPSnippet.objects.all(),
        )

        # Because developers running this unit test might not have an IPv6
        # address configured we remove the dns_servers from the generated
        # config.
        for observed_subnet in observed_subnets:
            del observed_subnet["dns_servers"]

        self.assertEqual(
            {
                "name": "failover-vlan-%d" % ha_vlan.id,
                "mode": "primary",
                "address": str(primary_ip.ip),
                "peer_address": str(secondary_ip.ip),
            },
            observed_failover,
        )
        self.assertEqual(
            sorted(
                [
                    {
                        "subnet": str(ha_network.network),
                        "subnet_mask": str(ha_network.netmask),
                        "subnet_cidr": str(ha_network.cidr),
                        "broadcast_ip": str(ha_network.broadcast),
                        "router_ip": str(ha_subnet.gateway_ip),
                        "ntp_servers": ntp_servers,
                        "domain_name": default_domain.name,
                        "dhcp_snippets": [
                            {
                                "name": dhcp_snippet.name,
                                "description": dhcp_snippet.description,
                                "value": dhcp_snippet.value.data,
                            }
                            for dhcp_snippet in ha_dhcp_snippets
                        ],
                        "disabled_boot_architectures": ha_subnet.disabled_boot_architectures,
                        "pools": [
                            {
                                "ip_range_low": str(ip_range.start_ip),
                                "ip_range_high": str(ip_range.end_ip),
                                "failover_peer": "failover-vlan-%d"
                                % ha_vlan.id,
                                "dhcp_snippets": [],
                            }
                            for ip_range in (
                                ha_subnet.get_dynamic_ranges().order_by("id")
                            )
                        ],
                    },
                    {
                        "subnet": str(other_network.network),
                        "subnet_mask": str(other_network.netmask),
                        "subnet_cidr": str(other_network.cidr),
                        "broadcast_ip": str(other_network.broadcast),
                        "router_ip": str(other_subnet.gateway_ip),
                        "ntp_servers": ntp_servers,
                        "domain_name": default_domain.name,
                        "dhcp_snippets": [
                            {
                                "name": dhcp_snippet.name,
                                "description": dhcp_snippet.description,
                                "value": dhcp_snippet.value.data,
                            }
                            for dhcp_snippet in other_dhcp_snippets
                        ],
                        "disabled_boot_architectures": other_subnet.disabled_boot_architectures,
                        "pools": [
                            {
                                "ip_range_low": str(ip_range.start_ip),
                                "ip_range_high": str(ip_range.end_ip),
                                "failover_peer": "failover-vlan-%d"
                                % ha_vlan.id,
                                "dhcp_snippets": [],
                            }
                            for ip_range in (
                                other_subnet.get_dynamic_ranges().order_by(
                                    "id"
                                )
                            )
                        ],
                    },
                ],
                key=itemgetter("subnet"),
            ),
            observed_subnets,
        )
        self.assertCountEqual(
            dhcp.make_hosts_for_subnets([ha_subnet]), observed_hosts
        )
        self.assertEqual(primary_interface.name, observed_interface)


class TestGetDHCPConfiguration(MAASServerTestCase):
    """Tests for `get_dhcp_configuration`."""

    def setUp(self):
        super().setUp()
        SecretManager().set_simple_secret(
            "omapi-key", factory.make_name("omapi")
        )

    def make_RackController_ready_for_DHCP(self):
        rack = factory.make_RackController()
        vlan = factory.make_VLAN(dhcp_on=True, primary_rack=rack)
        subnet4 = factory.make_Subnet(vlan=vlan, cidr="10.20.30.0/24")
        subnet6 = factory.make_Subnet(
            vlan=vlan, cidr="fd38:c341:27da:c831::/64"
        )
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan
        )
        address4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet4,
            interface=interface,
        )
        address6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet6,
            interface=interface,
        )
        return rack, (address4, address6)

    def assertHasConfigurationForNTP(
        self, shared_network, subnet, ntp_servers
    ):
        [network] = shared_network
        [the_subnet] = network.get("subnets", [])
        self.assertEqual(the_subnet.get("subnet_cidr"), subnet.cidr)
        self.assertEqual(the_subnet.get("ntp_servers"), ntp_servers)

    def test_uses_global_ntp_servers_when_ntp_external_only_is_set(self):
        ntp_servers = [factory.make_hostname(), factory.make_ip_address()]
        Config.objects.set_config("ntp_servers", ", ".join(ntp_servers))
        Config.objects.set_config("ntp_external_only", True)

        rack, (addr4, addr6) = self.make_RackController_ready_for_DHCP()
        config = dhcp.get_dhcp_configuration(rack)

        self.assertHasConfigurationForNTP(
            config.shared_networks_v4, addr4.subnet, ntp_servers
        )
        self.assertHasConfigurationForNTP(
            config.shared_networks_v6, addr6.subnet, ntp_servers
        )

    def test_finds_per_subnet_addresses_when_ntp_external_only_not_set(self):
        ntp_servers = [factory.make_hostname(), factory.make_ip_address()]
        Config.objects.set_config("ntp_servers", ", ".join(ntp_servers))
        Config.objects.set_config("ntp_external_only", False)

        rack, (addr4, addr6) = self.make_RackController_ready_for_DHCP()
        config = dhcp.get_dhcp_configuration(rack)

        self.assertHasConfigurationForNTP(
            config.shared_networks_v4, addr4.subnet, [addr4.ip]
        )
        self.assertHasConfigurationForNTP(
            config.shared_networks_v6, addr6.subnet, [addr6.ip]
        )


class TestConfigureDHCP(MAASTransactionServerTestCase):
    """Tests for `configure_dhcp`."""

    def setUp(self):
        super().setUp()
        SecretManager().set_simple_secret(
            "omapi-key", factory.make_name("omapi")
        )

    @synchronous
    def prepare_rpc(self, rack_controller):
        """Set up test case for speaking RPC to `rack_controller`."""
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        cluster = fixture.makeCluster(
            rack_controller, ConfigureDHCPv4, ConfigureDHCPv6
        )
        return (
            cluster,
            getattr(cluster, ConfigureDHCPv4.commandName.decode("ascii")),
            getattr(cluster, ConfigureDHCPv6.commandName.decode("ascii")),
        )

    @transactional
    def create_rack_controller(
        self, dhcp_on=True, missing_ipv4=False, missing_ipv6=False
    ):
        """Create a `rack_controller` in a state that will call both
        `ConfigureDHCPv4` and `ConfigureDHCPv6` with data."""
        primary_rack = factory.make_RackController(interface=False)
        secondary_rack = factory.make_RackController(interface=False)

        vlan = factory.make_VLAN(
            dhcp_on=dhcp_on,
            primary_rack=primary_rack,
            secondary_rack=secondary_rack,
        )
        primary_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=primary_rack, vlan=vlan
        )
        secondary_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=secondary_rack, vlan=vlan
        )

        subnet_v4 = factory.make_ipv4_Subnet_with_IPRanges(
            vlan=vlan, unmanaged=(not dhcp_on)
        )
        subnet_v6 = factory.make_Subnet(
            vlan=vlan,
            cidr="fd38:c341:27da:c831::/64",
            gateway_ip="fd38:c341:27da:c831::1",
            dns_servers=[],
        )
        iprange_v4 = subnet_v4.get_dynamic_ranges().first()
        iprange_v4.save()
        iprange_v6 = factory.make_IPRange(
            subnet_v6,
            "fd38:c341:27da:c831:0:1::",
            "fd38:c341:27da:c831:0:1:ffff:0",
        )

        if not missing_ipv4:
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.AUTO,
                subnet=subnet_v4,
                interface=primary_interface,
            )
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.AUTO,
                subnet=subnet_v4,
                interface=secondary_interface,
            )
        if not missing_ipv6:
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.AUTO,
                subnet=subnet_v6,
                interface=primary_interface,
            )
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.AUTO,
                subnet=subnet_v6,
                interface=secondary_interface,
            )

        for _ in range(3):
            factory.make_DHCPSnippet(
                subnet=subnet_v4, iprange=iprange_v4, enabled=True
            )
            factory.make_DHCPSnippet(
                subnet=subnet_v6, iprange=iprange_v6, enabled=True
            )
            factory.make_DHCPSnippet(subnet=subnet_v4, enabled=True)
            factory.make_DHCPSnippet(subnet=subnet_v6, enabled=True)
            factory.make_DHCPSnippet(enabled=True)

        config = dhcp.get_dhcp_configuration(primary_rack)
        return primary_rack, config

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_configure_for_both_ipv4_and_ipv6(self):
        # ... when DHCP_CONNECT is True.
        self.patch(dhcp.settings, "DHCP_CONNECT", True)
        rack_controller, config = yield deferToDatabase(
            self.create_rack_controller
        )
        protocol, ipv4_stub, ipv6_stub = yield deferToThread(
            self.prepare_rpc, rack_controller
        )
        ipv4_stub.side_effect = always_succeed_with({})
        ipv6_stub.side_effect = always_succeed_with({})
        interfaces_v4 = [{"name": name} for name in config.interfaces_v4]
        interfaces_v6 = [{"name": name} for name in config.interfaces_v6]

        yield dhcp.configure_dhcp(rack_controller)

        ipv4_stub.assert_called_once_with(
            ANY,
            omapi_key=config.omapi_key,
            failover_peers=config.failover_peers_v4,
            shared_networks=config.shared_networks_v4,
            hosts=config.hosts_v4,
            interfaces=interfaces_v4,
            global_dhcp_snippets=config.global_dhcp_snippets,
        )
        ipv6_stub.assert_called_once_with(
            ANY,
            omapi_key=config.omapi_key,
            failover_peers=config.failover_peers_v6,
            shared_networks=config.shared_networks_v6,
            hosts=config.hosts_v6,
            interfaces=interfaces_v6,
            global_dhcp_snippets=config.global_dhcp_snippets,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_generate_dhcp_configuration_for_both_ipv4_and_ipv6(self):
        # ... when DHCP_CONNECT is True.
        self.patch(dhcp.settings, "DHCP_CONNECT", True)
        rack_controller, dhcp_config = yield deferToDatabase(
            self.create_rack_controller
        )

        interfaces_v4 = " ".join(
            sorted(name for name in dhcp_config.interfaces_v4)
        )
        interfaces_v6 = " ".join(
            sorted(name for name in dhcp_config.interfaces_v6)
        )

        get_config_v4_stub = self.patch(dhcp, "get_config_v4")
        get_config_v6_stub = self.patch(dhcp, "get_config_v6")

        get_config_v4_stub.return_value = ""
        get_config_v6_stub.return_value = ""

        result = yield deferToDatabase(
            dhcp.generate_dhcp_configuration, rack_controller
        )
        get_config_v4_stub.assert_called_once_with(
            template_name="dhcpd.conf.template",
            global_dhcp_snippets=dhcp_config.global_dhcp_snippets,
            failover_peers=dhcp_config.failover_peers_v4,
            shared_networks=dhcp_config.shared_networks_v4,
            hosts=dhcp_config.hosts_v4,
            omapi_key=dhcp_config.omapi_key,
        )
        get_config_v6_stub.assert_called_once_with(
            template_name="dhcpd6.conf.template",
            global_dhcp_snippets=dhcp_config.global_dhcp_snippets,
            failover_peers=dhcp_config.failover_peers_v6,
            shared_networks=dhcp_config.shared_networks_v6,
            hosts=dhcp_config.hosts_v6,
            omapi_key=dhcp_config.omapi_key,
        )

        assert result["dhcpd_interfaces"] == base64.b64encode(
            interfaces_v4.encode("utf-8")
        ).decode("utf-8")
        assert result["dhcpd6_interfaces"] == base64.b64encode(
            interfaces_v6.encode("utf-8")
        ).decode("utf-8")

    @wait_for_reactor
    @inlineCallbacks
    def test_closed_handler_drops_connection(self):
        # ... when DHCP_CONNECT is True.
        self.patch(dhcp.settings, "DHCP_CONNECT", True)

        rack_controller, config = yield deferToDatabase(
            self.create_rack_controller
        )
        protocol, ipv4_stub, ipv6_stub = yield deferToThread(
            self.prepare_rpc, rack_controller
        )

        # Get the client and simulate a closed handler
        client = yield getClientFor(rack_controller.system_id)
        self.patch(client._conn, "_sendBoxCommand").side_effect = (
            always_fail_with(RuntimeError("the handler is closed"))
        )

        ipv4_stub.side_effect = always_succeed_with({})
        ipv6_stub.side_effect = always_succeed_with({})

        # The RuntimeError is propagated
        with pytest.raises(RuntimeError):
            yield dhcp.configure_dhcp(rack_controller)

        # But the connection should have been closed and no connections should be available now.
        with pytest.raises(exceptions.NoConnectionsAvailable):
            yield getClientFor(rack_controller.system_id)

    @wait_for_reactor
    @inlineCallbacks
    def test_doesnt_call_configure_for_both_ipv4_and_ipv6(self):
        # ... when DHCP_CONNECT is False.
        self.patch(dhcp.settings, "DHCP_CONNECT", False)
        rack_controller, config = yield deferToDatabase(
            self.create_rack_controller
        )
        protocol, ipv4_stub, ipv6_stub = yield deferToThread(
            self.prepare_rpc, rack_controller
        )
        ipv4_stub.side_effect = always_succeed_with({})
        ipv6_stub.side_effect = always_succeed_with({})

        yield dhcp.configure_dhcp(rack_controller)

        ipv4_stub.assert_not_called()
        ipv6_stub.assert_not_called()

    @wait_for_reactor
    @inlineCallbacks
    def test_updates_service_status_running_when_dhcp_on(self):
        self.patch(dhcp.settings, "DHCP_CONNECT", True)
        rack_controller, _ = yield deferToDatabase(self.create_rack_controller)
        protocol, ipv4_stub, ipv6_stub = yield deferToThread(
            self.prepare_rpc, rack_controller
        )
        ipv4_stub.side_effect = always_succeed_with({})
        ipv6_stub.side_effect = always_succeed_with({})

        @transactional
        def service_statuses_are_unknown():
            dhcpv4_service = Service.objects.get(
                node=rack_controller, name="dhcpd"
            )
            self.assertEqual(dhcpv4_service.status, SERVICE_STATUS.UNKNOWN)
            self.assertEqual(dhcpv4_service.status_info, "")
            dhcpv6_service = Service.objects.get(
                node=rack_controller, name="dhcpd6"
            )
            self.assertEqual(dhcpv6_service.status, SERVICE_STATUS.UNKNOWN)
            self.assertEqual(dhcpv6_service.status_info, "")

        yield deferToDatabase(service_statuses_are_unknown)

        yield dhcp.configure_dhcp(rack_controller)

        @transactional
        def services_are_running():
            dhcpv4_service = Service.objects.get(
                node=rack_controller, name="dhcpd"
            )
            self.assertEqual(dhcpv4_service.status, SERVICE_STATUS.RUNNING)
            self.assertEqual(dhcpv4_service.status_info, "")
            dhcpv6_service = Service.objects.get(
                node=rack_controller, name="dhcpd6"
            )
            self.assertEqual(dhcpv6_service.status, SERVICE_STATUS.RUNNING)
            self.assertEqual(dhcpv6_service.status_info, "")

        yield deferToDatabase(services_are_running)

    @wait_for_reactor
    @inlineCallbacks
    def test_updates_service_status_off_when_dhcp_off(self):
        self.patch(dhcp.settings, "DHCP_CONNECT", True)
        rack_controller, _ = yield deferToDatabase(
            self.create_rack_controller, dhcp_on=False
        )
        protocol, ipv4_stub, ipv6_stub = yield deferToThread(
            self.prepare_rpc, rack_controller
        )
        ipv4_stub.side_effect = always_succeed_with({})
        ipv6_stub.side_effect = always_succeed_with({})

        @transactional
        def service_statuses_are_unknown():
            dhcpv4_service = Service.objects.get(
                node=rack_controller, name="dhcpd"
            )
            self.assertEqual(dhcpv4_service.status, SERVICE_STATUS.UNKNOWN)
            self.assertEqual(dhcpv4_service.status_info, "")

            dhcpv6_service = Service.objects.get(
                node=rack_controller, name="dhcpd6"
            )
            self.assertEqual(dhcpv6_service.status, SERVICE_STATUS.UNKNOWN)
            self.assertEqual(dhcpv6_service.status_info, "")

        yield deferToDatabase(service_statuses_are_unknown)

        yield dhcp.configure_dhcp(rack_controller)

        @transactional
        def service_status_updated():
            dhcpv4_service = Service.objects.get(
                node=rack_controller, name="dhcpd"
            )
            self.assertEqual(dhcpv4_service.status, SERVICE_STATUS.OFF)
            self.assertEqual(dhcpv4_service.status_info, "")
            dhcpv6_service = Service.objects.get(
                node=rack_controller, name="dhcpd6"
            )
            self.assertEqual(dhcpv6_service.status, SERVICE_STATUS.OFF)
            self.assertEqual(dhcpv6_service.status_info, "")

        yield deferToDatabase(service_status_updated)

    @wait_for_reactor
    @inlineCallbacks
    def test_updates_service_status_dead_when_configuration_crashes(self):
        self.patch(dhcp.settings, "DHCP_CONNECT", True)
        rack_controller, _ = yield deferToDatabase(
            self.create_rack_controller, dhcp_on=False
        )
        protocol, ipv4_stub, ipv6_stub = yield deferToThread(
            self.prepare_rpc, rack_controller
        )
        ipv4_exc = factory.make_name("ipv4_failure")
        ipv4_stub.side_effect = always_fail_with(CannotConfigureDHCP(ipv4_exc))
        ipv6_exc = factory.make_name("ipv6_failure")
        ipv6_stub.side_effect = always_fail_with(CannotConfigureDHCP(ipv6_exc))

        with self.assertRaisesRegex(CannotConfigureDHCP, "ipv[46]_failure"):
            yield dhcp.configure_dhcp(rack_controller)

        @transactional
        def service_status_updated():
            dhcpv4_service = Service.objects.get(
                node=rack_controller, name="dhcpd"
            )
            self.assertEqual(dhcpv4_service.status, SERVICE_STATUS.DEAD)
            self.assertEqual(dhcpv4_service.status_info, ipv4_exc)
            dhcpv6_service = Service.objects.get(
                node=rack_controller, name="dhcpd6"
            )
            self.assertEqual(dhcpv6_service.status, SERVICE_STATUS.DEAD)
            self.assertEqual(dhcpv6_service.status_info, ipv6_exc)

        yield deferToDatabase(service_status_updated)


class TestGetDHCPRackcontroller(MAASTransactionServerTestCase):
    def create_dhcp_vlan(self, primary_address, secondary_adress=None):
        dhcp_vlan = factory.make_VLAN()
        dhcp_subnet = factory.make_Subnet(
            vlan=dhcp_vlan, cidr=IPNetwork(primary_address).cidr
        )
        primary_rack = factory.make_rack_with_interfaces(
            eth0=[primary_address]
        )
        secondary_rack = None
        if secondary_adress is not None:
            secondary_rack = factory.make_rack_with_interfaces(
                eth0=[secondary_adress]
            )
        dhcp_vlan.dhcp_on = True
        dhcp_vlan.primary_rack = primary_rack
        dhcp_vlan.secondary_rack = secondary_rack

        with post_commit_hooks:
            dhcp_vlan.save()

        return dhcp_subnet

    def test_subnet(self):
        subnet = self.create_dhcp_vlan("10.10.10.2/24")
        self.create_dhcp_vlan("10.10.20.2/24")
        snippet = factory.make_DHCPSnippet(subnet=subnet, enabled=True)
        self.assertCountEqual(
            [subnet.vlan.primary_rack], _get_dhcp_rackcontrollers(snippet)
        )

    def test_subnet_includes_secondary(self):
        subnet = self.create_dhcp_vlan("10.10.10.2/24", "10.10.10.3/24")
        self.create_dhcp_vlan("10.10.20.0/24")
        snippet = factory.make_DHCPSnippet(subnet=subnet, enabled=True)
        self.assertCountEqual(
            [subnet.vlan.primary_rack, subnet.vlan.secondary_rack],
            _get_dhcp_rackcontrollers(snippet),
        )

    def test_subnet_relay(self):
        dhcp_subnet = self.create_dhcp_vlan("10.10.10.2/24")
        self.create_dhcp_vlan("10.10.20.2/24")
        relay_subnet = factory.make_Subnet(cidr="10.10.30.0/24")
        relay_subnet.vlan.relay_vlan = dhcp_subnet.vlan

        with post_commit_hooks:
            relay_subnet.vlan.save()

        snippet = factory.make_DHCPSnippet(subnet=relay_subnet, enabled=True)
        self.assertCountEqual(
            [dhcp_subnet.vlan.primary_rack], _get_dhcp_rackcontrollers(snippet)
        )

    def test_node(self):
        subnet = self.create_dhcp_vlan("10.10.10.2/24")
        self.create_dhcp_vlan("10.10.20.0/24")
        node = factory.make_Machine_with_Interface_on_Subnet(subnet=subnet)
        snippet = factory.make_DHCPSnippet(node=node, enabled=True)
        self.assertCountEqual(
            [subnet.vlan.primary_rack], _get_dhcp_rackcontrollers(snippet)
        )

    def test_node_includes_secondary(self):
        subnet = self.create_dhcp_vlan("10.10.10.2/24", "10.10.10.3/24")
        self.create_dhcp_vlan("10.10.20.0/24")
        node = factory.make_Machine_with_Interface_on_Subnet(subnet=subnet)
        snippet = factory.make_DHCPSnippet(node=node, enabled=True)
        self.assertCountEqual(
            [subnet.vlan.primary_rack, subnet.vlan.secondary_rack],
            _get_dhcp_rackcontrollers(snippet),
        )

    def test_node_relay(self):
        dhcp_subnet = self.create_dhcp_vlan("10.10.10.2/24")
        self.create_dhcp_vlan("10.10.20.2/24")
        relay_subnet = factory.make_Subnet(cidr="10.10.30.0/24")
        relay_subnet.vlan.relay_vlan = dhcp_subnet.vlan

        with post_commit_hooks:
            relay_subnet.vlan.save()

        node = factory.make_Machine_with_Interface_on_Subnet(
            subnet=relay_subnet
        )
        snippet = factory.make_DHCPSnippet(node=node, enabled=True)
        self.assertCountEqual(
            [dhcp_subnet.vlan.primary_rack], _get_dhcp_rackcontrollers(snippet)
        )


class TestConfigureDhcpOnAgents(MAASServerTestCase):
    @wait_for_reactor
    @inlineCallbacks
    def test_configure_dhcp_on_agents(self):
        d = defer.succeed(None)
        self.patch(dhcp_module, "start_workflow").return_value = d

        yield dhcp.configure_dhcp_on_agents(
            system_ids=["test"],
            vlan_ids=[0],
            subnet_ids=[1],
            static_ip_addr_ids=[2],
            ip_range_ids=[3],
            reserved_ip_ids=[4],
        )

        dhcp_module.start_workflow.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(
                system_ids=["test"],
                vlan_ids=[0],
                subnet_ids=[1],
                static_ip_addr_ids=[2],
                ip_range_ids=[3],
                reserved_ip_ids=[4],
            ),
            task_queue="region",
        )
