# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
import random
import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from fixtures import FakeLogger
from hypothesis import given, settings
from hypothesis.strategies import integers
from netaddr import AddrFormatError, IPAddress, IPNetwork

from maasserver.enum import (
    IPADDRESS_TYPE,
    IPRANGE_TYPE,
    NODE_STATUS,
    RDNS_MODE,
    RDNS_MODE_CHOICES,
)
from maasserver.exceptions import StaticIPAddressExhaustion
from maasserver.models import Config, Notification, Space
from maasserver.models.subnet import (
    create_cidr,
    get_allocated_ips,
    get_boot_rackcontroller_ips,
    Subnet,
)
from maasserver.models.timestampedmodel import now
from maasserver.permissions import NodePermission
from maasserver.testing.factory import factory, RANDOM, RANDOM_OR_NONE
from maasserver.testing.orm import rollback
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import get_one, post_commit_hooks, reload_object
from maastesting.djangotestcase import count_queries
from provisioningserver.utils.network import inet_ntop, MAASIPRange


class TestCreateCidr(MAASServerTestCase):
    def test_creates_cidr_from_ipv4_strings(self):
        cidr = create_cidr("169.254.0.0", "255.255.255.0")
        self.assertEqual("169.254.0.0/24", cidr)

    def test_creates_cidr_from_ipv4_prefixlen(self):
        cidr = create_cidr("169.254.0.0", 24)
        self.assertEqual("169.254.0.0/24", cidr)

    def test_raises_for_invalid_ipv4_prefixlen(self):
        self.assertRaises(AddrFormatError, create_cidr, "169.254.0.0", 33)

    def test_discards_extra_ipv4_network_bits(self):
        cidr = create_cidr("169.254.0.1", 24)
        self.assertEqual("169.254.0.0/24", cidr)

    def test_creates_cidr_from_ipv6_strings(self):
        # No one really uses this syntax, but we'll test it anyway.
        cidr = create_cidr("2001:67c:1360:8c01::", "ffff:ffff:ffff:ffff::")
        self.assertEqual("2001:67c:1360:8c01::/64", cidr)

    def test_creates_cidr_from_ipv6_prefixlen(self):
        cidr = create_cidr("2001:67c:1360:8c01::", 64)
        self.assertEqual("2001:67c:1360:8c01::/64", cidr)

    def test_discards_extra_ipv6_network_bits(self):
        cidr = create_cidr("2001:67c:1360:8c01::1", 64)
        self.assertEqual("2001:67c:1360:8c01::/64", cidr)

    def test_raises_for_invalid_ipv6_prefixlen(self):
        self.assertRaises(
            AddrFormatError, create_cidr, "2001:67c:1360:8c01::", 129
        )

    def test_accepts_ipaddresses(self):
        cidr = create_cidr(
            IPAddress("169.254.0.1"), IPAddress("255.255.255.0")
        )
        self.assertEqual("169.254.0.0/24", cidr)

    def test_accepts_ipnetwork(self):
        cidr = create_cidr(IPNetwork("169.254.0.1/24"))
        self.assertEqual("169.254.0.0/24", cidr)

    def test_accepts_ipnetwork_with_subnet_override(self):
        cidr = create_cidr(IPNetwork("169.254.0.1/24"), 16)
        self.assertEqual("169.254.0.0/16", cidr)


class TestSubnetQueriesMixin(MAASServerTestCase):
    def test_filter_by_specifiers_takes_single_item(self):
        subnet1 = factory.make_Subnet(name="subnet1")
        factory.make_Subnet(name="subnet2")
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers("subnet1"), [subnet1]
        )

    def test_filter_by_specifiers_takes_multiple_items(self):
        subnet1 = factory.make_Subnet(name="subnet1")
        subnet2 = factory.make_Subnet(name="subnet2")
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(["subnet1", "subnet2"]),
            [subnet1, subnet2],
        )

    def test_filter_by_specifiers_takes_multiple_cidr_or_name(self):
        subnet1 = factory.make_Subnet(name="subnet1", cidr="8.8.8.0/24")
        subnet2 = factory.make_Subnet(name="subnet2")
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(["8.8.8.8/24", "subnet2"]),
            [subnet1, subnet2],
        )

    def test_filter_by_specifiers_empty_filter_matches_all(self):
        subnet1 = factory.make_Subnet(name="subnet1", cidr="8.8.8.0/24")
        subnet2 = factory.make_Subnet(name="subnet2")
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers([]), [subnet1, subnet2]
        )

    def test_filter_by_specifiers_matches_name_if_requested(self):
        subnet1 = factory.make_Subnet(name="subnet1", cidr="8.8.8.0/24")
        subnet2 = factory.make_Subnet(name="subnet2")
        factory.make_Subnet(name="subnet3")
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(
                ["name:subnet1", "name:subnet2"]
            ),
            [subnet1, subnet2],
        )

    def test_filter_by_specifiers_matches_space_name_if_requested(self):
        subnet1 = factory.make_Subnet(
            name="subnet1", cidr="8.8.8.0/24", space=RANDOM
        )
        subnet2 = factory.make_Subnet(name="subnet2", space=RANDOM)
        factory.make_Subnet(name="subnet3", space=RANDOM_OR_NONE)
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(
                [
                    "space:%s" % subnet1.space.name,
                    "space:%s" % subnet2.space.name,
                ]
            ),
            [subnet1, subnet2],
        )

    def test_filter_by_specifiers_matches_vid_if_requested(self):
        subnet1 = factory.make_Subnet(name="subnet1", cidr="8.8.8.0/24", vid=1)
        subnet2 = factory.make_Subnet(name="subnet2", vid=2)
        subnet3 = factory.make_Subnet(name="subnet3", vid=3)
        factory.make_Subnet(name="subnet4", vid=4)
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(
                ["vlan:vid:0b1", "vlan:vid:0x2", "vlan:vid:3"]
            ),
            [subnet1, subnet2, subnet3],
        )

    def test_filter_by_specifiers_matches_untagged_vlan_if_requested(self):
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        subnet1 = factory.make_Subnet(
            name="subnet1", cidr="8.8.8.0/24", vlan=vlan
        )
        subnet2 = factory.make_Subnet(name="subnet2", vid=2)
        subnet3 = factory.make_Subnet(name="subnet3", vid=3)
        factory.make_Subnet(name="subnet4", vid=4)
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(
                ["vid:UNTAGGED", "vid:0x2", "vid:3"]
            ),
            [subnet1, subnet2, subnet3],
        )

    def test_filter_by_specifiers_raises_for_invalid_vid(self):
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        factory.make_Subnet(name="subnet1", cidr="8.8.8.0/24", vlan=vlan)
        factory.make_Subnet(name="subnet2", vid=2)
        factory.make_Subnet(name="subnet3", vid=3)
        factory.make_Subnet(name="subnet4", vid=4)
        self.assertRaises(
            ValidationError, Subnet.objects.filter_by_specifiers, ["vid:4095"]
        )

    def test_filter_by_specifiers_works_with_chained_filter(self):
        factory.make_Subnet(name="subnet1", cidr="8.8.8.0/24")
        subnet2 = factory.make_Subnet(name="subnet2")
        self.assertCountEqual(
            Subnet.objects.exclude(name="subnet1").filter_by_specifiers(
                ["8.8.8.8/24", "subnet2"]
            ),
            [subnet2],
        )

    def test_filter_by_specifiers_ip_filter_matches_specific_ip(self):
        subnet1 = factory.make_Subnet(name="subnet1", cidr="8.8.8.0/24")
        subnet2 = factory.make_Subnet(name="subnet2", cidr="7.7.7.0/24")
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers("ip:8.8.8.8"), [subnet1]
        )
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers("ip:7.7.7.7"), [subnet2]
        )
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers("ip:1.1.1.1"), []
        )

    def test_filter_by_specifiers_ip_filter_raises_for_invalid_ip(self):
        factory.make_Subnet(name="subnet1", cidr="8.8.8.0/24")
        factory.make_Subnet(name="subnet2", cidr="2001:db8::/64")
        self.assertRaises(
            AddrFormatError, Subnet.objects.filter_by_specifiers, "ip:x8.8.8.0"
        )
        self.assertRaises(
            AddrFormatError,
            Subnet.objects.filter_by_specifiers,
            "ip:x2001:db8::",
        )

    def test_filter_by_specifiers_ip_filter_matches_specific_cidr(self):
        subnet1 = factory.make_Subnet(name="subnet1", cidr="8.8.8.0/24")
        subnet2 = factory.make_Subnet(name="subnet2", cidr="2001:db8::/64")
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers("cidr:8.8.8.0/24"), [subnet1]
        )
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers("cidr:2001:db8::/64"),
            [subnet2],
        )

    def test_filter_by_specifiers_ip_filter_raises_for_invalid_cidr(self):
        factory.make_Subnet(name="subnet1", cidr="8.8.8.0/24")
        factory.make_Subnet(name="subnet2", cidr="2001:db8::/64")
        self.assertRaises(
            AddrFormatError,
            Subnet.objects.filter_by_specifiers,
            "cidr:x8.8.8.0/24",
        )
        self.assertRaises(
            AddrFormatError,
            Subnet.objects.filter_by_specifiers,
            "cidr:x2001:db8::/64",
        )

    def test_filter_by_specifiers_ip_chained_filter_matches_specific_ip(self):
        subnet1 = factory.make_Subnet(name="subnet1", cidr="8.8.8.0/24")
        factory.make_Subnet(name="subnet2", cidr="7.7.7.0/24")
        subnet3 = factory.make_Subnet(name="subnet3", cidr="6.6.6.0/24")
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(
                ["ip:8.8.8.8", "name:subnet3"]
            ),
            [subnet1, subnet3],
        )

    def test_filter_by_specifiers_ip_filter_matches_specific_ipv6(self):
        subnet1 = factory.make_Subnet(name="subnet1", cidr="2001:db8::/64")
        subnet2 = factory.make_Subnet(name="subnet2", cidr="2001:db8:1::/64")
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers("ip:2001:db8::5"), [subnet1]
        )
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers("ip:2001:db8:1::5"), [subnet2]
        )
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers("ip:1.1.1.1"), []
        )

    def test_filter_by_specifiers_space_filter(self):
        space1 = factory.make_Space()
        vlan1 = factory.make_VLAN(space=space1)
        vlan2 = factory.make_VLAN(space=None)
        subnet1 = factory.make_Subnet(vlan=vlan1, space=None)
        subnet2 = factory.make_Subnet(vlan=vlan2, space=None)
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers("space:%s" % space1.name),
            [subnet1],
        )
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers("space:%s" % Space.UNDEFINED),
            [subnet2],
        )

    def test_matches_interfaces(self):
        node1 = factory.make_Node_with_Interface_on_Subnet()
        node2 = factory.make_Node_with_Interface_on_Subnet()
        iface1 = node1.get_boot_interface()
        iface2 = node2.get_boot_interface()
        subnet1 = iface1.ip_addresses.first().subnet
        subnet2 = iface2.ip_addresses.first().subnet
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers("interface:id:%s" % iface1.id),
            [subnet1],
        )
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers("interface:id:%s" % iface2.id),
            [subnet2],
        )
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(
                ["interface:id:%s" % iface1.id, "interface:id:%s" % iface2.id]
            ),
            [subnet1, subnet2],
        )

    def test_not_operators(self):
        node1 = factory.make_Node_with_Interface_on_Subnet()
        node2 = factory.make_Node_with_Interface_on_Subnet()
        iface1 = node1.get_boot_interface()
        iface2 = node2.get_boot_interface()
        subnet1 = iface1.ip_addresses.first().subnet
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(
                ["interface:id:%s" % iface1.id, "!interface:id:%s" % iface2.id]
            ),
            [subnet1],
        )
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(
                [
                    "interface:id:%s" % iface1.id,
                    "not_interface:id:%s" % iface2.id,
                ]
            ),
            [subnet1],
        )

    def test_not_operators_order_independent(self):
        node1 = factory.make_Node_with_Interface_on_Subnet()
        node2 = factory.make_Node_with_Interface_on_Subnet()
        iface1 = node1.get_boot_interface()
        iface2 = node2.get_boot_interface()
        subnet2 = iface2.ip_addresses.first().subnet
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(
                ["!interface:id:%s" % iface1.id, "interface:id:%s" % iface2.id]
            ),
            [subnet2],
        )
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(
                [
                    "not_interface:id:%s" % iface1.id,
                    "interface:id:%s" % iface2.id,
                ]
            ),
            [subnet2],
        )

    def test_and_operator(self):
        node1 = factory.make_Node_with_Interface_on_Subnet()
        node2 = factory.make_Node_with_Interface_on_Subnet()
        iface1 = node1.get_boot_interface()
        iface2 = node2.get_boot_interface()
        # Try to filter by two mutually exclusive conditions.
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(
                ["interface:id:%s" % iface1.id, "&interface:id:%s" % iface2.id]
            ),
            [],
        )

    def test_craziness_works(self):
        # This test validates that filters can be "chained" to each other
        # in an arbitrary way.
        node1 = factory.make_Node_with_Interface_on_Subnet()
        node2 = factory.make_Node_with_Interface_on_Subnet()
        iface1 = node1.get_boot_interface()
        iface2 = node2.get_boot_interface()
        subnet1 = iface1.ip_addresses.first().subnet
        subnet2 = iface2.ip_addresses.first().subnet
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(
                "interface:subnet:id:%s" % subnet1.id
            ),
            [subnet1],
        )
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(
                "interface:subnet:id:%s" % subnet2.id
            ),
            [subnet2],
        )
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(
                [
                    "interface:subnet:id:%s" % subnet1.id,
                    "interface:subnet:id:%s" % subnet2.id,
                ]
            ),
            [subnet1, subnet2],
        )
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(
                "interface:subnet:interface:subnet:id:%s" % subnet1.id
            ),
            [subnet1],
        )
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(
                "interface:subnet:interface:subnet:id:%s" % subnet2.id
            ),
            [subnet2],
        )
        self.assertCountEqual(
            Subnet.objects.filter_by_specifiers(
                [
                    "interface:subnet:interface:subnet:id:%s" % subnet1.id,
                    "interface:subnet:interface:subnet:id:%s" % subnet2.id,
                ]
            ),
            [subnet1, subnet2],
        )


