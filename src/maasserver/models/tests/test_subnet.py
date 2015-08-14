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

from django.core.exceptions import ValidationError
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
from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    MatchesStructure,
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
        self.assertIPBestMatchesSubnet(subnet.get_cidr().first, subnet)
        self.assertIPBestMatchesSubnet(subnet.get_cidr().last, subnet)

    def test_get_subnets_with_ip_finds_most_specific_subnet(self):
        subnet1 = factory.make_Subnet(cidr=IPNetwork('10.0.0.0/8'))
        subnet2 = factory.make_Subnet(cidr=IPNetwork('10.0.0.0/16'))
        subnet3 = factory.make_Subnet(cidr=IPNetwork('10.0.0.0/24'))
        self.assertIPBestMatchesSubnet(subnet1.get_cidr().first, subnet3)
        self.assertIPBestMatchesSubnet(subnet1.get_cidr().last, subnet1)
        self.assertIPBestMatchesSubnet(subnet2.get_cidr().last, subnet2)
        self.assertIPBestMatchesSubnet(subnet3.get_cidr().last, subnet3)

    def test_get_subnets_with_ip_finds_matching_ipv6_subnet(self):
        subnet = factory.make_Subnet(cidr=factory.make_ipv6_network())
        self.assertIPBestMatchesSubnet(subnet.get_cidr().first, subnet)
        self.assertIPBestMatchesSubnet(subnet.get_cidr().last, subnet)

    def test_get_subnets_with_ip_finds_most_specific_ipv6_subnet(self):
        subnet1 = factory.make_Subnet(cidr=IPNetwork('2001:db8::/32'))
        subnet2 = factory.make_Subnet(cidr=IPNetwork('2001:db8::/48'))
        subnet3 = factory.make_Subnet(cidr=IPNetwork('2001:db8::/64'))
        self.assertIPBestMatchesSubnet(subnet1.get_cidr().first, subnet3)
        self.assertIPBestMatchesSubnet(subnet1.get_cidr().last, subnet1)
        self.assertIPBestMatchesSubnet(subnet2.get_cidr().last, subnet2)
        self.assertIPBestMatchesSubnet(subnet3.get_cidr().last, subnet3)

    def test_get_subnets_with_ip_returns_empty_list_if_not_found(self):
        network = factory._make_random_network()
        factory.make_Subnet()
        self.assertIPBestMatchesSubnet(network.first - 1, None)
        self.assertIPBestMatchesSubnet(network.first + 1, None)
