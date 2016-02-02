# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`StaticIPAddress` tests."""

__all__ = []


from random import randint

from django.core.exceptions import ValidationError
from django.db import transaction
from maasserver import locks
from maasserver.enum import (
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_FAMILY,
    IPADDRESS_TYPE,
)
from maasserver.exceptions import (
    StaticIPAddressExhaustion,
    StaticIPAddressOutOfRange,
    StaticIPAddressUnavailable,
)
from maasserver.models.domain import Domain
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import (
    is_serialization_failure,
    transactional,
)
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from mock import sentinel
from netaddr import (
    IPAddress,
    IPRange,
)
from testtools.matchers import (
    Contains,
    Equals,
    HasLength,
    Not,
)


class TestStaticIPAddressManager(MAASServerTestCase):

    def test_filter_by_ip_family_ipv4(self):
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=str(network_v4.cidr))
        ip_v4 = factory.pick_ip_in_network(network_v4)
        ip_v4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip_v4,
            subnet=subnet_v4)
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=str(network_v6.cidr))
        ip_v6 = factory.pick_ip_in_network(network_v6)
        ip_v6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip_v6,
            subnet=subnet_v6)
        self.assertItemsEqual(
            [ip_v4],
            StaticIPAddress.objects.filter_by_ip_family(IPADDRESS_FAMILY.IPv4))

    def test_filter_by_ip_family_ipv6(self):
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=str(network_v4.cidr))
        ip_v4 = factory.pick_ip_in_network(network_v4)
        ip_v4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip_v4,
            subnet=subnet_v4)
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=str(network_v6.cidr))
        ip_v6 = factory.pick_ip_in_network(network_v6)
        ip_v6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip_v6,
            subnet=subnet_v6)
        self.assertItemsEqual(
            [ip_v6],
            StaticIPAddress.objects.filter_by_ip_family(IPADDRESS_FAMILY.IPv6))

    def test_filter_by_subnet_cidr_family_ipv4(self):
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=str(network_v4.cidr))
        ip_v4 = factory.pick_ip_in_network(network_v4)
        ip_v4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip_v4,
            subnet=subnet_v4)
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=str(network_v6.cidr))
        ip_v6 = factory.pick_ip_in_network(network_v6)
        ip_v6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip_v6,
            subnet=subnet_v6)
        self.assertItemsEqual(
            [ip_v4],
            StaticIPAddress.objects.filter_by_subnet_cidr_family(
                IPADDRESS_FAMILY.IPv4))

    def test_filter_by_subnet_cidr_family_ipv6(self):
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=str(network_v4.cidr))
        ip_v4 = factory.pick_ip_in_network(network_v4)
        ip_v4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip_v4,
            subnet=subnet_v4)
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=str(network_v6.cidr))
        ip_v6 = factory.pick_ip_in_network(network_v6)
        ip_v6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip_v6,
            subnet=subnet_v6)
        self.assertItemsEqual(
            [ip_v6],
            StaticIPAddress.objects.filter_by_subnet_cidr_family(
                IPADDRESS_FAMILY.IPv6))