class TestSubnetManagerGetSubnetOr404(MAASServerTestCase):
    def test_user_view_returns_subnet(self):
        user = factory.make_User()
        subnet = factory.make_Subnet()
        self.assertEqual(
            subnet,
            Subnet.objects.get_subnet_or_404(
                subnet.id, user, NodePermission.view
            ),
        )

    def test_user_edit_raises_PermissionError(self):
        user = factory.make_User()
        subnet = factory.make_Subnet()
        self.assertRaises(
            PermissionDenied,
            Subnet.objects.get_subnet_or_404,
            subnet.id,
            user,
            NodePermission.edit,
        )

    def test_user_admin_raises_PermissionError(self):
        user = factory.make_User()
        subnet = factory.make_Subnet()
        self.assertRaises(
            PermissionDenied,
            Subnet.objects.get_subnet_or_404,
            subnet.id,
            user,
            NodePermission.admin,
        )

    def test_admin_view_returns_subnet(self):
        admin = factory.make_admin()
        subnet = factory.make_Subnet()
        self.assertEqual(
            subnet,
            Subnet.objects.get_subnet_or_404(
                subnet.id, admin, NodePermission.view
            ),
        )

    def test_admin_edit_returns_subnet(self):
        admin = factory.make_admin()
        subnet = factory.make_Subnet()
        self.assertEqual(
            subnet,
            Subnet.objects.get_subnet_or_404(
                subnet.id, admin, NodePermission.edit
            ),
        )

    def test_admin_admin_returns_subnet(self):
        admin = factory.make_admin()
        subnet = factory.make_Subnet()
        self.assertEqual(
            subnet,
            Subnet.objects.get_subnet_or_404(
                subnet.id, admin, NodePermission.admin
            ),
        )


