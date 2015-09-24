# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Subnet model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


import random

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from maasserver.enum import (
    IPADDRESS_TYPE,
    NODE_PERMISSION,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
)
from maasserver.models.subnet import (
    create_cidr,
    Subnet,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from netaddr import (
    AddrFormatError,
    IPAddress,
    IPNetwork,
)
from provisioningserver.utils.network import inet_ntop
from testtools import ExpectedException
from testtools.matchers import (
    Contains,
    Equals,
    HasLength,
    MatchesStructure,
    Not,
)


class CreateCidrTest(MAASServerTestCase):

    def test_creates_cidr_from_ipv4_strings(self):
        cidr = create_cidr("169.254.0.0", "255.255.255.0")
        self.assertEqual("169.254.0.0/24", cidr)

    def test_creates_cidr_from_ipv4_prefixlen(self):
        cidr = create_cidr("169.254.0.0", 24)
        self.assertEqual("169.254.0.0/24", cidr)

    def test_raises_for_invalid_ipv4_prefixlen(self):
        with ExpectedException(AddrFormatError):
            create_cidr("169.254.0.0", 33)

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
        with ExpectedException(AddrFormatError):
            create_cidr("2001:67c:1360:8c01::", 129)

    def test_accepts_ipaddresses(self):
        cidr = create_cidr(
            IPAddress("169.254.0.1"), IPAddress("255.255.255.0"))
        self.assertEqual("169.254.0.0/24", cidr)

    def test_accepts_ipnetwork(self):
        cidr = create_cidr(IPNetwork("169.254.0.1/24"))
        self.assertEqual("169.254.0.0/24", cidr)

    def test_accepts_ipnetwork_with_subnet_override(self):
        cidr = create_cidr(IPNetwork("169.254.0.1/24"), 16)
        self.assertEqual("169.254.0.0/16", cidr)


class TestSubnetManagerGetSubnetOr404(MAASServerTestCase):

    def test__user_view_returns_subnet(self):
        user = factory.make_User()
        subnet = factory.make_Subnet()
        self.assertEquals(
            subnet,
            Subnet.objects.get_subnet_or_404(
                subnet.id, user, NODE_PERMISSION.VIEW))

    def test__user_edit_raises_PermissionError(self):
        user = factory.make_User()
        subnet = factory.make_Subnet()
        self.assertRaises(
            PermissionDenied,
            Subnet.objects.get_subnet_or_404,
            subnet.id, user, NODE_PERMISSION.EDIT)

    def test__user_admin_raises_PermissionError(self):
        user = factory.make_User()
        subnet = factory.make_Subnet()
        self.assertRaises(
            PermissionDenied,
            Subnet.objects.get_subnet_or_404,
            subnet.id, user, NODE_PERMISSION.ADMIN)

    def test__admin_view_returns_subnet(self):
        admin = factory.make_admin()
        subnet = factory.make_Subnet()
        self.assertEquals(
            subnet,
            Subnet.objects.get_subnet_or_404(
                subnet.id, admin, NODE_PERMISSION.VIEW))

    def test__admin_edit_returns_subnet(self):
        admin = factory.make_admin()
        subnet = factory.make_Subnet()
        self.assertEquals(
            subnet,
            Subnet.objects.get_subnet_or_404(
                subnet.id, admin, NODE_PERMISSION.EDIT))

    def test__admin_admin_returns_subnet(self):
        admin = factory.make_admin()
        subnet = factory.make_Subnet()
        self.assertEquals(
            subnet,
            Subnet.objects.get_subnet_or_404(
                subnet.id, admin, NODE_PERMISSION.ADMIN))


class SubnetTest(MAASServerTestCase):

    def assertIPBestMatchesSubnet(self, ip, expected):
        subnets = Subnet.objects.get_subnets_with_ip(IPAddress(ip))
        for tmp in subnets:
            subnet = tmp
            break
        else:
            subnet = None
        self.assertThat(subnet, Equals(expected))

    def test_creates_subnet(self):
        name = factory.make_name('name')
        vlan = factory.make_VLAN()
        space = factory.make_Space()
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network.cidr)
        gateway_ip = factory.pick_ip_in_network(network)
        dns_servers = [
            factory.make_ip_address()
            for _ in range(random.randint(1, 3))]
        subnet = Subnet(
            name=name, vlan=vlan, cidr=cidr, gateway_ip=gateway_ip,
            space=space, dns_servers=dns_servers)
        subnet.save()
        subnet_from_db = Subnet.objects.get(name=name)
        self.assertThat(subnet_from_db, MatchesStructure.byEquality(
            name=name, vlan=vlan, cidr=cidr, space=space,
            gateway_ip=gateway_ip, dns_servers=dns_servers))

    def test_validates_gateway_ip(self):
        error = self.assertRaises(
            ValidationError, factory.make_Subnet,
            cidr=create_cidr('192.168.0.0', 24), gateway_ip='10.0.0.0')
        self.assertEqual(
            {'gateway_ip': ["Gateway IP must be within CIDR range."]},
            error.message_dict)

    def test_create_from_cidr_creates_subnet(self):
        vlan = factory.make_VLAN()
        cidr = unicode(factory.make_ip4_or_6_network().cidr)
        space = factory.make_Space()
        name = "subnet-" + cidr
        subnet = Subnet.objects.create_from_cidr(cidr, vlan, space)
        self.assertThat(subnet, MatchesStructure.byEquality(
            name=name, vlan=vlan, cidr=cidr, space=space,
            gateway_ip=None, dns_servers=[]))

    def test_get_subnets_with_ip_finds_matching_subnet(self):
        subnet = factory.make_Subnet(cidr=factory.make_ipv4_network())
        self.assertIPBestMatchesSubnet(subnet.get_ipnetwork().first, subnet)
        self.assertIPBestMatchesSubnet(subnet.get_ipnetwork().last, subnet)

    def test_get_subnets_with_ip_finds_most_specific_subnet(self):
        subnet1 = factory.make_Subnet(cidr=IPNetwork('10.0.0.0/8'))
        subnet2 = factory.make_Subnet(cidr=IPNetwork('10.0.0.0/16'))
        subnet3 = factory.make_Subnet(cidr=IPNetwork('10.0.0.0/24'))
        self.assertIPBestMatchesSubnet(subnet1.get_ipnetwork().first, subnet3)
        self.assertIPBestMatchesSubnet(subnet1.get_ipnetwork().last, subnet1)
        self.assertIPBestMatchesSubnet(subnet2.get_ipnetwork().last, subnet2)
        self.assertIPBestMatchesSubnet(subnet3.get_ipnetwork().last, subnet3)

    def test_get_subnets_with_ip_finds_matching_ipv6_subnet(self):
        subnet = factory.make_Subnet(cidr=factory.make_ipv6_network())
        self.assertIPBestMatchesSubnet(subnet.get_ipnetwork().first, subnet)
        self.assertIPBestMatchesSubnet(subnet.get_ipnetwork().last, subnet)

    def test_get_subnets_with_ip_finds_most_specific_ipv6_subnet(self):
        subnet1 = factory.make_Subnet(cidr=IPNetwork('2001:db8::/32'))
        subnet2 = factory.make_Subnet(cidr=IPNetwork('2001:db8::/48'))
        subnet3 = factory.make_Subnet(cidr=IPNetwork('2001:db8::/64'))
        self.assertIPBestMatchesSubnet(subnet1.get_ipnetwork().first, subnet3)
        self.assertIPBestMatchesSubnet(subnet1.get_ipnetwork().last, subnet1)
        self.assertIPBestMatchesSubnet(subnet2.get_ipnetwork().last, subnet2)
        self.assertIPBestMatchesSubnet(subnet3.get_ipnetwork().last, subnet3)

    def test_get_subnets_with_ip_returns_empty_list_if_not_found(self):
        network = factory._make_random_network()
        factory.make_Subnet()
        self.assertIPBestMatchesSubnet(network.first - 1, None)
        self.assertIPBestMatchesSubnet(network.first + 1, None)

    def test_get_managed_cluster_interface(self):
        subnet = factory.make_Subnet()
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        ngi = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        self.assertEquals(ngi, subnet.get_managed_cluster_interface())