class TestStaticIPAddressManagerTrasactional(MAASTransactionServerTestCase):
    '''The following TestStaticIPAddressManager tests require
        MAASTransactionServerTestCase, and thus have been separated
        from the TestStaticIPAddressManager above.
    '''

    def make_ip_ranges(self, network=None):
        if network is None:
            network = factory.make_ip4_or_6_network()
        middle = network.size // 2
        dynamic_range = IPRange(network.first, network[middle])
        static_range = IPRange(network[middle + 1], network.last)
        return (
            network,
            str(IPAddress(static_range.first)),
            str(IPAddress(static_range.last)),
            str(IPAddress(dynamic_range.first)),
            str(IPAddress(dynamic_range.last)),
        )

    @transactional
    def test_allocate_new_returns_ip_in_correct_range(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        ipaddress = StaticIPAddress.objects.allocate_new(
            network, static_low, static_high, dynamic_low, dynamic_high)
        self.assertIsInstance(ipaddress, StaticIPAddress)
        iprange = IPRange(static_low, static_high)
        self.assertIn(IPAddress(ipaddress.ip), iprange)

    @transactional
    def test_allocate_new_allocates_IPv6_address(self):
        network = factory.make_ipv6_network()
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges(network))
        ipaddress = StaticIPAddress.objects.allocate_new(
            network, static_low, static_high, dynamic_low, dynamic_high)
        self.assertIsInstance(ipaddress, StaticIPAddress)
        self.assertIn(
            IPAddress(ipaddress.ip), IPRange(static_low, static_high))

    @transactional
    def test_allocate_new_sets_user(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        user = factory.make_User()
        ipaddress = StaticIPAddress.objects.allocate_new(
            network, static_low, static_high, dynamic_low, dynamic_high,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=user)
        self.assertEqual(user, ipaddress.user)

    @transactional
    def test_allocate_new_with_user_disallows_wrong_alloc_types(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        user = factory.make_User()
        alloc_type = factory.pick_enum(
            IPADDRESS_TYPE, but_not=[
                IPADDRESS_TYPE.DHCP,
                IPADDRESS_TYPE.DISCOVERED,
                IPADDRESS_TYPE.USER_RESERVED,
            ])
        self.assertRaises(
            AssertionError, StaticIPAddress.objects.allocate_new, network,
            static_low, static_high, dynamic_low, dynamic_high,
            user=user, alloc_type=alloc_type)

    @transactional
    def test_allocate_new_with_reserved_type_requires_a_user(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        self.assertRaises(
            AssertionError, StaticIPAddress.objects.allocate_new, network,
            static_low, static_high, dynamic_low, dynamic_high,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED)

    @transactional
    def test_allocate_new_compares_by_IP_not_alphabetically(self):
        # Django has a bug that casts IP addresses with HOST(), which
        # results in alphabetical comparisons of strings instead of IP
        # addresses.  See https://bugs.launchpad.net/maas/+bug/1338452
        network = "10.0.0.0/8"
        static_low = "10.0.0.98"
        static_high = "10.0.0.100"
        dynamic_low = "10.0.0.101"
        dynamic_high = "10.0.0.105"
        subnet = factory.make_Subnet(cidr=network)
        factory.make_StaticIPAddress("10.0.0.99", subnet=subnet)
        ipaddress = StaticIPAddress.objects.allocate_new(
            network, static_low, static_high, dynamic_low, dynamic_high,
            subnet=subnet)
        self.assertEqual(ipaddress.ip, "10.0.0.98")

    @transactional
    def test_allocate_new_returns_requested_IP_if_available(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        requested_address = str(IPAddress(static_low) + 1)
        ipaddress = StaticIPAddress.objects.allocate_new(
            network, static_low, static_high, dynamic_low, dynamic_high,
            factory.pick_enum(
                IPADDRESS_TYPE, but_not=[
                    IPADDRESS_TYPE.DHCP,
                    IPADDRESS_TYPE.DISCOVERED,
                    IPADDRESS_TYPE.USER_RESERVED,
                ]),
            requested_address=requested_address)
        self.assertEqual(requested_address.format(), ipaddress.ip)

    @transactional
    def test_allocate_new_raises_when_requested_IP_unavailable(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        requested_address = StaticIPAddress.objects.allocate_new(
            network, static_low, static_high, dynamic_low, dynamic_high,
            factory.pick_enum(
                IPADDRESS_TYPE, but_not=[
                    IPADDRESS_TYPE.DHCP,
                    IPADDRESS_TYPE.DISCOVERED,
                    IPADDRESS_TYPE.USER_RESERVED,
                ])).ip
        self.assertRaises(
            StaticIPAddressUnavailable, StaticIPAddress.objects.allocate_new,
            network, static_low, static_high, dynamic_low, dynamic_high,
            requested_address=requested_address)

    @transactional
    def test_allocate_new_raises_serialization_error_if_ip_taken(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        # Simulate a "IP already taken" error.
        mock_attempt_allocation = self.patch(
            StaticIPAddress.objects, '_attempt_allocation')
        mock_attempt_allocation.side_effect = StaticIPAddressUnavailable()

        error = self.assertRaises(
            Exception, StaticIPAddress.objects.allocate_new,
            network, static_low, static_high, dynamic_low, dynamic_high)
        self.assertTrue(is_serialization_failure(error))

    @transactional
    def test_allocate_new_does_not_use_lock_for_requested_ip(self):
        # When requesting a specific IP address, there's no need to
        # acquire the lock.
        lock = self.patch(locks, 'staticip_acquire')
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        requested_address = str(IPAddress(static_low) + 1)
        ipaddress = StaticIPAddress.objects.allocate_new(
            network, static_low, static_high, dynamic_low, dynamic_high,
            requested_address=requested_address)
        self.assertIsInstance(ipaddress, StaticIPAddress)
        self.assertThat(lock.__enter__, MockNotCalled())

    @transactional
    def test_allocate_new_raises_when_requested_IP_out_of_network(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        other_network = factory.make_ipv4_network(but_not=network)
        requested_address = factory.pick_ip_in_network(other_network)
        e = self.assertRaises(
            StaticIPAddressOutOfRange, StaticIPAddress.objects.allocate_new,
            network, static_low, static_high, dynamic_low, dynamic_high,
            factory.pick_enum(
                IPADDRESS_TYPE, but_not=[
                    IPADDRESS_TYPE.DHCP,
                    IPADDRESS_TYPE.DISCOVERED,
                    IPADDRESS_TYPE.USER_RESERVED,
                ]),
            requested_address=requested_address)
        self.assertEqual(
            "%s is not inside the network %s" % (
                requested_address, network),
            str(e))

    @transactional
    def test_allocate_new_raises_when_requested_IP_in_dynamic_range(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        requested_address = dynamic_low
        e = self.assertRaises(
            StaticIPAddressOutOfRange, StaticIPAddress.objects.allocate_new,
            network, static_low, static_high, dynamic_low, dynamic_high,
            factory.pick_enum(
                IPADDRESS_TYPE, but_not=[
                    IPADDRESS_TYPE.DHCP,
                    IPADDRESS_TYPE.DISCOVERED,
                    IPADDRESS_TYPE.USER_RESERVED,
                ]),
            requested_address=requested_address)
        self.assertEqual(
            "%s is inside the dynamic range %s to %s" % (
                requested_address, dynamic_low, dynamic_high),
            str(e))

    @transactional
    def test_allocate_new_raises_when_alloc_type_is_None(self):
        error = self.assertRaises(
            ValueError, StaticIPAddress.objects.allocate_new,
            sentinel.network, sentinel.static_range_low,
            sentinel.static_range_low, sentinel.dynamic_range_low,
            sentinel.dynamic_range_high, alloc_type=None)
        self.assertEqual(
            "IP address type None is not allowed to use allocate_new.",
            str(error))

    @transactional
    def test_allocate_new_raises_when_alloc_type_is_not_allowed(self):
        error = self.assertRaises(
            ValueError, StaticIPAddress.objects.allocate_new,
            sentinel.network, sentinel.static_range_low,
            sentinel.static_range_low, sentinel.dynamic_range_low,
            sentinel.dynamic_range_high, alloc_type=IPADDRESS_TYPE.DHCP)
        self.assertEqual(
            "IP address type 5 is not allowed to use allocate_new.",
            str(error))

    @transactional
    def test_allocate_new_uses_staticip_acquire_lock(self):
        lock = self.patch(locks, 'staticip_acquire')
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        ipaddress = StaticIPAddress.objects.allocate_new(
            network, static_low, static_high, dynamic_low, dynamic_high)
        self.assertIsInstance(ipaddress, StaticIPAddress)
        self.assertThat(lock.__enter__, MockCalledOnceWith())
        self.assertThat(
            lock.__exit__, MockCalledOnceWith(None, None, None))

    def test_allocate_new_raises_when_addresses_exhausted(self):
        network = "192.168.230.0/24"
        static_low = static_high = "192.168.230.1"
        dynamic_low = dynamic_high = "192.168.230.2"
        subnet = factory.make_Subnet(cidr=network)
        with transaction.atomic():
            StaticIPAddress.objects.allocate_new(
                network, static_low, static_high, dynamic_low, dynamic_high,
                subnet=subnet)
        with transaction.atomic():
            e = self.assertRaises(
                StaticIPAddressExhaustion,
                StaticIPAddress.objects.allocate_new,
                network, static_low, static_high, dynamic_low, dynamic_high,
                subnet=subnet)
        self.assertEqual(
            "No more IPs available in range %s-%s" % (static_low, static_high),
            str(e))


class TestStaticIPAddressManagerMapping(MAASServerTestCase):
    """Tests for get_hostname_ip_mapping()."""

    def test_get_hostname_ip_mapping_returns_mapping(self):
        domain = Domain.objects.get_default_domain()
        expected_mapping = {}
        for _ in range(3):
            node = factory.make_Node(interface=True, disable_ipv4=False)
            boot_interface = node.get_boot_interface()
            subnet = factory.make_Subnet()
            staticip = factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=factory.pick_ip_in_Subnet(subnet),
                subnet=subnet, interface=boot_interface)
            full_hostname = "%s.%s" % (node.hostname, domain.name)
            expected_mapping[full_hostname] = (30, [staticip.ip])
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(domain)
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_returns_fqdn(self):
        hostname = factory.make_name('hostname')
        domainname = factory.make_name('domain')
        factory.make_Domain(name=domainname)
        full_hostname = "%s.%s" % (hostname, domainname)
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            interface=True, hostname=full_hostname,
            subnet=subnet, disable_ipv4=False)
        boot_interface = node.get_boot_interface()
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet, interface=boot_interface)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(subnet)
        self.assertEqual({full_hostname: (30, [staticip.ip])}, mapping)

    def test_get_hostname_ip_mapping_picks_mac_with_static_address(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'), disable_ipv4=False)
        boot_interface = node.get_boot_interface()
        subnet = boot_interface.ip_addresses.first().subnet
        nic2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node,
            vlan=boot_interface.vlan)
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, interface=nic2, subnet=subnet)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        self.assertEqual({node.fqdn: (30, [staticip.ip])}, mapping)

    def test_get_hostname_ip_mapping_considers_given_domain(self):
        domain = factory.make_Domain()
        factory.make_Node_with_Interface_on_Subnet(domain=domain)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            factory.make_Domain())
        self.assertEqual({}, mapping)

    def test_get_hostname_ip_mapping_picks_oldest_nic_with_sticky_ip(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr))
        node = factory.make_Node(
            interface=True, hostname=factory.make_name('host'),
            disable_ipv4=False)
        boot_interface = node.get_boot_interface()
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet, interface=boot_interface)
        newer_nic = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=newer_nic)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        self.assertEqual({node.fqdn: (30, [staticip.ip])}, mapping)

    def test_get_hostname_ip_mapping_picks_sticky_over_auto(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr))
        node = factory.make_Node(
            interface=True, hostname=factory.make_name('host'),
            disable_ipv4=False)
        boot_interface = node.get_boot_interface()
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet, interface=boot_interface)
        nic = node.get_boot_interface()
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, interface=nic)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        self.assertEqual({node.fqdn: (30, [staticip.ip])}, mapping)

    def test_get_hostname_ip_mapping_combines_IPv4_and_IPv6_addresses(self):
        node = factory.make_Node(interface=True, disable_ipv4=False)
        interface = node.get_boot_interface()
        ipv4_network = factory.make_ipv4_network()
        ipv4_subnet = factory.make_Subnet(cidr=ipv4_network)
        ipv4_address = factory.make_StaticIPAddress(
            interface=interface,
            ip=factory.pick_ip_in_network(ipv4_network), subnet=ipv4_subnet)
        ipv6_network = factory.make_ipv6_network()
        ipv6_subnet = factory.make_Subnet(cidr=ipv6_network)
        ipv6_address = factory.make_StaticIPAddress(
            interface=interface,
            ip=factory.pick_ip_in_network(ipv6_network), subnet=ipv6_subnet)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        self.assertItemsEqual(
            (30, [ipv4_address.ip, ipv6_address.ip]),
            mapping[node.fqdn])

    def test_get_hostname_ip_mapping_combines_MACs_for_same_node(self):
        # A node's preferred static IPv4 and IPv6 addresses may be on
        # different MACs.
        node = factory.make_Node(disable_ipv4=False)
        ipv4_network = factory.make_ipv4_network()
        ipv4_subnet = factory.make_Subnet(cidr=ipv4_network)
        ipv4_address = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            interface=factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node),
            ip=factory.pick_ip_in_network(ipv4_network), subnet=ipv4_subnet)
        ipv6_network = factory.make_ipv6_network()
        ipv6_subnet = factory.make_Subnet(cidr=ipv6_network)
        ipv6_address = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            interface=factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node),
            ip=factory.pick_ip_in_network(ipv6_network), subnet=ipv6_subnet)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        self.assertItemsEqual(
            (30, [ipv4_address.ip, ipv6_address.ip]),
            mapping[node.fqdn])

    def test_get_hostname_ip_mapping_skips_ipv4_if_disable_ipv4_set(self):
        node = factory.make_Node(interface=True, disable_ipv4=True)
        boot_interface = node.get_boot_interface()
        ipv4_network = factory.make_ipv4_network()
        ipv4_subnet = factory.make_Subnet(cidr=ipv4_network)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            interface=boot_interface,
            ip=factory.pick_ip_in_network(ipv4_network), subnet=ipv4_subnet)
        ipv6_network = factory.make_ipv6_network()
        ipv6_subnet = factory.make_Subnet(cidr=ipv6_network)
        ipv6_address = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            interface=boot_interface,
            ip=factory.pick_ip_in_network(ipv6_network), subnet=ipv6_subnet)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        self.assertEqual({node.fqdn: (30, [ipv6_address.ip])}, mapping)

    def test_get_hostname_ip_mapping_prefers_non_discovered_addresses(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr))
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'), subnet=subnet,
            disable_ipv4=False)
        iface = node.get_boot_interface()
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, interface=iface,
            subnet=subnet)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, interface=iface,
            subnet=subnet)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        self.assertEqual({node.fqdn: (30, [staticip.ip])}, mapping)

    def test_get_hostname_ip_mapping_prefers_bond_with_no_boot_interface(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr))
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'), subnet=subnet,
            disable_ipv4=False)
        node.boot_interface = None
        node.save()
        iface = node.get_boot_interface()
        iface2 = factory.make_Interface(node=node)
        iface3 = factory.make_Interface(node=node)
        bondif = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, parents=[iface2, iface3])
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface,
            subnet=subnet)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface2,
            subnet=subnet)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface3,
            subnet=subnet)
        bond_staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=bondif,
            subnet=subnet)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        self.assertEqual({node.fqdn: (30, [bond_staticip.ip])}, mapping)

    def test_get_hostname_ip_mapping_prefers_bond_with_boot_interface(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr))
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'), subnet=subnet,
            disable_ipv4=False)
        iface = node.get_boot_interface()
        iface2 = factory.make_Interface(node=node)
        bondif = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, parents=[iface, iface2])
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface,
            subnet=subnet)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface2,
            subnet=subnet)
        bond_staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=bondif,
            subnet=subnet)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        self.assertEqual({node.fqdn: (30, [bond_staticip.ip])}, mapping)

    def test_get_hostname_ip_mapping_ignores_bond_without_boot_interface(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr))
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'), subnet=subnet,
            disable_ipv4=False)
        iface = node.get_boot_interface()
        iface2 = factory.make_Interface(node=node)
        iface3 = factory.make_Interface(node=node)
        bondif = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, parents=[iface2, iface3])
        boot_staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface,
            subnet=subnet)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface2,
            subnet=subnet)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface3,
            subnet=subnet)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=bondif,
            subnet=subnet)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        self.assertEqual({node.fqdn: (30, [boot_staticip.ip])}, mapping)

    def test_get_hostname_ip_mapping_prefers_boot_interface(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr))
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'), subnet=subnet,
            disable_ipv4=False)
        iface = node.get_boot_interface()
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface,
            subnet=subnet)
        new_boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        node.boot_interface = new_boot_interface
        node.save()
        # IP address should be selected over the other physical IP address.
        boot_sip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=new_boot_interface,
            subnet=subnet)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        self.assertEqual({node.fqdn: (30, [boot_sip.ip])}, mapping)

    def test_get_hostname_ip_mapping_prefers_boot_interface_to_alias(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr))
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'), subnet=subnet,
            disable_ipv4=False)
        iface = node.get_boot_interface()
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface,
            subnet=subnet)
        new_boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        node.boot_interface = new_boot_interface
        node.save()
        # IP address should be selected over the other STICKY IP address.
        boot_sip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, interface=new_boot_interface,
            subnet=subnet)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        self.assertEqual({node.fqdn: (30, [boot_sip.ip])}, mapping)

    def test_get_hostname_ip_mapping_prefers_physical_interfaces_to_vlan(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr))
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'), subnet=subnet,
            disable_ipv4=False)
        iface = node.get_boot_interface()
        vlanif = factory.make_Interface(
            INTERFACE_TYPE.VLAN, node=node, parents=[iface])
        phy_staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface,
            subnet=subnet)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=vlanif,
            subnet=subnet)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        self.assertEqual({node.fqdn: (30, [phy_staticip.ip])}, mapping)


