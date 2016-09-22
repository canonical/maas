# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`StaticIPAddress` tests."""

__all__ = []

from random import (
    randint,
    shuffle,
)
from unittest import skip
from unittest.mock import sentinel

from django.core.exceptions import ValidationError
from django.db import transaction
from maasserver import locks
from maasserver.enum import (
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_FAMILY,
    IPADDRESS_TYPE,
    IPRANGE_TYPE,
)
from maasserver.exceptions import (
    StaticIPAddressExhaustion,
    StaticIPAddressOutOfRange,
    StaticIPAddressUnavailable,
)
from maasserver.models.config import Config
from maasserver.models.domain import Domain
from maasserver.models.staticipaddress import (
    HostnameIPMapping,
    StaticIPAddress,
)
from maasserver.models.subnet import Subnet
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import (
    reload_object,
    RetryTransaction,
    transactional,
)
from maasserver.websockets.base import dehydrate_datetime
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from netaddr import IPAddress
from testtools import ExpectedException
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


class TestStaticIPAddressManagerTransactional(MAASTransactionServerTestCase):
    """The following TestStaticIPAddressManager tests require
        MAASTransactionServerTestCase, and thus have been separated
        from the TestStaticIPAddressManager above.
    """

    def test_allocate_new_returns_ip_in_correct_range(self):
        with transaction.atomic():
            subnet = factory.make_managed_Subnet()
        with transaction.atomic():
            ipaddress = StaticIPAddress.objects.allocate_new(subnet)
        self.assertIsInstance(ipaddress, StaticIPAddress)
        self.assertTrue(
            subnet.is_valid_static_ip(ipaddress.ip),
            "%s: not valid for subnet with reserved IPs: %r" % (
                ipaddress.ip, subnet.get_ipranges_in_use()))

    @transactional
    def test_allocate_new_allocates_IPv6_address(self):
        subnet = factory.make_managed_ipv6_Subnet()
        ipaddress = StaticIPAddress.objects.allocate_new(subnet)
        self.assertIsInstance(ipaddress, StaticIPAddress)
        self.assertTrue(subnet.is_valid_static_ip(ipaddress.ip))

    @transactional
    def test_allocate_new_sets_user(self):
        subnet = factory.make_managed_Subnet()
        user = factory.make_User()
        ipaddress = StaticIPAddress.objects.allocate_new(
            subnet=subnet, alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=user)
        self.assertEqual(user, ipaddress.user)

    @transactional
    def test_allocate_new_with_user_disallows_wrong_alloc_types(self):
        subnet = factory.make_managed_Subnet()
        user = factory.make_User()
        alloc_type = factory.pick_enum(
            IPADDRESS_TYPE, but_not=[
                IPADDRESS_TYPE.DHCP,
                IPADDRESS_TYPE.DISCOVERED,
                IPADDRESS_TYPE.USER_RESERVED,
            ])
        with ExpectedException(AssertionError):
            StaticIPAddress.objects.allocate_new(
                subnet, user=user, alloc_type=alloc_type)

    @transactional
    def test_allocate_new_with_reserved_type_requires_a_user(self):
        subnet = factory.make_managed_Subnet()
        with ExpectedException(AssertionError):
            StaticIPAddress.objects.allocate_new(
                subnet, alloc_type=IPADDRESS_TYPE.USER_RESERVED)

    def test_allocate_new_compares_by_IP_not_alphabetically(self):
        # Django has a bug that casts IP addresses with HOST(), which
        # results in alphabetical comparisons of strings instead of IP
        # addresses.  See https://bugs.launchpad.net/maas/+bug/1338452
        with transaction.atomic():
            subnet = factory.make_Subnet(
                cidr='10.0.0.0/24', gateway_ip='10.0.0.1')
            factory.make_IPRange(subnet, '10.0.0.2', '10.0.0.97')
            factory.make_IPRange(subnet, '10.0.0.101', '10.0.0.254')
            factory.make_StaticIPAddress("10.0.0.99", subnet=subnet)
            subnet = reload_object(subnet)
        with transaction.atomic():
            ipaddress = StaticIPAddress.objects.allocate_new(subnet)
            self.assertEqual(ipaddress.ip, "10.0.0.98")

    @transactional
    def test_allocate_new_returns_requested_IP_if_available(self):
        subnet = factory.make_Subnet(cidr='10.0.0.0/24')
        ipaddress = StaticIPAddress.objects.allocate_new(
            subnet, factory.pick_enum(
                IPADDRESS_TYPE, but_not=[
                    IPADDRESS_TYPE.DHCP,
                    IPADDRESS_TYPE.DISCOVERED,
                    IPADDRESS_TYPE.USER_RESERVED,
                ]),
            requested_address='10.0.0.1')
        self.assertEqual('10.0.0.1', ipaddress.ip)

    @transactional
    def test_allocate_new_raises_when_requested_IP_unavailable(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges()
        requested_address = StaticIPAddress.objects.allocate_new(
            subnet,
            factory.pick_enum(
                IPADDRESS_TYPE, but_not=[
                    IPADDRESS_TYPE.DHCP,
                    IPADDRESS_TYPE.DISCOVERED,
                    IPADDRESS_TYPE.USER_RESERVED,
                ])).ip
        with ExpectedException(StaticIPAddressUnavailable):
            StaticIPAddress.objects.allocate_new(
                subnet, requested_address=requested_address)

    @transactional
    def test_allocate_new_requests_transaction_retry_if_ip_taken(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges()
        # Simulate a "IP already taken" error.
        mock_attempt_allocation = self.patch(
            StaticIPAddress.objects, '_attempt_allocation')
        mock_attempt_allocation.side_effect = StaticIPAddressUnavailable()
        self.assertRaises(
            RetryTransaction, StaticIPAddress.objects.allocate_new, subnet)

    @transactional
    def test_allocate_new_does_not_use_lock_for_requested_ip(self):
        # When requesting a specific IP address, there's no need to
        # acquire the lock.
        lock = self.patch(locks, 'staticip_acquire')
        subnet = factory.make_Subnet(cidr='10.0.0.0/24')
        ipaddress = StaticIPAddress.objects.allocate_new(
            subnet, requested_address='10.0.0.1')
        self.assertIsInstance(ipaddress, StaticIPAddress)
        self.assertThat(lock.__enter__, MockNotCalled())

    @transactional
    def test_allocate_new_raises_when_requested_IP_out_of_network(self):
        subnet = factory.make_Subnet(cidr='10.0.0.0/24')
        requested_address = '10.0.1.1'
        e = self.assertRaises(
            StaticIPAddressOutOfRange, StaticIPAddress.objects.allocate_new,
            subnet, factory.pick_enum(
                IPADDRESS_TYPE, but_not=[
                    IPADDRESS_TYPE.DHCP,
                    IPADDRESS_TYPE.DISCOVERED,
                    IPADDRESS_TYPE.USER_RESERVED,
                ]),
            requested_address=requested_address)
        self.assertEqual(
            "%s is not within subnet CIDR: %s" % (
                requested_address, str(subnet.get_ipnetwork())),
            str(e))

    def test_allocate_new_raises_when_requested_IP_in_dynamic_range(self):
        with transaction.atomic():
            subnet = factory.make_ipv4_Subnet_with_IPRanges()
            dynamic_range = subnet.get_dynamic_ranges().first()
            requested_address = str(IPAddress(
                dynamic_range.netaddr_iprange.first))
            dynamic_range_end = str(IPAddress(
                dynamic_range.netaddr_iprange.last))
            subnet = reload_object(subnet)
        with transaction.atomic():
            e = self.assertRaises(
                StaticIPAddressUnavailable,
                StaticIPAddress.objects.allocate_new,
                subnet, factory.pick_enum(
                    IPADDRESS_TYPE, but_not=[
                        IPADDRESS_TYPE.DHCP,
                        IPADDRESS_TYPE.DISCOVERED,
                        IPADDRESS_TYPE.USER_RESERVED,
                    ]),
                requested_address=requested_address)
            self.assertEqual(
                "%s is within the dynamic range from %s to %s" % (
                    requested_address, requested_address, dynamic_range_end),
                str(e))

    @transactional
    def test_allocate_new_raises_when_alloc_type_is_None(self):
        error = self.assertRaises(
            ValueError, StaticIPAddress.objects.allocate_new,
            sentinel.subnet, alloc_type=None)
        self.assertEqual(
            "IP address type None is not allowed to use allocate_new.",
            str(error))

    @transactional
    def test_allocate_new_raises_when_alloc_type_is_not_allowed(self):
        error = self.assertRaises(
            ValueError, StaticIPAddress.objects.allocate_new,
            sentinel.subnet, alloc_type=IPADDRESS_TYPE.DHCP)
        self.assertEqual(
            "IP address type 5 is not allowed to use allocate_new.",
            str(error))

    @transactional
    def test_allocate_new_uses_staticip_acquire_lock(self):
        lock = self.patch(locks, 'staticip_acquire')
        subnet = factory.make_ipv4_Subnet_with_IPRanges()
        ipaddress = StaticIPAddress.objects.allocate_new(subnet)
        self.assertIsInstance(ipaddress, StaticIPAddress)
        self.assertThat(lock.__enter__, MockCalledOnceWith())
        self.assertThat(
            lock.__exit__, MockCalledOnceWith(None, None, None))

    def test_allocate_new_raises_when_addresses_exhausted(self):
        network = "192.168.230.0/24"
        with transaction.atomic():
            subnet = factory.make_Subnet(cidr=network)
            factory.make_IPRange(
                subnet, '192.168.230.1', '192.168.230.254',
                type=IPRANGE_TYPE.RESERVED)
        with transaction.atomic():
            e = self.assertRaises(
                StaticIPAddressExhaustion,
                StaticIPAddress.objects.allocate_new,
                subnet)
        self.assertEqual(
            "No more IPs available in subnet: %s" % subnet.cidr,
            str(e))


class TestStaticIPAddressManagerMapping(MAASServerTestCase):
    """Tests for get_hostname_ip_mapping()."""

    def test_get_hostname_ip_mapping_returns_mapping(self):
        domain = Domain.objects.get_default_domain()
        expected_mapping = {}
        for _ in range(3):
            node = factory.make_Node(interface=True)
            boot_interface = node.get_boot_interface()
            subnet = factory.make_Subnet()
            staticip = factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=factory.pick_ip_in_Subnet(subnet),
                subnet=subnet, interface=boot_interface)
            full_hostname = "%s.%s" % (node.hostname, domain.name)
            expected_mapping[full_hostname] = HostnameIPMapping(
                node.system_id, 30, {staticip.ip}, node.node_type)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(domain)
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_returns_all_mappings_for_subnet(self):
        domain = Domain.objects.get_default_domain()
        expected_mapping = {}
        for _ in range(3):
            node = factory.make_Node(interface=True)
            boot_interface = node.get_boot_interface()
            subnet = factory.make_Subnet()
            staticip = factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=factory.pick_ip_in_Subnet(subnet),
                subnet=subnet, interface=boot_interface)
            full_hostname = "%s.%s" % (node.hostname, domain.name)
            expected_mapping[full_hostname] = HostnameIPMapping(
                node.system_id, 30, {staticip.ip}, node.node_type)
        # See also LP#1600259.  It doesn't matter what subnet is passed in, you
        # get all of them.
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            Subnet.objects.first())
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_returns_fqdn_and_other(self):
        hostname = factory.make_name('hostname')
        domainname = factory.make_name('domain')
        factory.make_Domain(name=domainname)
        full_hostname = "%s.%s" % (hostname, domainname)
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            interface=True, hostname=full_hostname, interface_count=3,
            subnet=subnet)
        boot_interface = node.get_boot_interface()
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet, interface=boot_interface)
        ifaces = node.interface_set.exclude(interface=boot_interface)
        sip2 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet, interface=ifaces[0])
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(subnet)
        self.assertEqual({
            full_hostname:
                HostnameIPMapping(
                    node.system_id, 30, {staticip.ip}, node.node_type),
            "%s.%s" % (ifaces[0].name, full_hostname):
                HostnameIPMapping(
                    node.system_id, 30, {sip2.ip}, node.node_type),
            }, mapping)

    def make_mapping(self, node, raw_ttl=False):
        if raw_ttl or node.address_ttl is not None:
            ttl = node.address_ttl
        elif node.domain.ttl is not None:
            ttl = node.domain.ttl
        else:
            ttl = Config.objects.get_config('default_dns_ttl')
        mapping = HostnameIPMapping(
            system_id=node.system_id, node_type=node.node_type, ttl=ttl)
        for ip in node.boot_interface.ip_addresses.all():
            mapping.ips.add(str(ip.ip))
        return {node.fqdn: mapping}

    def test_get_hostname_ip_mapping_inherits_ttl(self):
        # We create 2 domains, one with a ttl, one withoout.
        # Within each domain, create a node with an address_ttl, and one
        # without.
        global_ttl = randint(1, 99)
        Config.objects.set_config('default_dns_ttl', global_ttl)
        domains = [
            factory.make_Domain(),
            factory.make_Domain(ttl=randint(100, 199))]
        subnet = factory.make_Subnet(host_bits=randint(4, 15))
        for dom in domains:
            for ttl in (None, randint(200, 299)):
                node = factory.make_Node_with_Interface_on_Subnet(
                    interface=True, hostname="%s.%s" % (
                        factory.make_name('hostname'), dom.name),
                    subnet=subnet, address_ttl=ttl)
                boot_interface = node.get_boot_interface()
                factory.make_StaticIPAddress(
                    alloc_type=IPADDRESS_TYPE.STICKY,
                    ip=factory.pick_ip_in_Subnet(subnet),
                    subnet=subnet, interface=boot_interface)
            expected_mapping = {}
            for node in dom.node_set.all():
                expected_mapping.update(self.make_mapping(node))
            actual = StaticIPAddress.objects.get_hostname_ip_mapping(dom)
            self.assertItemsEqual(expected_mapping, actual)

    @skip("XXX: GavinPanella 2016-02-24 bug=1549397: Fails spuriously.")
    def test_get_hostname_ip_mapping_returns_raw_ttl(self):
        # We create 2 domains, one with a ttl, one withoout.
        # Within each domain, create a node with an address_ttl, and one
        # without.
        # We then query with raw_ttl=True, and confirm that nothing is
        # inherited.
        global_ttl = randint(1, 99)
        Config.objects.set_config('default_dns_ttl', global_ttl)
        domains = [
            factory.make_Domain(),
            factory.make_Domain(ttl=randint(100, 199))]
        subnet = factory.make_Subnet()
        for dom in domains:
            for ttl in (None, randint(200, 299)):
                node = factory.make_Node_with_Interface_on_Subnet(
                    interface=True, hostname="%s.%s" % (
                        factory.make_name('hostname'), dom.name),
                    subnet=subnet, address_ttl=ttl)
                boot_interface = node.get_boot_interface()
                factory.make_StaticIPAddress(
                    alloc_type=IPADDRESS_TYPE.STICKY,
                    ip=factory.pick_ip_in_Subnet(subnet),
                    subnet=subnet, interface=boot_interface)
            expected_mapping = {}
            for node in dom.node_set.all():
                expected_mapping.update(self.make_mapping(
                    node, raw_ttl=True))
            actual = StaticIPAddress.objects.get_hostname_ip_mapping(
                dom, raw_ttl=True)
            self.assertItemsEqual(expected_mapping, actual)

    def test_get_hostname_ip_mapping_picks_mac_with_static_address(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'))
        boot_interface = node.get_boot_interface()
        subnet = boot_interface.ip_addresses.first().subnet
        nic2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node,
            vlan=boot_interface.vlan)
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, interface=nic2, subnet=subnet)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        self.assertEqual({node.fqdn: HostnameIPMapping(
            node.system_id, 30, {staticip.ip}, node.node_type)}, mapping)

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
            interface=True, hostname=factory.make_name('host'))
        boot_interface = node.get_boot_interface()
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet, interface=boot_interface)
        newer_nic = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        newer_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet,
            interface=newer_nic)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {staticip.ip}, node.node_type),
            "%s.%s" % (newer_nic.name, node.fqdn): HostnameIPMapping(
                node.system_id, 30, {newer_ip.ip}, node.node_type)}
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_picks_sticky_over_auto(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr))
        node = factory.make_Node(
            interface=True, hostname=factory.make_name('host'))
        boot_interface = node.get_boot_interface()
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet,
            interface=boot_interface)
        nic = node.get_boot_interface()  # equals boot_interface
        auto_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, subnet=subnet, interface=nic)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {staticip.ip}, node.node_type),
            "%s.%s" % (nic.name, node.fqdn): HostnameIPMapping(
                node.system_id, 30, {auto_ip.ip}, node.node_type)}
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_combines_IPv4_and_IPv6_addresses(self):
        node = factory.make_Node(interface=True)
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
            {node.fqdn: HostnameIPMapping(
                node.system_id, 30, {ipv4_address.ip, ipv6_address.ip},
                node.node_type)},
            mapping)

    def test_get_hostname_ip_mapping_combines_MACs_for_same_node(self):
        # A node's preferred static IPv4 and IPv6 addresses may be on
        # different MACs.
        node = factory.make_Node()
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
            {node.fqdn: HostnameIPMapping(
                node.system_id, 30,
                {ipv4_address.ip, ipv6_address.ip}, node.node_type)},
            mapping)

    def test_get_hostname_ip_mapping_prefers_non_discovered_addresses(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr))
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'), subnet=subnet)
        iface = node.get_boot_interface()
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, interface=iface,
            subnet=subnet)
        discovered = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, interface=iface,
            subnet=subnet)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {staticip.ip}, node.node_type),
            "%s.%s" % (iface.name, node.fqdn): HostnameIPMapping(
                node.system_id, 30, {discovered.ip}, node.node_type)}
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_prefers_bond_with_no_boot_interface(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr))
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'), subnet=subnet)
        node.boot_interface = None
        node.save()
        iface = node.get_boot_interface()
        iface2 = factory.make_Interface(node=node)
        iface3 = factory.make_Interface(node=node)
        bondif = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, parents=[iface2, iface3])
        iface_ip = factory.make_StaticIPAddress(
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
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {bond_staticip.ip}, node.node_type),
            "%s.%s" % (iface.name, node.fqdn): HostnameIPMapping(
                node.system_id, 30, {iface_ip.ip}, node.node_type)}
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_prefers_bond_with_boot_interface(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr))
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'), subnet=subnet)
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
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {bond_staticip.ip}, node.node_type),
            }
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_ignores_bond_without_boot_interface(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr))
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'), subnet=subnet)
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
        bondip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=bondif,
            subnet=subnet)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {boot_staticip.ip}, node.node_type),
            "%s.%s" % (bondif.name, node.fqdn): HostnameIPMapping(
                node.system_id, 30, {bondip.ip}, node.node_type)}
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_prefers_boot_interface(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr))
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'), subnet=subnet)
        iface = node.get_boot_interface()
        iface_ip = factory.make_StaticIPAddress(
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
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {boot_sip.ip}, node.node_type),
            "%s.%s" % (iface.name, node.fqdn): HostnameIPMapping(
                node.system_id, 30, {iface_ip.ip}, node.node_type)}
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_prefers_boot_interface_to_alias(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr))
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'), subnet=subnet)
        iface = node.get_boot_interface()
        iface_ip = factory.make_StaticIPAddress(
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
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {boot_sip.ip}, node.node_type),
            "%s.%s" % (iface.name, node.fqdn): HostnameIPMapping(
                node.system_id, 30, {iface_ip.ip}, node.node_type)}
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_prefers_physical_interfaces_to_vlan(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr))
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'), subnet=subnet)
        iface = node.get_boot_interface()
        vlanif = factory.make_Interface(
            INTERFACE_TYPE.VLAN, node=node, parents=[iface])
        phy_staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface,
            subnet=subnet)
        vlanip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=vlanif,
            subnet=subnet)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {phy_staticip.ip}, node.node_type),
            "%s.%s" % (vlanif.name, node.fqdn): HostnameIPMapping(
                node.system_id, 30, {vlanip.ip}, node.node_type)}
        self.assertEqual(expected_mapping, mapping)

    @skip("XXX: GavinPanella 2016-04-27 bug=1556188: Fails spuriously.")
    def test_get_hostname_ip_mapping_returns_domain_head_ips(self):
        parent = factory.make_Domain()
        name = factory.make_name()
        child = factory.make_Domain(name='%s.%s' % (name, parent.name))
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, domain=parent, hostname=name)
        sip1 = factory.make_StaticIPAddress(subnet=subnet)
        node.interface_set.first().ip_addresses.add(sip1)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            parent)
        self.assertEqual({node.fqdn: HostnameIPMapping(
            node.system_id, 30, {sip1.ip}, node.node_type)}, mapping)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            child)
        self.assertEqual({node.fqdn: HostnameIPMapping(
            node.system_id, 30, {sip1.ip}, node.node_type)}, mapping)

    def test_get_hostname_ip_mapping_does_not_return_discovered_and_auto(self):
        # Create a situation where we have an AUTO ip on the pxeboot interface,
        # and a discovered IP of the other address family (v4/v6) on another
        # interface.
        domain = Domain.objects.get_default_domain()
        cidrs = [factory.make_ipv6_network(), factory.make_ipv4_network()]
        shuffle(cidrs)
        subnets = [factory.make_Subnet(cidr=cidr) for cidr in cidrs]
        # First, make a node with an interface on subnets[0].  Assign the boot
        # interface an AUTO IP on subnets[0].
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'), subnet=subnets[0],
            vlan=subnets[0].vlan)
        sip0 = node.boot_interface.ip_addresses.first()
        ip0 = factory.pick_ip_in_network(cidrs[0])
        sip0.ip = ip0
        sip0.alloc_type = IPADDRESS_TYPE.AUTO
        sip0.save()
        # Now create another interface, and give it a DISCOVERED IP of the
        # other family from subnets[1].
        iface1 = factory.make_Interface(node=node, vlan=subnets[1].vlan)
        ip1 = factory.pick_ip_in_network(cidrs[1])
        sip1 = factory.make_StaticIPAddress(
            subnet=subnets[1], ip=ip1,
            alloc_type=IPADDRESS_TYPE.DISCOVERED
            )
        iface1.ip_addresses.add(sip1)
        iface1.save()
        # The only mapping we should get is for the boot interface.
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {sip0.ip}, node.node_type),
            "%s.%s" % (iface1.name, node.fqdn): HostnameIPMapping(
                node.system_id, 30, {sip1.ip}, node.node_type)}
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_returns_correct_bond_ip(self):
        # Create a situation where we have a STICKY ip on the pxeboot
        # interface, a STICKY ip on a bond containing the pxeboot interface and
        # another interface, and a discovered IP of the other address family
        # (v4/v6) on another interface.  We should only get the bond ip.
        domain = Domain.objects.get_default_domain()
        cidrs = [factory.make_ipv6_network(), factory.make_ipv4_network()]
        shuffle(cidrs)
        subnets = [factory.make_Subnet(cidr=cidr) for cidr in cidrs]
        # First, make a node with an interface on subnets[0].  Assign the boot
        # interface an AUTO IP on subnets[0].
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name('host'), subnet=subnets[0],
            vlan=subnets[0].vlan)
        sip0 = node.boot_interface.ip_addresses.first()
        ip0 = factory.pick_ip_in_network(cidrs[0])
        sip0.ip = ip0
        sip0.alloc_type = IPADDRESS_TYPE.STICKY
        sip0.save()
        # Now create another interface, and give it a DISCOVERED IP of the
        # other family from subnets[1].
        iface1 = factory.make_Interface(node=node, vlan=subnets[1].vlan)
        ip1 = factory.pick_ip_in_network(cidrs[1])
        sip1 = factory.make_StaticIPAddress(
            subnet=subnets[1], ip=ip1,
            alloc_type=IPADDRESS_TYPE.DISCOVERED
            )
        iface1.ip_addresses.add(sip1)
        iface1.save()
        # Now create a bond containing the boot interface, and assign it
        # another IP from the same subnet as the boot interface.
        iface0 = node.get_boot_interface()
        iface2 = factory.make_Interface(node=node)
        bondif = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, parents=[iface0, iface2])
        bondip = factory.pick_ip_in_network(cidrs[0], but_not=[ip0])
        bond_sip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=bondif,
            subnet=subnets[0], ip=bondip)
        # The only mapping we should get is for the bond interface.
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {bond_sip.ip}, node.node_type),
            "%s.%s" % (iface1.name, node.fqdn): HostnameIPMapping(
                node.system_id, 30, {sip1.ip}, node.node_type),
            }
        self.assertEqual(expected_mapping, mapping)


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
        subnet = factory.make_Subnet()
        num_ips = randint(3, 5)
        ips = [
            factory.make_StaticIPAddress(
                subnet=subnet, alloc_type=IPADDRESS_TYPE.USER_RESERVED)
            for _ in range(num_ips)
        ]
        mappings = StaticIPAddress.objects._get_user_reserved_mappings(
            subnet)
        self.expectThat(mappings, HasLength(len(ips)))

    def test_user_reserved_addresses_included_in_get_hostname_ip_mapping(self):
        num_ips = randint(3, 5)
        domain0 = Domain.objects.get_default_domain()
        domain1 = factory.make_Domain()
        ips = [
            factory.make_StaticIPAddress(
                hostname="%s.%s" % (factory.make_name('host'), domain0.name),
                alloc_type=IPADDRESS_TYPE.USER_RESERVED)
            for _ in range(num_ips)
        ]
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain0)
        self.expectThat(mappings, HasLength(len(ips)))
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain1)
        self.expectThat(mappings, HasLength(0))

    def test_user_reserved_addresses_included_in_correct_domains(self):
        domain0 = Domain.objects.get_default_domain()
        domain1 = factory.make_Domain()
        domain2 = factory.make_Domain()
        ips1 = [
            factory.make_StaticIPAddress(
                hostname="%s.%s" % (
                    factory.make_name('host'), domain1.name),
                alloc_type=IPADDRESS_TYPE.USER_RESERVED)
            for _ in range(randint(3, 5))
        ]
        ips2 = [
            factory.make_StaticIPAddress(
                hostname="%s.%s" % (
                    factory.make_name('host'), domain2.name),
                alloc_type=IPADDRESS_TYPE.USER_RESERVED)
            for _ in range(randint(1, 2))
        ]
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain0)
        self.expectThat(mappings, HasLength(0))
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain1)
        self.expectThat(mappings, HasLength(len(ips1)))
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain2)
        self.expectThat(mappings, HasLength(len(ips2)))


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
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        ip = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet), user=user,
            interface=node.get_boot_interface())
        json = ip.render_json(with_node_summary=True)
        self.expectThat(json, Not(Contains("user")))
        self.expectThat(json, Contains("node_summary"))

    def test__node_summary_includes_interface_name(self):
        user = factory.make_User()
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        self.expectThat(node.interface_set.count(), Equals(1))
        iface = node.interface_set.first()
        ip = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet), user=user,
            interface=node.get_boot_interface())
        json = ip.render_json(with_node_summary=True)
        self.expectThat(json, Not(Contains("user")))
        self.expectThat(json, Contains("node_summary"))
        self.expectThat(json['node_summary']['via'], Equals(iface.name))

    def test__data_is_accurate_and_complete(self):
        user = factory.make_User()
        hostname = factory.make_name('hostname')
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, hostname=hostname)
        ip = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet), user=user,
            interface=node.get_boot_interface())
        json = ip.render_json(with_username=True, with_node_summary=True)
        self.expectThat(
            json["created"], Equals(dehydrate_datetime(ip.created)))
        self.expectThat(
            json["updated"], Equals(dehydrate_datetime(ip.updated)))
        self.expectThat(json["user"], Equals(user.username))
        self.assertThat(json, Contains("node_summary"))
        node_summary = json["node_summary"]
        self.expectThat(node_summary["system_id"], Equals(node.system_id))
        self.expectThat(node_summary["node_type"], Equals(node.node_type))