class SubnetIPRangeTest(MAASServerTestCase):

    def test__finds_used_ranges(self):
        ng = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        subnet = factory.make_Subnet(
            gateway_ip='', dns_servers=[], host_bits=8)
        net = subnet.get_ipnetwork()
        free_ip_1 = inet_ntop(net.first + 1)
        cluster_ip = inet_ntop(net.first + 2)
        free_ip_2 = inet_ntop(net.first + 3)
        free_ip_3 = inet_ntop(net.first + 9)
        dynamic_range_low = inet_ntop(net.first + 10)
        dynamic_range_high = inet_ntop(net.first + 49)
        static_range_low = inet_ntop(net.first + 50)
        static_range_high = inet_ntop(net.first + 99)
        free_ip_4 = inet_ntop(net.first + 100)
        factory.make_NodeGroupInterface(
            ng, subnet=subnet, ip=cluster_ip,
            ip_range_low=dynamic_range_low,
            ip_range_high=dynamic_range_high,
            static_ip_range_low=static_range_low,
            static_ip_range_high=static_range_high)
        s = subnet.get_ipranges_in_use()
        self.assertThat(s, Contains(cluster_ip))
        self.assertThat(s, Contains(dynamic_range_low))
        self.assertThat(s, Contains(dynamic_range_high))
        self.assertThat(s, Not(Contains(static_range_low)))
        self.assertThat(s, Not(Contains(static_range_high)))
        self.assertThat(s, Not(Contains(free_ip_1)))
        self.assertThat(s, Not(Contains(free_ip_2)))
        self.assertThat(s, Not(Contains(free_ip_3)))
        self.assertThat(s, Not(Contains(free_ip_4)))
        self.assertThat(s[cluster_ip].purpose, Contains('cluster-ip'))
        self.assertThat(
            s[dynamic_range_low].purpose, Contains('dynamic-range'))

    def test__finds_used_ranges_includes_allocated_ip(self):
        ng = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        subnet = factory.make_Subnet(
            gateway_ip='', dns_servers=[], host_bits=8)
        net = subnet.get_ipnetwork()
        cluster_ip = inet_ntop(net.first + 2)
        dynamic_range_low = inet_ntop(net.first + 10)
        dynamic_range_high = inet_ntop(net.first + 49)
        static_range_low = inet_ntop(net.first + 50)
        static_range_high = inet_ntop(net.first + 99)
        factory.make_NodeGroupInterface(
            ng, subnet=subnet, ip=cluster_ip,
            ip_range_low=dynamic_range_low,
            ip_range_high=dynamic_range_high,
            static_ip_range_low=static_range_low,
            static_ip_range_high=static_range_high)
        factory.make_StaticIPAddress(
            ip=static_range_low, alloc_type=IPADDRESS_TYPE.USER_RESERVED)
        s = subnet.get_ipranges_in_use()
        self.assertThat(s, Contains(static_range_low))
        self.assertThat(s, Not(Contains(static_range_high)))

    def test__get_ipranges_not_in_use_includes_free_ips(self):
        ng = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        subnet = factory.make_Subnet(
            gateway_ip='', dns_servers=[], host_bits=8)
        net = subnet.get_ipnetwork()
        cluster_ip = inet_ntop(net.first + 2)
        dynamic_range_low = inet_ntop(net.first + 10)
        dynamic_range_high = inet_ntop(net.first + 49)
        static_range_low = inet_ntop(net.first + 50)
        static_range_high = inet_ntop(net.first + 99)
        factory.make_NodeGroupInterface(
            ng, subnet=subnet, ip=cluster_ip,
            ip_range_low=dynamic_range_low,
            ip_range_high=dynamic_range_high,
            static_ip_range_low=static_range_low,
            static_ip_range_high=static_range_high)
        factory.make_StaticIPAddress(
            ip=static_range_low, alloc_type=IPADDRESS_TYPE.USER_RESERVED)
        s = subnet.get_ipranges_not_in_use()
        self.assertThat(s, Not(Contains(static_range_low)))
        self.assertThat(s, Contains(static_range_high))

    def test__get_iprange_usage_includes_used_and_unused_ips(self):
        ng = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        subnet = factory.make_Subnet(
            gateway_ip='', dns_servers=[], host_bits=8)
        net = subnet.get_ipnetwork()
        cluster_ip = inet_ntop(net.first + 2)
        dynamic_range_low = inet_ntop(net.first + 10)
        dynamic_range_high = inet_ntop(net.first + 49)
        static_range_low = inet_ntop(net.first + 50)
        static_range_high = inet_ntop(net.first + 99)
        factory.make_NodeGroupInterface(
            ng, subnet=subnet, ip=cluster_ip,
            ip_range_low=dynamic_range_low,
            ip_range_high=dynamic_range_high,
            static_ip_range_low=static_range_low,
            static_ip_range_high=static_range_high)
        factory.make_StaticIPAddress(
            ip=static_range_low, alloc_type=IPADDRESS_TYPE.USER_RESERVED)
        s = subnet.get_iprange_usage()
        self.assertThat(s, Contains(static_range_low))
        self.assertThat(s, Contains(static_range_high))