class TestSubnet(MAASServerTestCase):
    def assertIPBestMatchesSubnet(self, ip, expected):
        subnets = Subnet.objects.raw_subnets_containing_ip(IPAddress(ip))
        for tmp in subnets:
            subnet = tmp
            break
        else:
            subnet = None
        self.assertEqual(expected, subnet)

    def test_can_create_update_and_delete_subnet_with_attached_range(self):
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/8", gateway_ip=None, dns_servers=[]
        )
        iprange = factory.make_IPRange(
            subnet, start_ip="10.0.0.1", end_ip="10.255.255.254"
        )
        subnet.description = "foo"
        subnet.save()
        subnet.delete()
        iprange.delete()

    def test_can_create_update_and_delete_subnet_with_assigned_ips(self):
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/8", gateway_ip=None, dns_servers=[]
        )
        iprange = factory.make_IPRange(
            subnet, start_ip="10.0.0.1", end_ip="10.255.255.252"
        )
        static_ip = factory.make_StaticIPAddress(
            "10.255.255.254",
            subnet=subnet,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
        )
        static_ip_2 = factory.make_StaticIPAddress(
            "10.255.255.253",
            subnet=subnet,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
        )
        subnet.description = "foo"
        subnet.save()
        static_ip_2.delete()
        subnet.delete()
        iprange.delete()
        static_ip.delete()

    def test_creates_subnet(self):
        name = factory.make_name("name")
        vlan = factory.make_VLAN()
        factory.make_Space()
        network = factory.make_ip4_or_6_network()
        cidr = str(network.cidr)
        gateway_ip = factory.pick_ip_in_network(network)
        dns_servers = [
            factory.make_ip_address() for _ in range(random.randint(1, 3))
        ]
        rdns_mode = factory.pick_choice(RDNS_MODE_CHOICES)
        allow_proxy = factory.pick_bool()
        allow_dns = factory.pick_bool()
        subnet = Subnet(
            name=name,
            vlan=vlan,
            cidr=cidr,
            gateway_ip=gateway_ip,
            dns_servers=dns_servers,
            rdns_mode=rdns_mode,
            allow_proxy=allow_proxy,
            allow_dns=allow_dns,
        )
        subnet.save()
        subnet_from_db = Subnet.objects.get(name=name)
        self.assertEqual(subnet_from_db.name, name)
        self.assertEqual(subnet_from_db.vlan, vlan)
        self.assertEqual(subnet_from_db.cidr, cidr)
        self.assertEqual(subnet_from_db.gateway_ip, gateway_ip)
        self.assertEqual(subnet_from_db.dns_servers, dns_servers)
        self.assertEqual(subnet_from_db.rdns_mode, rdns_mode)
        self.assertEqual(subnet_from_db.allow_proxy, allow_proxy)
        self.assertEqual(subnet_from_db.allow_dns, allow_dns)

    def test_creates_subnet_with_correct_defaults(self):
        name = factory.make_name("name")
        vlan = factory.make_VLAN()
        factory.make_Space()
        network = factory.make_ip4_or_6_network()
        cidr = str(network.cidr)
        gateway_ip = factory.pick_ip_in_network(network)
        dns_servers = [
            factory.make_ip_address() for _ in range(random.randint(1, 3))
        ]
        subnet = Subnet(
            name=name,
            vlan=vlan,
            cidr=cidr,
            gateway_ip=gateway_ip,
            dns_servers=dns_servers,
        )
        subnet.save()
        subnet_from_db = Subnet.objects.get(name=name)
        self.assertEqual(subnet_from_db.name, name)
        self.assertEqual(subnet_from_db.vlan, vlan)
        self.assertEqual(subnet_from_db.cidr, cidr)
        self.assertEqual(subnet_from_db.gateway_ip, gateway_ip)
        self.assertEqual(subnet_from_db.dns_servers, dns_servers)
        self.assertEqual(subnet_from_db.rdns_mode, RDNS_MODE.DEFAULT)
        self.assertTrue(subnet_from_db.allow_proxy)
        self.assertTrue(subnet_from_db.allow_dns)

    def test_creates_subnet_with_default_name_if_name_is_none(self):
        vlan = factory.make_VLAN()
        factory.make_Space()
        network = factory.make_ip4_or_6_network()
        cidr = str(network.cidr)
        gateway_ip = factory.pick_ip_in_network(network)
        dns_servers = [
            factory.make_ip_address() for _ in range(random.randint(1, 3))
        ]
        rdns_mode = factory.pick_choice(RDNS_MODE_CHOICES)
        subnet = Subnet(
            name=None,
            vlan=vlan,
            cidr=cidr,
            gateway_ip=gateway_ip,
            dns_servers=dns_servers,
            rdns_mode=rdns_mode,
        )
        subnet.save()
        subnet_from_db = Subnet.objects.get(cidr=cidr)
        self.assertEqual(subnet_from_db.name, str(cidr))
        self.assertEqual(subnet_from_db.vlan, vlan)
        self.assertEqual(subnet_from_db.cidr, cidr)
        self.assertEqual(subnet_from_db.gateway_ip, gateway_ip)
        self.assertEqual(subnet_from_db.dns_servers, dns_servers)
        self.assertEqual(subnet_from_db.rdns_mode, rdns_mode)

    def test_creates_subnet_with_default_name_if_name_is_empty(self):
        vlan = factory.make_VLAN()
        network = factory.make_ip4_or_6_network()
        cidr = str(network.cidr)
        gateway_ip = factory.pick_ip_in_network(network)
        dns_servers = [
            factory.make_ip_address() for _ in range(random.randint(1, 3))
        ]
        rdns_mode = factory.pick_choice(RDNS_MODE_CHOICES)
        subnet = Subnet(
            name="",
            vlan=vlan,
            cidr=cidr,
            gateway_ip=gateway_ip,
            dns_servers=dns_servers,
            rdns_mode=rdns_mode,
        )
        subnet.save()
        subnet_from_db = Subnet.objects.get(cidr=cidr)
        self.assertEqual(subnet_from_db.name, str(cidr))
        self.assertEqual(subnet_from_db.vlan, vlan)
        self.assertEqual(subnet_from_db.cidr, cidr)
        self.assertEqual(subnet_from_db.gateway_ip, gateway_ip)
        self.assertEqual(subnet_from_db.dns_servers, dns_servers)
        self.assertEqual(subnet_from_db.rdns_mode, rdns_mode)

    def test_disallows_creation_with_space(self):
        space = factory.make_Space()
        self.assertRaises(AssertionError, Subnet, space=space)

    def test_validates_gateway_ip(self):
        error = self.assertRaises(
            ValidationError,
            factory.make_Subnet,
            cidr=create_cidr("192.168.0.0", 24),
            gateway_ip="10.0.0.0",
        )
        self.assertEqual(
            {"gateway_ip": ["Gateway IP must be within CIDR range."]},
            error.message_dict,
        )

    def test_allows_fe80_gateway(self):
        network = factory.make_ipv6_network(slash=64)
        gateway_ip = factory.pick_ip_in_network(IPNetwork("fe80::/64"))
        subnet = factory.make_Subnet(cidr=str(network), gateway_ip=gateway_ip)
        self.assertEqual(subnet.gateway_ip, gateway_ip)

    def test_denies_fe80_gateway_for_ipv4(self):
        network = factory.make_ipv4_network(slash=22)
        gateway_ip = factory.pick_ip_in_network(IPNetwork("fe80::/64"))
        error = self.assertRaises(
            ValidationError,
            factory.make_Subnet,
            cidr=str(network),
            gateway_ip=gateway_ip,
        )
        self.assertEqual(
            {"gateway_ip": ["Gateway IP must be within CIDR range."]},
            error.message_dict,
        )

    def test_create_from_cidr_creates_subnet(self):
        vlan = factory.make_VLAN()
        cidr = str(factory.make_ip4_or_6_network().cidr)
        name = "subnet-" + cidr
        subnet = Subnet.objects.create_from_cidr(cidr, vlan)
        self.assertEqual(subnet.name, name)
        self.assertEqual(subnet.vlan, vlan)
        self.assertEqual(subnet.cidr, cidr)
        self.assertIsNone(subnet.gateway_ip)
        self.assertEqual(subnet.dns_servers, [])

    def test_get_subnets_with_ip_finds_matching_subnet(self):
        subnet = factory.make_Subnet(cidr=factory.make_ipv4_network())
        self.assertIPBestMatchesSubnet(subnet.get_ipnetwork().first, subnet)
        self.assertIPBestMatchesSubnet(subnet.get_ipnetwork().last, subnet)

    def test_get_subnets_with_ip_finds_most_specific_subnet(self):
        subnet1 = factory.make_Subnet(cidr=IPNetwork("10.0.0.0/8"))
        subnet2 = factory.make_Subnet(cidr=IPNetwork("10.0.0.0/16"))
        subnet3 = factory.make_Subnet(cidr=IPNetwork("10.0.0.0/24"))
        self.assertIPBestMatchesSubnet(subnet1.get_ipnetwork().first, subnet3)
        self.assertIPBestMatchesSubnet(subnet1.get_ipnetwork().last, subnet1)
        self.assertIPBestMatchesSubnet(subnet2.get_ipnetwork().last, subnet2)
        self.assertIPBestMatchesSubnet(subnet3.get_ipnetwork().last, subnet3)

    def test_get_subnets_with_ip_finds_matching_ipv6_subnet(self):
        subnet = factory.make_Subnet(cidr=factory.make_ipv6_network())
        self.assertIPBestMatchesSubnet(subnet.get_ipnetwork().first, subnet)
        self.assertIPBestMatchesSubnet(subnet.get_ipnetwork().last, subnet)

    def test_get_subnets_with_ip_finds_most_specific_ipv6_subnet(self):
        subnet1 = factory.make_Subnet(cidr=IPNetwork("2001:db8::/32"))
        subnet2 = factory.make_Subnet(cidr=IPNetwork("2001:db8::/48"))
        subnet3 = factory.make_Subnet(cidr=IPNetwork("2001:db8::/64"))
        self.assertIPBestMatchesSubnet(subnet1.get_ipnetwork().first, subnet3)
        self.assertIPBestMatchesSubnet(subnet1.get_ipnetwork().last, subnet1)
        self.assertIPBestMatchesSubnet(subnet2.get_ipnetwork().last, subnet2)
        self.assertIPBestMatchesSubnet(subnet3.get_ipnetwork().last, subnet3)

    def test_get_subnets_with_ip_returns_empty_list_if_not_found(self):
        network = factory._make_random_network()
        factory.make_Subnet()
        self.assertIPBestMatchesSubnet(network.first - 1, None)
        self.assertIPBestMatchesSubnet(network.first + 1, None)

    def make_random_parent(self, net, bits=None):
        if bits is None:
            bits = random.randint(1, 3)
        net = IPNetwork(net)
        if net.version == 6 and net.prefixlen - bits > 124:
            bits = net.prefixlen - 124
        elif net.version == 4 and net.prefixlen - bits > 24:
            bits = net.prefixlen - 24
        parent = IPNetwork("%s/%d" % (net.network, net.prefixlen - bits))
        parent = IPNetwork("%s/%d" % (parent.network, parent.prefixlen))
        return parent

    def test_get_smallest_enclosing_sane_subnet_returns_none_when_none(self):
        subnet = factory.make_Subnet()
        self.assertIsNone(subnet.get_smallest_enclosing_sane_subnet())

    @settings(deadline=None)
    @given(integers(25, 29), integers(2, 5))
    def test_get_smallest_enclosing_sane_subnet_finds_parent_ipv4(
        self, subnet_mask, parent_bits
    ):
        with rollback():  # Needed when using `hypothesis`.
            subnet = factory.make_Subnet(cidr="192.168.0.0/%d" % subnet_mask)
            net = IPNetwork(subnet.cidr)
            self.assertIsNone(subnet.get_smallest_enclosing_sane_subnet())
            parent = self.make_random_parent(net, bits=parent_bits)
            parent = factory.make_Subnet(cidr=parent.cidr)
            self.assertEqual(
                parent, subnet.get_smallest_enclosing_sane_subnet()
            )

    @settings(deadline=None)
    @given(integers(100, 126), integers(2, 20))
    def test_get_smallest_enclosing_sane_subnet_finds_parent_ipv6(
        self, subnet_mask, parent_bits
    ):
        with rollback():  # Needed when using `hypothesis`.
            subnet = factory.make_Subnet(cidr="2001:db8::d0/%d" % subnet_mask)
            net = IPNetwork(subnet.cidr)
            self.assertIsNone(subnet.get_smallest_enclosing_sane_subnet())
            parent = self.make_random_parent(net, bits=parent_bits)
            parent = factory.make_Subnet(cidr=parent.cidr)
            self.assertEqual(
                parent, subnet.get_smallest_enclosing_sane_subnet()
            )

    def test_cannot_delete_with_dhcp_enabled(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges()
        with self.assertRaisesRegex(ValidationError, "servicing a dynamic"):
            subnet.delete()


class TestGetBestSubnetForIP(MAASServerTestCase):
    def test_returns_most_specific_ipv4_subnet(self):
        factory.make_Subnet(cidr="10.0.0.0/8")
        expected_subnet = factory.make_Subnet(cidr="10.1.1.0/24")
        factory.make_Subnet(cidr="10.1.0.0/16")
        subnet = Subnet.objects.get_best_subnet_for_ip("10.1.1.1")
        self.assertEqual(subnet, expected_subnet)

    def test_returns_most_specific_ipv6_subnet(self):
        factory.make_Subnet(cidr="2001::/16")
        expected_subnet = factory.make_Subnet(cidr="2001:db8:1:2::/64")
        factory.make_Subnet(cidr="2001:db8::/32")
        subnet = Subnet.objects.get_best_subnet_for_ip("2001:db8:1:2::1")
        self.assertEqual(subnet, expected_subnet)

    def test_returns_most_specific_ipv4_subnet___ipv4_mapped_ipv6_addr(self):
        factory.make_Subnet(cidr="10.0.0.0/8")
        expected_subnet = factory.make_Subnet(cidr="10.1.1.0/24")
        factory.make_Subnet(cidr="10.1.0.0/16")
        subnet = Subnet.objects.get_best_subnet_for_ip("::ffff:10.1.1.1")
        self.assertEqual(subnet, expected_subnet)

    def test_returns_none_if_no_subnet_found(self):
        factory.make_Subnet(cidr="10.0.0.0/8")
        factory.make_Subnet(cidr="10.1.1.0/24")
        factory.make_Subnet(cidr="10.1.0.0/16")
        subnet = Subnet.objects.get_best_subnet_for_ip("::")
        self.assertIsNone(subnet)


class TestSubnetLabel(MAASServerTestCase):
    def test_returns_cidr_for_null_name(self):
        network = factory.make_ip4_or_6_network()
        subnet = Subnet(name=None, cidr=network)
        self.assertEqual(str(subnet.cidr), subnet.label)

    def test_returns_cidr_for_empty_name(self):
        network = factory.make_ip4_or_6_network()
        subnet = Subnet(name="", cidr=network)
        self.assertEqual(str(subnet.cidr), subnet.label)

    def test_returns_cidr_if_name_is_cidr(self):
        network = factory.make_ip4_or_6_network()
        subnet = Subnet(name=str(network), cidr=network)
        self.assertEqual(str(subnet.cidr), subnet.label)

    def test_returns_name_and_cidr_if_name_is_different(self):
        network = factory.make_ip4_or_6_network()
        subnet = Subnet(name=factory.make_string(prefix="net"), cidr=network)
        self.assertEqual(f"{subnet.name} ({str(subnet.cidr)})", subnet.label)


class TestSubnetIPRange(MAASServerTestCase):
    def test_finds_used_ranges_includes_allocated_ip(self):
        subnet = factory.make_Subnet(
            gateway_ip="", dns_servers=[], host_bits=8
        )
        net = subnet.get_ipnetwork()
        static_range_low = inet_ntop(net.first + 50)
        static_range_high = inet_ntop(net.first + 99)
        factory.make_StaticIPAddress(
            ip=static_range_low, alloc_type=IPADDRESS_TYPE.USER_RESERVED
        )
        s = subnet.get_ipranges_in_use()
        self.assertIn(static_range_low, s)
        self.assertNotIn(static_range_high, s)

    def test_finds_used_ranges_includes_discovered_ip(self):
        subnet = factory.make_Subnet(
            gateway_ip="", dns_servers=[], host_bits=8
        )
        net = subnet.get_ipnetwork()
        static_range_low = inet_ntop(net.first + 50)
        static_range_high = inet_ntop(net.first + 99)
        factory.make_StaticIPAddress(
            ip=static_range_low, alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        s = subnet.get_ipranges_in_use()
        self.assertIn(static_range_low, s)
        self.assertNotIn(static_range_high, s)

    def test_finds_used_ranges_ignores_discovered_ip(self):
        subnet = factory.make_Subnet(
            gateway_ip="", dns_servers=[], host_bits=8
        )
        net = subnet.get_ipnetwork()
        static_range_low = inet_ntop(net.first + 50)
        static_range_high = inet_ntop(net.first + 99)
        factory.make_StaticIPAddress(
            ip=static_range_low, alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        s = subnet.get_ipranges_in_use(ignore_discovered_ips=True)
        self.assertNotIn(static_range_low, s)
        self.assertNotIn(static_range_high, s)

    def test_get_ipranges_not_in_use_includes_free_ips(self):
        subnet = factory.make_Subnet(
            gateway_ip="", dns_servers=[], host_bits=8
        )
        net = subnet.get_ipnetwork()
        static_range_low = inet_ntop(net.first + 50)
        static_range_high = inet_ntop(net.first + 99)
        factory.make_StaticIPAddress(
            ip=static_range_low, alloc_type=IPADDRESS_TYPE.USER_RESERVED
        )
        s = subnet.get_ipranges_not_in_use()
        self.assertNotIn(static_range_low, s)
        self.assertIn(static_range_high, s)

    def test_get_ipranges_not_in_use_includes_discovered_ip(self):
        subnet = factory.make_Subnet(
            gateway_ip="", dns_servers=[], host_bits=8
        )
        net = subnet.get_ipnetwork()
        static_range_low = inet_ntop(net.first + 50)
        static_range_high = inet_ntop(net.first + 99)
        factory.make_StaticIPAddress(
            ip=static_range_low, alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        s = subnet.get_ipranges_not_in_use()
        self.assertNotIn(static_range_low, s)
        self.assertIn(static_range_high, s)

    def test_get_ipranges_not_in_use_ignores_discovered_ip(self):
        subnet = factory.make_Subnet(
            gateway_ip="", dns_servers=[], host_bits=8
        )
        net = subnet.get_ipnetwork()
        static_range_low = inet_ntop(net.first + 50)
        static_range_high = inet_ntop(net.first + 99)
        factory.make_StaticIPAddress(
            ip=static_range_low, alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        s = subnet.get_ipranges_not_in_use(ignore_discovered_ips=True)
        self.assertIn(static_range_low, s)
        self.assertIn(static_range_high, s)

    def test_get_ipranges_not_in_use_excludes_ip_range(self):
        subnet = factory.make_Subnet(
            gateway_ip="", dns_servers=[], host_bits=8
        )
        net = subnet.get_ipnetwork()
        static_range_low = inet_ntop(net.first + 50)
        static_range_high = inet_ntop(net.first + 99)
        ip_range = factory.make_IPRange(
            subnet=subnet,
            start_ip=static_range_low,
            end_ip=static_range_high,
            alloc_type=IPRANGE_TYPE.RESERVED,
        )
        s = subnet.get_ipranges_not_in_use(
            ignore_discovered_ips=True, exclude_ip_ranges=[ip_range]
        )
        self.assertIn(static_range_low, s)
        self.assertIn(static_range_high, s)

    def test_get_iprange_usage_includes_used_and_unused_ips(self):
        subnet = factory.make_Subnet(
            gateway_ip="", dns_servers=[], host_bits=8
        )
        net = subnet.get_ipnetwork()
        static_range_low = inet_ntop(net.first + 50)
        static_range_high = inet_ntop(net.first + 99)
        factory.make_StaticIPAddress(
            ip=static_range_low, alloc_type=IPADDRESS_TYPE.USER_RESERVED
        )
        s = subnet.get_iprange_usage()
        self.assertIn(static_range_low, s)
        self.assertIn(static_range_high, s)

    def test_get_iprange_usage_includes_static_route_gateway_ip(self):
        subnet = factory.make_Subnet(
            gateway_ip="", dns_servers=[], host_bits=8
        )
        gateway_ip_1 = factory.pick_ip_in_Subnet(subnet)
        gateway_ip_2 = factory.pick_ip_in_Subnet(
            subnet, but_not=[gateway_ip_1]
        )
        factory.make_StaticRoute(source=subnet, gateway_ip=gateway_ip_1)
        factory.make_StaticRoute(source=subnet, gateway_ip=gateway_ip_2)
        s = subnet.get_iprange_usage()
        self.assertIn(gateway_ip_1, s)
        self.assertIn(gateway_ip_2, s)

    def get__get_iprange_usage_includes_neighbours_on_request(self):
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/30", gateway_ip=None, dns_servers=None
        )
        rackif = factory.make_Interface(vlan=subnet.vlan)
        factory.make_Discovery(ip="10.0.0.1", interface=rackif)
        iprange = subnet.get_iprange_usage(with_neighbours=True)
        self.assertIn(MAASIPRange("10.0.0.1", purpose="neighbour"), iprange)

    def get__get_iprange_usage_excludes_neighbours_by_default(self):
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/30", gateway_ip=None, dns_servers=None
        )
        rackif = factory.make_Interface(vlan=subnet.vlan)
        factory.make_Discovery(ip="10.0.0.1", interface=rackif)
        iprange = subnet.get_iprange_usage(with_neighbours=True)
        self.assertNotIn(
            MAASIPRange("10.0.0.1", purpose="neighbour"),
            iprange,
        )


class TestRenderJSONForRelatedIPs(MAASServerTestCase):
    def test_sorts_by_ip_address(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        factory.make_StaticIPAddress(
            ip="10.0.0.2",
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            subnet=subnet,
        )
        factory.make_StaticIPAddress(
            ip="10.0.0.154",
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            subnet=subnet,
        )
        factory.make_StaticIPAddress(
            ip="10.0.0.1",
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            subnet=subnet,
        )
        json = subnet.render_json_for_related_ips()
        self.assertEqual(json[0]["ip"], "10.0.0.1")
        self.assertEqual(json[1]["ip"], "10.0.0.2")
        self.assertEqual(json[2]["ip"], "10.0.0.154")

    def test_returns_expected_json(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        ip = factory.make_StaticIPAddress(
            ip="10.0.0.1",
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            subnet=subnet,
        )
        json = subnet.render_json_for_related_ips(
            with_username=True, with_summary=True
        )
        self.assertEqual(
            [ip.render_json(with_username=True, with_summary=True)],
            json,
        )

    def test_includes_node_summary(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, status=NODE_STATUS.READY
        )
        iface = node.current_config.interface_set.first()
        ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet, interface=iface
        )
        json = subnet.render_json_for_related_ips(
            with_username=True, with_summary=True
        )
        self.assertEqual(list, type(json))
        for result in json:
            if result["ip"] == ip.ip:
                self.assertEqual(dict, type(result["node_summary"]))
                node_summary = result["node_summary"]
                self.assertEqual(node.fqdn, node_summary["fqdn"])
                self.assertEqual(iface.name, node_summary["via"])
                self.assertEqual(node.system_id, node_summary["system_id"])
                self.assertEqual(node.node_type, node_summary["node_type"])
                self.assertEqual(node.hostname, node_summary["hostname"])
                return
        self.assertFalse(True, "Could not find IP address in output.")

    def test_includes_bmcs(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet, interface=None
        )
        bmc = factory.make_BMC(ip_address=ip)
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, status=NODE_STATUS.READY, bmc=bmc
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet,
            interface=node.current_config.interface_set.first(),
        )
        subnet = reload_object(subnet)
        json = subnet.render_json_for_related_ips(
            with_username=True, with_summary=True
        )
        self.assertEqual(list, type(json))
        for result in json:
            if result["ip"] == ip.ip:
                self.assertEqual(list, type(result["bmcs"]))
                bmc_json = result["bmcs"][0]
                self.assertEqual(bmc.id, bmc_json["id"])
                self.assertEqual(bmc.power_type, bmc_json["power_type"])
                self.assertEqual(
                    node.hostname, bmc_json["nodes"][0]["hostname"]
                )
                self.assertEqual(
                    node.system_id, bmc_json["nodes"][0]["system_id"]
                )
                return
        self.assertFalse(True, "Could not find IP address in output.")

    def test_includes_dns_records(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet, interface=None
        )
        dnsresource = factory.make_DNSResource(
            ip_addresses=[ip], subnet=subnet
        )
        json = subnet.render_json_for_related_ips(
            with_username=True, with_summary=True
        )
        self.assertEqual(list, type(json))
        for result in json:
            if result["ip"] == ip.ip:
                self.assertEqual(list, type(result["dns_records"]))
                dns_json = result["dns_records"][0]
                self.assertEqual(dnsresource.id, dns_json["id"])
                self.assertEqual(dnsresource.name, dns_json["name"])
                self.assertEqual(dnsresource.domain.name, dns_json["domain"])
                return
        self.assertFalse(True, "Could not find IP address in output.")

    def test_excludes_blank_addresses(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        factory.make_StaticIPAddress(
            ip=None, alloc_type=IPADDRESS_TYPE.DISCOVERED, subnet=subnet
        )
        factory.make_StaticIPAddress(
            ip="10.0.0.1",
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            subnet=subnet,
        )
        json = subnet.render_json_for_related_ips()
        self.assertEqual(json[0]["ip"], "10.0.0.1")
        self.assertEqual(len(json), 1)

    def test_query_count_stable(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        for _ in range(10):
            ip = factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.USER_RESERVED, subnet=subnet
            )
            factory.make_DNSResource(ip_addresses=[ip], subnet=subnet)
        for _ in range(10):
            node = factory.make_Node_with_Interface_on_Subnet(
                subnet=subnet, status=NODE_STATUS.READY
            )
            iface = node.current_config.interface_set.first()
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.STICKY,
                subnet=subnet,
                interface=iface,
            )
        for _ in range(10):
            ip = factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet, interface=None
            )
            bmc = factory.make_BMC(ip_address=ip)
            node = factory.make_Node_with_Interface_on_Subnet(
                subnet=subnet, status=NODE_STATUS.READY, bmc=bmc
            )
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.STICKY,
                subnet=subnet,
                interface=node.current_config.interface_set.first(),
            )
        count, _ = count_queries(subnet.render_json_for_related_ips)
        self.assertEqual(9, count)


class TestSubnetGetRelatedRanges(MAASServerTestCase):
    def test_get_dynamic_ranges_returns_dynamic_range_filter(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_dynamic_range=True, with_static_range=True
        )
        dynamic_ranges = subnet.get_dynamic_ranges()
        ranges = list(dynamic_ranges)
        self.assertEqual(len(ranges), 1)
        self.assertEqual(IPRANGE_TYPE.DYNAMIC, ranges[0].type)

    def test_get_dynamic_ranges_returns_unmanaged_dynamic_range_filter(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_dynamic_range=True, with_static_range=True, unmanaged=True
        )
        dynamic_ranges = subnet.get_dynamic_ranges()
        ranges = list(dynamic_ranges)
        self.assertEqual(len(ranges), 1)
        self.assertEqual(IPRANGE_TYPE.DYNAMIC, ranges[0].type)

    def test_get_dynamic_range_for_ip(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_dynamic_range=True,
            with_static_range=True,
            unmanaged=random.choice([True, False]),
        )
        dynamic_range = subnet.get_dynamic_ranges().first()
        start_ip = dynamic_range.start_ip
        end_ip = dynamic_range.end_ip
        random_ip = str(
            IPAddress(
                random.randint(
                    int(IPAddress(start_ip) + 1), int(IPAddress(end_ip) - 1)
                )
            )
        )
        self.assertIsNone(subnet.get_dynamic_range_for_ip("0.0.0.0"))
        self.assertEqual(
            dynamic_range, subnet.get_dynamic_range_for_ip(start_ip)
        )
        self.assertEqual(
            dynamic_range, subnet.get_dynamic_range_for_ip(end_ip)
        )
        self.assertEqual(
            dynamic_range, subnet.get_dynamic_range_for_ip(random_ip)
        )


class TestSubnetGetMAASIPSetForNeighbours(MAASServerTestCase):
    def test_returns_observed_neighbours(self):
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/30", gateway_ip=None, dns_servers=None
        )
        rackif = factory.make_Interface(vlan=subnet.vlan)
        factory.make_Discovery(ip="10.0.0.1", interface=rackif)
        ipset = subnet.get_maasipset_for_neighbours()
        self.assertIn("10.0.0.1", ipset)
        self.assertNotIn("10.0.0.2", ipset)

    def test_excludes_neighbours_with_static_ip_addresses(self):
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/30", gateway_ip=None, dns_servers=None
        )
        rackif = factory.make_Interface(vlan=subnet.vlan)
        factory.make_Discovery(ip="10.0.0.1", interface=rackif)
        factory.make_StaticIPAddress(ip="10.0.0.1", cidr="10.0.0.0/30")
        ipset = subnet.get_maasipset_for_neighbours()
        self.assertNotIn("10.0.0.1", ipset)
        self.assertNotIn("10.0.0.2", ipset)