class TestStaticIPAddress(MAASServerTestCase):

    def test_repr_with_valid_type(self):
        # Using USER_RESERVED here because it doesn't validate the Subnet.
        actual = "%s" % factory.make_StaticIPAddress(
            ip="10.0.0.1", alloc_type=IPADDRESS_TYPE.USER_RESERVED)
        self.assertEqual("10.0.0.1:type=USER_RESERVED", actual)

    def test_repr_with_invalid_type(self):
        actual = "%s" % factory.make_StaticIPAddress(
            ip="10.0.0.1", alloc_type=99999, subnet=factory.make_Subnet(
                cidr="10.0.0.0/8"))
        self.assertEqual("10.0.0.1:type=99999", actual)

    def test_stores_to_database(self):
        ipaddress = factory.make_StaticIPAddress()
        self.assertEqual([ipaddress], list(StaticIPAddress.objects.all()))

    def test_invalid_address_raises_validation_error(self):
        ip = StaticIPAddress(ip='256.0.0.0.0')
        self.assertRaises(ValidationError, ip.full_clean)

    def test_get_interface_link_type_returns_AUTO_for_AUTO(self):
        ip = StaticIPAddress(alloc_type=IPADDRESS_TYPE.AUTO)
        self.assertEqual(
            INTERFACE_LINK_TYPE.AUTO, ip.get_interface_link_type())

    def test_get_interface_link_type_returns_DHCP_for_DHCP(self):
        ip = StaticIPAddress(alloc_type=IPADDRESS_TYPE.DHCP)
        self.assertEqual(
            INTERFACE_LINK_TYPE.DHCP, ip.get_interface_link_type())

    def test_get_interface_link_type_returns_STATIC_for_USER_RESERVED(self):
        ip = StaticIPAddress(alloc_type=IPADDRESS_TYPE.USER_RESERVED)
        self.assertEqual(
            INTERFACE_LINK_TYPE.STATIC, ip.get_interface_link_type())

    def test_get_interface_link_type_returns_STATIC_for_STICKY_with_ip(self):
        ip = StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=factory.make_ipv4_address())
        self.assertEqual(
            INTERFACE_LINK_TYPE.STATIC, ip.get_interface_link_type())

    def test_get_interface_link_type_returns_LINK_UP_for_STICKY_no_ip(self):
        ip = StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip="")
        self.assertEqual(
            INTERFACE_LINK_TYPE.LINK_UP, ip.get_interface_link_type())

    def test_deallocate_removes_object(self):
        ipaddress = factory.make_StaticIPAddress()
        ipaddress.deallocate()
        self.assertEqual([], list(StaticIPAddress.objects.all()))

    def test_deallocate_ignores_other_objects(self):
        ipaddress = factory.make_StaticIPAddress()
        ipaddress2 = factory.make_StaticIPAddress()
        ipaddress.deallocate()
        self.assertEqual([ipaddress2], list(StaticIPAddress.objects.all()))