class TestRenderJSONForRelatedIPs(MAASServerTestCase):

    def test__sorts_by_ip_address(self):
        subnet = factory.make_Subnet(cidr='10.0.0.0/24')
        factory.make_StaticIPAddress(
            ip='10.0.0.2', alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            subnet=subnet)
        factory.make_StaticIPAddress(
            ip='10.0.0.154', alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            subnet=subnet)
        factory.make_StaticIPAddress(
            ip='10.0.0.1', alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            subnet=subnet)
        json = subnet.render_json_for_related_ips()
        self.expectThat(json[0]["ip"], Equals('10.0.0.1'))
        self.expectThat(json[1]["ip"], Equals('10.0.0.2'))
        self.expectThat(json[2]["ip"], Equals('10.0.0.154'))

    def test__returns_expected_json(self):
        subnet = factory.make_Subnet(cidr='10.0.0.0/24')
        ip = factory.make_StaticIPAddress(
            ip='10.0.0.1', alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            subnet=subnet)
        json = subnet.render_json_for_related_ips(
            with_username=True, with_node_summary=True)
        self.assertThat(type(json), Equals(list))
        self.assertThat(json[0], Equals(ip.render_json(
            with_username=True, with_node_summary=True)))

    def test__excludes_blank_addresses(self):
        subnet = factory.make_Subnet(cidr='10.0.0.0/24')
        factory.make_StaticIPAddress(
            ip=None, alloc_type=IPADDRESS_TYPE.DISCOVERED,
            subnet=subnet)
        factory.make_StaticIPAddress(
            ip='10.0.0.1', alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            subnet=subnet)
        json = subnet.render_json_for_related_ips()
        self.expectThat(json[0]["ip"], Equals('10.0.0.1'))
        self.expectThat(json, HasLength(1))