class TestSubnetGetLeastRecentlySeenUnknownNeighbour(MAASServerTestCase):
    def test_returns_least_recently_seen_neighbour(self):
        # Note: 10.0.0.0/30 --> 10.0.0.1 and 10.0.0.0.2 are usable.
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/30", gateway_ip=None, dns_servers=None
        )
        rackif = factory.make_Interface(vlan=subnet.vlan)
        now = timezone.now()
        yesterday = now - timedelta(days=1)
        factory.make_Discovery(ip="10.0.0.1", interface=rackif, updated=now)
        factory.make_Discovery(
            ip="10.0.0.2", interface=rackif, updated=yesterday
        )
        discovery = subnet.get_least_recently_seen_unknown_neighbour()
        self.assertEqual("10.0.0.2", discovery.ip)

    def test_returns_least_recently_seen_neighbour_excludes_in_use(self):
        # Note: 10.0.0.0/30 --> 10.0.0.1 and 10.0.0.0.2 are usable.
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/30", gateway_ip=None, dns_servers=None
        )
        rackif = factory.make_Interface(vlan=subnet.vlan)
        now = timezone.now()
        yesterday = now - timedelta(days=1)
        factory.make_Discovery(ip="10.0.0.1", interface=rackif, updated=now)
        factory.make_Discovery(
            ip="10.0.0.2", interface=rackif, updated=yesterday
        )
        factory.make_IPRange(
            subnet,
            start_ip="10.0.0.2",
            end_ip="10.0.0.2",
            alloc_type=IPRANGE_TYPE.RESERVED,
        )
        discovery = subnet.get_least_recently_seen_unknown_neighbour()
        self.assertEqual("10.0.0.1", discovery.ip)

    def test_returns_least_recently_seen_neighbour_handles_unmanaged(self):
        # Note: 10.0.0.0/29 --> 10.0.0.1 through 10.0.0.0.6 are usable.
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/29",
            gateway_ip=None,
            dns_servers=None,
            managed=False,
        )
        rackif = factory.make_Interface(vlan=subnet.vlan)
        now = timezone.now()
        yesterday = now - timedelta(days=1)
        factory.make_Discovery(ip="10.0.0.1", interface=rackif, updated=now)
        factory.make_Discovery(
            ip="10.0.0.2", interface=rackif, updated=yesterday
        )
        factory.make_Discovery(ip="10.0.0.3", interface=rackif, updated=now)
        factory.make_Discovery(
            ip="10.0.0.4", interface=rackif, updated=yesterday
        )
        factory.make_IPRange(
            subnet,
            start_ip="10.0.0.1",
            end_ip="10.0.0.2",
            alloc_type=IPRANGE_TYPE.RESERVED,
        )
        discovery = subnet.get_least_recently_seen_unknown_neighbour()
        self.assertEqual("10.0.0.2", discovery.ip)

    def test_returns_none_if_no_neighbours(self):
        # Note: 10.0.0.0/30 --> 10.0.0.1 and 10.0.0.0.2 are usable.
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/30", gateway_ip=None, dns_servers=None
        )
        ip = subnet.get_least_recently_seen_unknown_neighbour()
        self.assertIsNone(ip)