class TestUserReservedStaticIPAddress(MAASServerTestCase):

    def test_user_reserved_addresses_have_default_hostnames(self):
        num_ips = randint(3, 5)
        ips = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.USER_RESERVED)
            for _ in range(num_ips)
        ]
        mappings = StaticIPAddress.objects._get_user_reserved_mappings({})
        self.expectThat(mappings, HasLength(len(ips)))

    def test_user_reserved_addresses_included_in_get_hostname_ip_mapping(self):
        num_ips = randint(3, 5)
        domain = factory.make_Domain()
        ips = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.USER_RESERVED)
            for _ in range(num_ips)
        ]
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain)
        self.expectThat(mappings, HasLength(len(ips)))

    def test_user_reserved_addresses_included_in_all_nodegroups(self):
        num_ips = randint(3, 5)
        domain1 = factory.make_Domain()
        domain2 = factory.make_Domain()
        ips = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.USER_RESERVED)
            for _ in range(num_ips)
        ]
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain1)
        self.expectThat(mappings, HasLength(len(ips)))
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain2)
        self.expectThat(mappings, HasLength(len(ips)))


class TestRenderJSON(MAASServerTestCase):

    def test__excludes_username_and_node_summary_by_default(self):
        ip = factory.make_StaticIPAddress(
            ip=factory.make_ipv4_address(),
            alloc_type=IPADDRESS_TYPE.USER_RESERVED)
        json = ip.render_json()
        self.expectThat(json, Not(Contains("user")))
        self.expectThat(json, Not(Contains("node_summary")))

    def test__includes_username_if_requested(self):
        user = factory.make_User()
        ip = factory.make_StaticIPAddress(
            ip=factory.make_ipv4_address(), user=user,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED)
        json = ip.render_json(with_username=True)
        self.expectThat(json, Contains("user"))
        self.expectThat(json, Not(Contains("node_summary")))
        self.expectThat(json["user"], Equals(user.username))

    def test__includes_node_summary_if_requested(self):
        user = factory.make_User()
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            disable_ipv4=False, subnet=subnet)
        ip = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet), user=user,
            interface=node.get_boot_interface())
        json = ip.render_json(with_node_summary=True)
        self.expectThat(json, Not(Contains("user")))
        self.expectThat(json, Contains("node_summary"))

    def test__data_is_accurate(self):
        user = factory.make_User()
        hostname = factory.make_name('hostname')
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            disable_ipv4=False, subnet=subnet, hostname=hostname)
        ip = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet), user=user,
            interface=node.get_boot_interface())
        json = ip.render_json(with_username=True, with_node_summary=True)
        self.expectThat(json["user"], Equals(user.username))
        self.assertThat(json, Contains("node_summary"))
        node_summary = json["node_summary"]
        self.expectThat(node_summary["system_id"], Equals(node.system_id))
        self.expectThat(node_summary["node_type"], Equals(node.node_type))