class TestSubnetGetNextIPForAllocation(MAASServerTestCase):
    scenarios = (
        ("managed", {"managed": True}),
        ("unmanaged", {"managed": False}),
    )

    def make_Subnet(self, *args, **kwargs):
        """Helper to create a subnet for this test suite.

        Eclipses the entire subnet with an IPRange of type RESERVED, so that
        unmanaged and managed test scenarios are expected to behave the same.
        """
        cidr = kwargs.get("cidr")
        network = IPNetwork(cidr)
        # Note: these tests assume IPv4.
        first = str(IPAddress(network.first + 1))
        last = str(IPAddress(network.last - 1))
        subnet = factory.make_Subnet(*args, managed=self.managed, **kwargs)
        if not self.managed:
            factory.make_IPRange(
                subnet,
                start_ip=first,
                end_ip=last,
                alloc_type=IPRANGE_TYPE.RESERVED,
            )
            subnet = reload_object(subnet)
        return subnet

    def test_raises_if_no_free_addresses(self):
        # Note: 10.0.0.0/30 --> 10.0.0.1 and 10.0.0.0.2 are usable.
        subnet = self.make_Subnet(
            cidr="10.0.0.0/30", gateway_ip="10.0.0.1", dns_servers=["10.0.0.2"]
        )
        with self.assertRaisesRegex(
            StaticIPAddressExhaustion,
            "No more IPs available in subnet: 10.0.0.0/30.",
        ):
            subnet.get_next_ip_for_allocation()

    def test_allocates_next_free_address(self):
        # Note: 10.0.0.0/30 --> 10.0.0.1 and 10.0.0.0.2 are usable.
        subnet = self.make_Subnet(
            cidr="10.0.0.0/30", gateway_ip=None, dns_servers=None
        )
        [ip] = subnet.get_next_ip_for_allocation()
        self.assertEqual("10.0.0.1", ip)

    def test_avoids_gateway_ip(self):
        # Note: 10.0.0.0/30 --> 10.0.0.1 and 10.0.0.0.2 are usable.
        subnet = self.make_Subnet(
            cidr="10.0.0.0/30", gateway_ip="10.0.0.1", dns_servers=None
        )
        [ip] = subnet.get_next_ip_for_allocation()
        self.assertEqual("10.0.0.2", ip)

    def test_avoids_excluded_addresses(self):
        # Note: 10.0.0.0/30 --> 10.0.0.1 and 10.0.0.0.2 are usable.
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/30", gateway_ip=None, dns_servers=None
        )
        [ip] = subnet.get_next_ip_for_allocation(
            exclude_addresses=["10.0.0.1"]
        )
        self.assertEqual("10.0.0.2", ip)

    def test_avoids_excluded_addresses_count(self):
        # Note: 10.0.0.0/29 --> 10.0.0.1 and 10.0.0.0.6 are usable.
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/29", gateway_ip=None, dns_servers=None
        )
        ips = subnet.get_next_ip_for_allocation(
            exclude_addresses=["10.0.0.3"], count=6
        )
        self.assertCountEqual(
            ips, ["10.0.0.1", "10.0.0.2", "10.0.0.4", "10.0.0.5", "10.0.0.6"]
        )

    def test_avoids_dns_servers(self):
        # Note: 10.0.0.0/30 --> 10.0.0.1 and 10.0.0.0.2 are usable.
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/30", gateway_ip=None, dns_servers=["10.0.0.1"]
        )
        [ip] = subnet.get_next_ip_for_allocation()
        self.assertEqual("10.0.0.2", ip)

    def test_avoids_observed_neighbours(self):
        # Note: 10.0.0.0/30 --> 10.0.0.1 and 10.0.0.0.2 are usable.
        subnet = self.make_Subnet(
            cidr="10.0.0.0/30", gateway_ip=None, dns_servers=None
        )
        rackif = factory.make_Interface(vlan=subnet.vlan)
        factory.make_Discovery(ip="10.0.0.1", interface=rackif)
        [ip] = subnet.get_next_ip_for_allocation()
        self.assertEqual("10.0.0.2", ip)

    def test_logs_if_suggests_previously_observed_neighbour(self):
        # Note: 10.0.0.0/30 --> 10.0.0.1 and 10.0.0.0.2 are usable.
        subnet = self.make_Subnet(
            cidr="10.0.0.0/30", gateway_ip=None, dns_servers=None
        )
        rackif = factory.make_Interface(vlan=subnet.vlan)
        dt_now = now()
        yesterday = dt_now - timedelta(days=1)
        factory.make_Discovery(ip="10.0.0.1", interface=rackif, updated=dt_now)
        factory.make_Discovery(
            ip="10.0.0.2", interface=rackif, updated=yesterday
        )
        logger = self.useFixture(FakeLogger("maas"))
        [ip] = subnet.get_next_ip_for_allocation()
        self.assertEqual("10.0.0.2", ip)
        self.assertRegex(
            logger.output,
            f"Next IP address to allocate from '.*' has been observed previously: 10.0.0.2 was last claimed by .* via .* on .* at {re.escape(str(yesterday))}.\n",
        )

    def test_uses_smallest_free_range_when_not_considering_neighbours(self):
        # Note: 10.0.0.0/29 --> 10.0.0.1 through 10.0.0.0.6 are usable.
        subnet = self.make_Subnet(
            cidr="10.0.0.0/29", gateway_ip=None, dns_servers=None
        )
        # With .4 in use, the free ranges are {1, 2, 3}, {5, 6}. So MAAS should
        # select 10.0.0.5, since that is the first address in the smallest
        # available range.
        factory.make_StaticIPAddress(ip="10.0.0.4", cidr="10.0.0.0/29")
        [ip] = subnet.get_next_ip_for_allocation()
        self.assertEqual("10.0.0.5", ip)


class TestUnmanagedSubnets(MAASServerTestCase):
    def test_allocation_uses_reserved_range(self):
        # Note: 10.0.0.0/29 --> 10.0.0.1 through 10.0.0.0.6 are usable.
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/29",
            gateway_ip=None,
            dns_servers=None,
            managed=False,
        )
        range1 = factory.make_IPRange(
            subnet,
            start_ip="10.0.0.1",
            end_ip="10.0.0.1",
            alloc_type=IPRANGE_TYPE.RESERVED,
        )
        subnet = reload_object(subnet)
        [ip] = subnet.get_next_ip_for_allocation()
        self.assertEqual("10.0.0.1", ip)
        range1.delete()
        factory.make_IPRange(
            subnet,
            start_ip="10.0.0.6",
            end_ip="10.0.0.6",
            alloc_type=IPRANGE_TYPE.RESERVED,
        )
        subnet = reload_object(subnet)
        [ip] = subnet.get_next_ip_for_allocation()
        self.assertEqual("10.0.0.6", ip)

    def test_allocation_uses_multiple_reserved_ranges(self):
        # Note: 10.0.0.0/29 --> 10.0.0.1 through 10.0.0.0.6 are usable.
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/29",
            gateway_ip=None,
            dns_servers=None,
            managed=False,
        )
        factory.make_IPRange(
            subnet,
            start_ip="10.0.0.3",
            end_ip="10.0.0.4",
            alloc_type=IPRANGE_TYPE.RESERVED,
        )
        subnet = reload_object(subnet)
        [ip] = subnet.get_next_ip_for_allocation()
        self.assertEqual("10.0.0.3", ip)
        factory.make_StaticIPAddress(ip)
        [ip] = subnet.get_next_ip_for_allocation()
        self.assertEqual("10.0.0.4", ip)
        factory.make_StaticIPAddress(ip)
        with self.assertRaisesRegex(
            StaticIPAddressExhaustion,
            "No more IPs available in subnet: 10.0.0.0/29.",
        ):
            subnet.get_next_ip_for_allocation()


class TestSubnetIPExhaustionNotifications(MAASServerTestCase):
    """Tests the effects of the signal handlers on the StaticIPAddress and
    IPRange classes, which will cause the subnet notification creation or
    deletion code to be executed.
    """

    # For reference, IPv4:
    #     /32: 1 address
    #     /31: 2 address (tunneling subnet, no broadcast/network)
    #     /30: 4 addresses, 2 usable
    #     /29: 8 addresses, 6 usable
    #     /28: 16 addresses, 14 usable
    #     /27: 32 addresses, 30 usable
    #     /26: 64 addresses, 62 usable
    #     /25: 128 addresses, 126 usable
    #     /24: 256 addresses, 254 usable
    #     /23: 512 addresses, 510 usable
    #     /22: 1024 addresses, 1022 usable
    #     /21: 2048 addresses, 2046 usable
    #
    # IPv6:
    #     /128: 1 address
    #     /127: 2 address (tunneling subnet)
    #     /126: 4 addresses
    #     /125: 8 addresses
    #     /124: 16 addresses
    #     /123: 32 addresses
    #     /122: 64 addresses
    #     /121: 128 addresses
    #     /120: 256 addresses
    #     /119: 512 addresses
    #     /118: 1024 addresses
    #     /117: 2048 addresses

    scenarios = (
        # Default threshold is 16.
        (
            "Default threshold warns for /26",
            {
                "threshold": None,
                "cidr": "10.0.0.0/26",
                "expected_notification": True,
            },
        ),
        (
            "Default threshold doesn't warn for /27",
            {
                "threshold": None,
                "cidr": "10.0.0.0/27",
                "expected_notification": False,
            },
        ),
        (
            "threshold=1 warns for /29",
            {
                "threshold": 1,
                "cidr": "10.0.0.0/29",
                "expected_notification": True,
            },
        ),
        (
            "threshold=0 never warns",
            {
                "threshold": 0,
                "cidr": "10.0.0.0/29",
                "expected_notification": False,
            },
        ),
        (
            "Default threshold warns for /122 IPv6",
            {
                "threshold": None,
                "cidr": "2001::/26",
                "expected_notification": True,
            },
        ),
        (
            "Default threshold doesn't warn for /123 IPv6",
            {
                "threshold": None,
                "cidr": "2001::/123",
                "expected_notification": False,
            },
        ),
        (
            "Default threshold warns for /48 IPv6",
            {
                "threshold": None,
                "cidr": "2001::/48",
                "expected_notification": True,
            },
        ),
        (
            "Default threshold warns for /16 IPv6",
            {
                "threshold": None,
                "cidr": "2001::/16",
                "expected_notification": True,
            },
        ),
        (
            "threshold=1 warns for /125 IPv6",
            {
                "threshold": 1,
                "cidr": "2001::/125",
                "expected_notification": True,
            },
        ),
        (
            "threshold=0 never warns for IPv6",
            {
                "threshold": 0,
                "cidr": "2001::/127",
                "expected_notification": False,
            },
        ),
    )

    def setUp(self):
        super().setUp()
        self.ipnetwork = IPNetwork(self.cidr)
        self.subnet = factory.make_Subnet(
            cidr=self.cidr, dns_servers=[], gateway_ip=None, space=None
        )
        if self.threshold is not None:
            Config.objects.set_config(
                "subnet_ip_exhaustion_threshold_count", self.threshold
            )
        self.threshold = Config.objects.get_config(
            "subnet_ip_exhaustion_threshold_count"
        )

    def test_notification_when_ip_saved(self):
        # Create an IP range to fill ip most of the subnet, but not enough
        # to reach the threshold.
        network_size = self.ipnetwork.size - 2
        if self.ipnetwork.version == 6:
            network_size += 1
        desired_range_size = network_size - self.threshold - 1
        if desired_range_size > 0:
            range_start = self.ipnetwork.first + 1
            range_end = (
                self.ipnetwork.first + network_size - self.threshold - 1
            )
            # Cover most of the threshold (except one IP address) with an IP
            # range, so that when we allocate a single IP we go over the limit.
            factory.make_IPRange(
                start_ip=str(IPAddress(range_start)),
                end_ip=str(IPAddress(range_end)),
                subnet=self.subnet,
                alloc_type=IPRANGE_TYPE.RESERVED,
            )
        else:
            # Dummy value so we allocate an IP below.
            range_end = self.ipnetwork.first
        ident = "ip_exhaustion__subnet_%d" % self.subnet.id
        notification = get_one(Notification.objects.filter(ident=ident))
        notification_exists = notification is not None
        # By now, the notification should never have been created. (If so,
        # it was created too early.)
        self.assertFalse(notification_exists)
        factory.make_StaticIPAddress(
            ip=str(IPAddress(range_end + 1)),
            subnet=self.subnet,
            alloc_type=IPADDRESS_TYPE.STICKY,
        )
        notification = get_one(Notification.objects.filter(ident=ident))
        notification_exists = notification is not None
        # ... but creating another single IP address in the subnet should push
        # it over the edge.
        self.assertEqual(self.expected_notification, notification_exists)

    def test_notification_when_range_saved(self):
        # Calculate a range size large enough to push us over the threshold.
        network_size = self.ipnetwork.size - 2
        if self.ipnetwork.version == 6:
            network_size += 1
        range_start = self.ipnetwork.first + 1
        range_end = (self.ipnetwork.first + network_size) - (
            min(self.threshold, network_size)
        )
        factory.make_IPRange(
            start_ip=str(IPAddress(range_start)),
            end_ip=str(IPAddress(range_end)),
            subnet=self.subnet,
            alloc_type=IPRANGE_TYPE.RESERVED,
        )
        ident = "ip_exhaustion__subnet_%d" % self.subnet.id
        notification = get_one(Notification.objects.filter(ident=ident))
        notification_exists = notification is not None
        self.assertEqual(self.expected_notification, notification_exists)

    def test_notification_cleared_when_range_deleted(self):
        # Calculate a range size large enough to push us over the threshold.
        network_size = self.ipnetwork.size - 2
        if self.ipnetwork.version == 6:
            network_size += 1
        range_start = self.ipnetwork.first + 1
        range_end = (self.ipnetwork.first + network_size) - (
            min(self.threshold, network_size)
        )
        range = factory.make_IPRange(
            start_ip=str(IPAddress(range_start)),
            end_ip=str(IPAddress(range_end)),
            subnet=self.subnet,
            alloc_type=IPRANGE_TYPE.RESERVED,
        )
        ident = "ip_exhaustion__subnet_%d" % self.subnet.id
        notification = get_one(Notification.objects.filter(ident=ident))
        notification_exists = notification is not None
        self.assertEqual(self.expected_notification, notification_exists)
        range.delete()
        notification = get_one(Notification.objects.filter(ident=ident))
        notification_exists = notification is not None
        self.assertFalse(notification_exists)

    def test_notification_cleared_on_next_save_if_threshold_changes(self):
        # Calculate a range size large enough to push us over the threshold.
        network_size = self.ipnetwork.size - 2
        if self.ipnetwork.version == 6:
            network_size += 1
        range_start = self.ipnetwork.first + 1
        range_end = (self.ipnetwork.first + network_size) - (
            min(self.threshold, network_size)
        )
        range = factory.make_IPRange(
            start_ip=str(IPAddress(range_start)),
            end_ip=str(IPAddress(range_end)),
            subnet=self.subnet,
            alloc_type=IPRANGE_TYPE.RESERVED,
        )
        ident = "ip_exhaustion__subnet_%d" % self.subnet.id
        notification = get_one(Notification.objects.filter(ident=ident))
        notification_exists = notification is not None
        self.assertEqual(self.expected_notification, notification_exists)
        Config.objects.set_config("subnet_ip_exhaustion_threshold_count", 0)
        range.save(force_update=True)
        notification = get_one(Notification.objects.filter(ident=ident))
        notification_exists = notification is not None
        self.assertFalse(notification_exists)

    def test_notification_cleared_when_ip_deleted(self):
        # Create an IP range to fill ip most of the subnet, but not enough
        # to reach the threshold.
        network_size = self.ipnetwork.size - 2
        if self.ipnetwork.version == 6:
            network_size += 1
        desired_range_size = network_size - self.threshold - 1
        if desired_range_size > 0:
            range_start = self.ipnetwork.first + 1
            range_end = (
                self.ipnetwork.first + network_size - self.threshold - 1
            )
            # Cover most of the threshold (except one IP address) with an IP
            # range, so that when we allocate a single IP we go over the limit.
            factory.make_IPRange(
                start_ip=str(IPAddress(range_start)),
                end_ip=str(IPAddress(range_end)),
                subnet=self.subnet,
                alloc_type=IPRANGE_TYPE.RESERVED,
            )
        else:
            # Dummy value so we allocate an IP below.
            range_end = self.ipnetwork.first
        ident = "ip_exhaustion__subnet_%d" % self.subnet.id
        notification = get_one(Notification.objects.filter(ident=ident))
        notification_exists = notification is not None
        # By now, the notification should never have been created. (If so,
        # it was created too early.)
        self.assertFalse(notification_exists)
        ip = factory.make_StaticIPAddress(
            ip=str(IPAddress(range_end + 1)),
            subnet=self.subnet,
            alloc_type=IPADDRESS_TYPE.STICKY,
        )
        notification = get_one(Notification.objects.filter(ident=ident))
        notification_exists = notification is not None
        # ... but creating another single IP address in the subnet should push
        # it over the edge.
        self.assertEqual(self.expected_notification, notification_exists)
        ip.delete()
        notification = get_one(Notification.objects.filter(ident=ident))
        notification_exists = notification is not None
        self.assertFalse(notification_exists)


class TestGetAllocatedIps(MAASServerTestCase):
    def test_no_ips(self):
        subnet1 = factory.make_Subnet()
        subnet2 = factory.make_Subnet()
        result = get_allocated_ips([subnet1, subnet2])
        result1, result2 = result
        self.assertIs(subnet1, result1[0])
        self.assertEqual([], result1[1])
        self.assertIs(subnet2, result2[0])
        self.assertEqual([], result2[1])

    def test_no_allocated_ips(self):
        subnet = factory.make_Subnet()
        # There may be records with emtpy ip fields in the db, for
        # expired leases, but still link an interface to a subnet.
        # Such records are ignored.
        factory.make_StaticIPAddress(subnet=subnet, ip=None)
        factory.make_StaticIPAddress(subnet=subnet, ip="")
        [(_, ips)] = get_allocated_ips([subnet])
        self.assertEqual([], ips)

    def test_allocated_ips(self):
        subnet1 = factory.make_Subnet()
        ip1 = factory.make_StaticIPAddress(subnet=subnet1)
        ip2 = factory.make_StaticIPAddress(subnet=subnet1)
        subnet2 = factory.make_Subnet()
        ip3 = factory.make_StaticIPAddress(subnet=subnet2)
        queries, result = count_queries(
            lambda: list(get_allocated_ips([subnet1, subnet2]))
        )
        [(returned_subnet1, ips1), (returned_subnet2, ips2)] = result
        self.assertIs(subnet1, returned_subnet1)
        self.assertCountEqual(
            [(ip1.ip, ip1.alloc_type), (ip2.ip, ip2.alloc_type)], ips1
        )
        self.assertIs(subnet2, returned_subnet2)
        self.assertEqual([(ip3.ip, ip3.alloc_type)], ips2)
        self.assertEqual(1, queries)

    def test_subnet_allocated_ips(self):
        subnet = factory.make_Subnet()
        ip1 = factory.make_StaticIPAddress(subnet=subnet)
        ip2 = factory.make_StaticIPAddress(subnet=subnet)
        queries, ips = count_queries(subnet.get_allocated_ips)
        self.assertCountEqual(
            [(ip1.ip, ip1.alloc_type), (ip2.ip, ip2.alloc_type)], ips
        )
        self.assertEqual(1, queries)

    def test_subnet_allocated_ips_cached(self):
        subnet = factory.make_Subnet()
        ip1 = factory.make_StaticIPAddress(subnet=subnet)
        ip2 = factory.make_StaticIPAddress(subnet=subnet)
        [(_, ips)] = get_allocated_ips([subnet])
        subnet.cache_allocated_ips(ips)
        queries, ips = count_queries(subnet.get_allocated_ips)
        self.assertCountEqual(
            [(ip1.ip, ip1.alloc_type), (ip2.ip, ip2.alloc_type)], ips
        )
        self.assertEqual(0, queries)


class TestGetBootRackcontrollerIPs(MAASServerTestCase):
    def test_no_dhcpd(self):
        vlan = factory.make_VLAN(
            dhcp_on=False,
            primary_rack=None,
            secondary_rack=None,
        )
        subnet = factory.make_Subnet(vlan=vlan, cidr="10.10.0.0/24")
        factory.make_rack_with_interfaces(eth0=["10.10.0.2/24"])
        self.assertEqual([], get_boot_rackcontroller_ips(subnet))

    def test_with_primary(self):
        vlan = factory.make_VLAN(
            dhcp_on=False,
            primary_rack=None,
            secondary_rack=None,
        )
        subnet = factory.make_Subnet(vlan=vlan, cidr="10.10.0.0/24")
        # Create another vlan to make sure it doesn't get selected.
        factory.make_Subnet(cidr="10.20.0.0/24")
        rack1 = factory.make_rack_with_interfaces(
            eth0=["10.10.0.2/24"],
            eth1=["10.20.0.2/24"],
        )
        vlan.dhcp_on = True
        vlan.primary_rack = rack1

        with post_commit_hooks:
            vlan.save()
        self.assertEqual(["10.10.0.2"], get_boot_rackcontroller_ips(subnet))

    def test_with_secondary(self):
        vlan = factory.make_VLAN(
            dhcp_on=False,
            primary_rack=None,
            secondary_rack=None,
        )
        subnet = factory.make_Subnet(vlan=vlan, cidr="10.10.0.0/24")
        rack1 = factory.make_rack_with_interfaces(eth0=["10.10.0.2/24"])
        rack2 = factory.make_rack_with_interfaces(eth0=["10.10.0.3/24"])
        vlan.dhcp_on = True
        vlan.primary_rack = rack1
        vlan.secondary_rack = rack2

        with post_commit_hooks:
            vlan.save()
        self.assertCountEqual(
            ["10.10.0.2", "10.10.0.3"], get_boot_rackcontroller_ips(subnet)
        )

    def test_with_multiple_subnets(self):
        vlan = factory.make_VLAN(
            dhcp_on=False,
            primary_rack=None,
            secondary_rack=None,
        )
        subnet1 = factory.make_Subnet(vlan=vlan, cidr="10.10.1.0/24")
        factory.make_Subnet(vlan=vlan, cidr="10.10.0.0/24")
        factory.make_Subnet(vlan=vlan, cidr="10.10.2.0/24")
        rack1 = factory.make_rack_with_interfaces(
            eth0=["10.10.0.2/24", "10.10.1.2/24", "10.10.2.2/24"]
        )
        rack2 = factory.make_rack_with_interfaces(
            eth0=["10.10.0.3/24", "10.10.1.3/24", "10.10.2.3/24"]
        )
        vlan.dhcp_on = True
        vlan.primary_rack = rack1
        vlan.secondary_rack = rack2

        with post_commit_hooks:
            vlan.save()

        boot_ips = get_boot_rackcontroller_ips(subnet1)
        self.assertCountEqual(
            [
                "10.10.1.2",
                "10.10.2.2",
                "10.10.0.2",
                "10.10.1.3",
                "10.10.2.3",
                "10.10.0.3",
            ],
            boot_ips,
        )
        # 10.10.1.2 and 10.10.1.3 are always first, since they are
        # from the passed in subnet.
        self.assertCountEqual(["10.10.1.2", "10.10.1.3"], boot_ips[:2])

    def test_with_no_matching_subnets(self):
        # If the rack doesn't have an IP on the requested subnet, pick any IP
        # from any other subnet on the same VLAN.
        vlan = factory.make_VLAN(
            dhcp_on=False,
            primary_rack=None,
            secondary_rack=None,
        )
        subnet1 = factory.make_Subnet(vlan=vlan, cidr="10.10.0.0/24")
        factory.make_Subnet(vlan=vlan, cidr="10.10.1.0/24")
        factory.make_Subnet(vlan=vlan, cidr="10.10.2.0/24")
        factory.make_Subnet(cidr="10.20.0.0/24")
        rack1 = factory.make_rack_with_interfaces(
            eth0=["10.10.1.2/24", "10.10.2.2/24"], eth1=["10.20.0.2/24"]
        )
        vlan.dhcp_on = True
        vlan.primary_rack = rack1

        with post_commit_hooks:
            vlan.save()

        boot_ips = get_boot_rackcontroller_ips(subnet1)
        self.assertCountEqual(["10.10.1.2", "10.10.2.2"], boot_ips)

    def test_with_relay(self):
        dhcp_vlan = factory.make_VLAN(
            dhcp_on=False,
            primary_rack=None,
            secondary_rack=None,
        )
        relay_vlan = factory.make_VLAN(
            dhcp_on=False,
            primary_rack=None,
            secondary_rack=None,
        )
        factory.make_Subnet(vlan=dhcp_vlan, cidr="10.10.0.0/24")
        factory.make_Subnet(vlan=dhcp_vlan, cidr="10.10.1.0/24")
        factory.make_Subnet(cidr="10.30.0.0/24")
        relay_subnet = factory.make_Subnet(
            vlan=relay_vlan, cidr="10.20.0.0/24"
        )
        rack1 = factory.make_rack_with_interfaces(
            eth0=["10.10.0.2/24", "10.10.1.2/24"], eth1=["10.30.0.2/24"]
        )

        with post_commit_hooks:
            dhcp_vlan.dhcp_on = True
            dhcp_vlan.primary_rack = rack1
            dhcp_vlan.save()
            relay_vlan.relay_vlan = dhcp_vlan
            relay_vlan.save()

        boot_ips = get_boot_rackcontroller_ips(relay_subnet)
        self.assertCountEqual(["10.10.0.2", "10.10.1.2"], boot_ips)

    def test_with_relay_mixed_ipv4_subnet(self):
        dhcp_vlan = factory.make_VLAN(
            dhcp_on=False,
            primary_rack=None,
            secondary_rack=None,
        )
        relay_vlan = factory.make_VLAN(
            dhcp_on=False,
            primary_rack=None,
            secondary_rack=None,
        )
        factory.make_Subnet(vlan=dhcp_vlan, cidr="10.10.0.0/24")
        factory.make_Subnet(vlan=dhcp_vlan, cidr="fd12:3456:789a::/64")
        factory.make_Subnet(cidr="10.30.0.0/24")
        relay_subnet = factory.make_Subnet(
            vlan=relay_vlan, cidr="10.20.0.0/24"
        )
        rack1 = factory.make_rack_with_interfaces(
            eth0=["10.10.0.2/24", "fd12:3456:789a::2/64"],
            eth1=["10.30.0.2/24"],
        )

        with post_commit_hooks:
            dhcp_vlan.dhcp_on = True
            dhcp_vlan.primary_rack = rack1
            dhcp_vlan.save()
            relay_vlan.relay_vlan = dhcp_vlan
            relay_vlan.save()

        boot_ips = get_boot_rackcontroller_ips(relay_subnet)
        self.assertEqual(["10.10.0.2"], boot_ips)

    def test_with_relay_prefer_mixed_ipv6_subnet(self):
        dhcp_vlan = factory.make_VLAN(
            dhcp_on=False,
            primary_rack=None,
            secondary_rack=None,
        )
        relay_vlan = factory.make_VLAN(
            dhcp_on=False,
            primary_rack=None,
            secondary_rack=None,
        )
        factory.make_Subnet(vlan=dhcp_vlan, cidr="10.10.0.0/24")
        factory.make_Subnet(vlan=dhcp_vlan, cidr="fd12:3456:789a::/64")
        factory.make_Subnet(cidr="10.30.0.0/24")
        relay_subnet = factory.make_Subnet(
            vlan=relay_vlan, cidr="fda9:8765:4321::/64"
        )
        rack1 = factory.make_rack_with_interfaces(
            eth0=["10.10.0.2/24", "fd12:3456:789a::2/64"],
            eth1=["10.30.0.2/24"],
        )

        with post_commit_hooks:
            dhcp_vlan.dhcp_on = True
            dhcp_vlan.primary_rack = rack1
            dhcp_vlan.save()
            relay_vlan.relay_vlan = dhcp_vlan
            relay_vlan.save()

        boot_ips = get_boot_rackcontroller_ips(relay_subnet)
        self.assertEqual(["fd12:3456:789a::2"], boot_ips)
