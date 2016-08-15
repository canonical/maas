# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for network helpers."""

__all__ = []

import socket
from socket import (
    EAI_BADFLAGS,
    EAI_NODATA,
    EAI_NONAME,
    gaierror,
    IPPROTO_TCP,
)
from unittest import mock

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from netaddr import (
    IPAddress,
    IPNetwork,
    IPRange,
)
from netaddr.eui import EUI
import netifaces
from netifaces import (
    AF_INET,
    AF_INET6,
    AF_LINK,
)
import provisioningserver.utils
from provisioningserver.utils import network as network_module
from provisioningserver.utils.network import (
    bytes_to_hex,
    bytes_to_int,
    clean_up_netifaces_address,
    find_ip_via_arp,
    find_mac_via_arp,
    format_eui,
    get_all_addresses_for_interface,
    get_all_interface_addresses,
    get_all_interfaces_definition,
    get_interface_children,
    hex_str_to_bytes,
    inet_ntop,
    interface_children,
    intersect_iprange,
    ip_range_within_network,
    IPRangeStatistics,
    is_loopback_address,
    MAASIPRange,
    MAASIPSet,
    make_iprange,
    make_network,
    parse_integer,
    resolve_host_to_addrinfo,
    resolve_hostname,
    resolves_to_loopback_address,
)
from provisioningserver.utils.shell import call_and_check
from testtools.matchers import (
    Contains,
    Equals,
    HasLength,
    Is,
    MatchesDict,
    MatchesSetwise,
    Not,
)


installed_curtin_version = call_and_check([
    "dpkg-query", "--showformat=${Version}",
    "--show", "python3-curtin"]).decode("ascii")
installed_curtin_version = int(
    installed_curtin_version.split("~bzr", 1)[1].split("-", 1)[0])


class TestMakeNetwork(MAASTestCase):

    def test_constructs_IPNetwork(self):
        network = make_network('10.22.82.0', 24)
        self.assertIsInstance(network, IPNetwork)
        self.assertEqual(IPNetwork('10.22.82.0/24'), network)

    def test_passes_args_to_IPNetwork(self):
        self.patch(network_module, 'IPNetwork')
        make_network('10.1.2.0', 24, foo=9)
        self.assertEqual(
            [mock.call('10.1.2.0/24', foo=9)],
            network_module.IPNetwork.mock_calls)


class TestInetNtop(MAASTestCase):

    def test__ipv4(self):
        ip = factory.make_ipv4_address()
        self.assertThat(inet_ntop(IPAddress(ip).value), Equals(ip))

    def test__ipv6(self):
        ip = factory.make_ipv6_address()
        self.assertThat(inet_ntop(IPAddress(ip).value), Equals(ip))


class TestConversionFunctions(MAASTestCase):

    def test__bytes_to_hex(self):
        self.assertThat(bytes_to_hex(b'\x01\xff'), Equals(b'01ff'))
        self.assertThat(bytes_to_hex(b'\x00\x01\xff'), Equals(b'0001ff'))

    def test__bytes_to_int(self):
        self.assertThat(bytes_to_int(b'\xff\xff'), Equals(65535))
        self.assertThat(bytes_to_int(b'\xff\xff\xff'), Equals(16777215))
        self.assertThat(
            bytes_to_int(b'\xff\xff\xff\xff\xff\xff'), Equals(281474976710655))

    def test__hex_str_to_bytes(self):
        self.assertThat(hex_str_to_bytes('0x0000'), Equals(b'\x00\x00'))
        self.assertThat(hex_str_to_bytes('ff:ff'), Equals(b'\xff\xff'))
        self.assertThat(hex_str_to_bytes('ff ff  '), Equals(b'\xff\xff'))
        self.assertThat(hex_str_to_bytes('  ff-ff'), Equals(b'\xff\xff'))
        self.assertThat(hex_str_to_bytes('ff-ff'), Equals(b'\xff\xff'))
        self.assertThat(hex_str_to_bytes('0xffff'), Equals(b'\xff\xff'))
        self.assertThat(hex_str_to_bytes(' 0xffff'), Equals(b'\xff\xff'))
        self.assertThat(
            hex_str_to_bytes('01:02:03:04:05:06'),
            Equals(b'\x01\x02\x03\x04\x05\x06'))
        self.assertThat(
            hex_str_to_bytes('0A:0B:0C:0D:0E:0F'),
            Equals(b'\x0a\x0b\x0c\x0d\x0e\x0f'))
        self.assertThat(
            hex_str_to_bytes('0a:0b:0c:0d:0e:0f'),
            Equals(b'\x0a\x0b\x0c\x0d\x0e\x0f'))

    def test__format_eui(self):
        self.assertThat(
            format_eui(EUI('0A-0B-0C-0D-0E-0F')), Equals("0a:0b:0c:0d:0e:0f"))


class TestFindIPViaARP(MAASTestCase):

    def patch_call(self, output):
        """Replace `call_and_check` with one that returns `output`."""
        fake = self.patch(network_module, 'call_and_check')
        fake.return_value = output.encode("ascii")
        return fake

    def test__resolves_MAC_address_to_IP(self):
        sample = """\
        Address HWtype  HWaddress Flags Mask            Iface
        192.168.100.20 (incomplete)                              virbr1
        192.168.0.104 (incomplete)                              eth0
        192.168.0.5 (incomplete)                              eth0
        192.168.0.2 (incomplete)                              eth0
        192.168.0.100 (incomplete)                              eth0
        192.168.122.20 ether   52:54:00:02:86:4b   C                     virbr0
        192.168.0.4 (incomplete)                              eth0
        192.168.0.1 ether   90:f6:52:f6:17:92   C                     eth0
        """

        call_and_check = self.patch_call(sample)
        ip_address_observed = find_ip_via_arp("90:f6:52:f6:17:92")
        self.assertThat(call_and_check, MockCalledOnceWith(['arp', '-n']))
        self.assertEqual("192.168.0.1", ip_address_observed)

    def test__returns_consistent_output(self):
        mac = factory.make_mac_address()
        ips = [
            '10.0.0.11',
            '10.0.0.99',
            ]
        lines = ['%s ether %s C eth0' % (ip, mac) for ip in ips]
        self.patch_call('\n'.join(lines))
        one_result = find_ip_via_arp(mac)
        self.patch_call('\n'.join(reversed(lines)))
        other_result = find_ip_via_arp(mac)

        self.assertIn(one_result, ips)
        self.assertEqual(one_result, other_result)

    def test__ignores_case(self):
        sample = """\
        192.168.0.1 ether   90:f6:52:f6:17:92   C                     eth0
        """
        self.patch_call(sample)
        ip_address_observed = find_ip_via_arp("90:f6:52:f6:17:92".upper())
        self.assertEqual("192.168.0.1", ip_address_observed)


class TestFindMACViaARP(MAASTestCase):

    def patch_call(self, output):
        """Replace `call_and_check` with one that returns `output`."""
        fake = self.patch(provisioningserver.utils.network, 'call_and_check')
        fake.return_value = output.encode("ascii")
        return fake

    def make_output_line(self, ip=None, mac=None, dev=None):
        """Compose an `ip neigh` output line for given `ip` and `mac`."""
        if ip is None:
            ip = factory.make_ipv4_address()
        if mac is None:
            mac = factory.make_mac_address()
        if dev is None:
            dev = factory.make_name('eth', sep='')
        return "%(ip)s dev %(dev)s lladdr %(mac)s\n" % {
            'ip': ip,
            'dev': dev,
            'mac': mac,
            }

    def test__calls_ip_neigh(self):
        call_and_check = self.patch_call('')
        find_mac_via_arp(factory.make_ipv4_address())
        self.assertThat(
            call_and_check,
            MockCalledOnceWith(['ip', 'neigh'], env={'LC_ALL': 'C'}))

    def test__works_with_real_call(self):
        find_mac_via_arp(factory.make_ipv4_address())
        # No error.
        pass

    def test__fails_on_nonsensical_output(self):
        self.patch_call("Weird output...")
        self.assertRaises(
            Exception, find_mac_via_arp, factory.make_ipv4_address())

    def test__returns_None_if_not_found(self):
        self.patch_call(self.make_output_line())
        self.assertIsNone(find_mac_via_arp(factory.make_ipv4_address()))

    def test__resolves_IPv4_address_to_MAC(self):
        sample = "10.55.60.9 dev eth0 lladdr 3c:41:92:68:2e:00 REACHABLE\n"
        self.patch_call(sample)
        mac_address_observed = find_mac_via_arp('10.55.60.9')
        self.assertEqual('3c:41:92:68:2e:00', mac_address_observed)

    def test__resolves_IPv6_address_to_MAC(self):
        sample = (
            "fd10::a76:d7fe:fe93:7cb dev eth0 lladdr 3c:41:92:6b:2e:00 "
            "REACHABLE\n")
        self.patch_call(sample)
        mac_address_observed = find_mac_via_arp('fd10::a76:d7fe:fe93:7cb')
        self.assertEqual('3c:41:92:6b:2e:00', mac_address_observed)

    def test__ignores_failed_neighbours(self):
        ip = factory.make_ipv4_address()
        self.patch_call("%s dev eth0  FAILED\n" % ip)
        self.assertIsNone(find_mac_via_arp(ip))

    def test__is_not_fooled_by_prefixing(self):
        self.patch_call(self.make_output_line('10.1.1.10'))
        self.assertIsNone(find_mac_via_arp('10.1.1.1'))
        self.assertIsNone(find_mac_via_arp('10.1.1.100'))

    def test__is_not_fooled_by_different_notations(self):
        mac = factory.make_mac_address()
        self.patch_call(self.make_output_line('9::0:05', mac=mac))
        self.assertEqual(mac, find_mac_via_arp('09:0::5'))

    def test__returns_consistent_output(self):
        ip = factory.make_ipv4_address()
        macs = [
            '52:54:00:02:86:4b',
            '90:f6:52:f6:17:92',
            ]
        lines = [self.make_output_line(ip, mac) for mac in macs]
        self.patch_call(''.join(lines))
        one_result = find_mac_via_arp(ip)
        self.patch_call(''.join(reversed(lines)))
        other_result = find_mac_via_arp(ip)

        self.assertIn(one_result, macs)
        self.assertEqual(one_result, other_result)


def patch_interfaces(testcase, interfaces):
    """Patch `netifaces` to show the given `interfaces`.

    :param testcase: The testcase that's doing the patching.
    :param interfaces: A dict mapping interface names to `netifaces`
        interface entries: dicts with keys like `AF_INET` etc.
    """
    # These two netifaces functions map conveniently onto dict methods.
    testcase.patch(netifaces, 'interfaces', interfaces.keys)
    testcase.patch(netifaces, 'ifaddresses', interfaces.get)


class TestGetAllAddressesForInterface(MAASTestCase):
    """Tests for `get_all_addresses_for_interface`."""

    scenarios = [
        ('ipv4', {
            'inet_class': AF_INET,
            'network_factory': factory.make_ipv4_network,
            'ip_address_factory': factory.make_ipv4_address,
            'loopback_address': '127.0.0.1',
            }),
        ('ipv6', {
            'inet_class': AF_INET6,
            'network_factory': factory.make_ipv6_network,
            'ip_address_factory': factory.make_ipv6_address,
            'loopback_address': '::1',
            }),
        ]

    def test__returns_address_for_inet_class(self):
        ip = self.ip_address_factory()
        interface = factory.make_name('eth', sep='')
        patch_interfaces(
            self, {interface: {self.inet_class: [{'addr': str(ip)}]}})
        self.assertEqual(
            [ip], list(get_all_addresses_for_interface(interface)))

    def test__ignores_non_address_information(self):
        network = self.network_factory()
        ip = factory.pick_ip_in_network(network)
        interface = factory.make_name('eth', sep='')
        patch_interfaces(self, {
            interface: {
                self.inet_class: [{
                    'addr': str(ip),
                    'broadcast': str(network.broadcast),
                    'netmask': str(network.netmask),
                    'peer': str(
                        factory.pick_ip_in_network(network, but_not=[ip])),
                    }],
                },
            })
        self.assertEqual(
            [ip], list(get_all_addresses_for_interface(interface)))

    def test__ignores_link_address(self):
        interface = factory.make_name('eth', sep='')
        patch_interfaces(self, {
            interface: {
                AF_LINK: [{
                    'addr': str(factory.make_mac_address()),
                    'peer': str(factory.make_mac_address()),
                    }],
                },
            })
        self.assertEqual([], list(get_all_addresses_for_interface(interface)))

    def test__ignores_interface_without_address(self):
        network = self.network_factory()
        interface = factory.make_name('eth', sep='')
        patch_interfaces(self, {
            interface: {
                self.inet_class: [{
                    'broadcast': str(network.broadcast),
                    'netmask': str(network.netmask),
                    }],
                },
            })
        self.assertEqual([], list(get_all_addresses_for_interface(interface)))


class TestGetAllInterfaceAddresses(MAASTestCase):
    """Tests for get_all_interface_addresses()."""

    def test__includes_loopback(self):
        v4_loopback_address = '127.0.0.1'
        v6_loopback_address = '::1'
        patch_interfaces(self, {
            'lo': {
                AF_INET: [
                    {'addr': v4_loopback_address}],
                AF_INET6: [
                    {'addr': v6_loopback_address}],
                }})
        self.assertEqual(
            [v4_loopback_address, v6_loopback_address],
            list(get_all_interface_addresses()))

    def test_returns_all_addresses_for_all_interfaces(self):
        v4_ips = [factory.make_ipv4_address() for _ in range(2)]
        v6_ips = [factory.make_ipv6_address() for _ in range(2)]
        ips = zip(v4_ips, v6_ips)
        interfaces = {
            factory.make_name('eth', sep=''): {
                AF_INET: [{'addr': str(ipv4)}],
                AF_INET6: [{'addr': str(ipv6)}],
                }
            for ipv4, ipv6 in ips
            }
        patch_interfaces(self, interfaces)
        self.assertItemsEqual(
            v4_ips + v6_ips,
            get_all_interface_addresses())


class TestGetAllInterfaceAddressesWithMultipleClasses(MAASTestCase):
    """Tests for get_all_interface_addresses() with multiple inet classes."""

    def patch_interfaces(self, interfaces):
        """Patch `netifaces` to show the given `interfaces`.

        :param interfaces: A dict mapping interface names to `netifaces`
            interface entries: dicts with keys like `AF_INET` etc.
        """
        # These two netifaces functions map conveniently onto dict methods.
        self.patch(netifaces, 'interfaces', interfaces.keys)
        self.patch(netifaces, 'ifaddresses', interfaces.get)

    def test_returns_all_addresses_for_interface(self):
        v4_ip = factory.make_ipv4_address()
        v6_ip = factory.make_ipv6_address()
        interface = factory.make_name('eth', sep='')
        patch_interfaces(self, {
            interface: {
                AF_INET: [
                    {'addr': str(v4_ip)}],
                AF_INET6: [
                    {'addr': str(v6_ip)}],
                }
            })
        self.assertEqual([v4_ip, v6_ip], list(get_all_interface_addresses()))


class TestCleanUpNetifacesAddress(MAASTestCase):
    """Tests for `clean_up_netifaces_address`."""

    def test__leaves_IPv4_intact(self):
        ip = str(factory.make_ipv4_address())
        interface = factory.make_name('eth')
        self.assertEqual(ip, clean_up_netifaces_address(ip, interface))

    def test__leaves_clean_IPv6_intact(self):
        ip = str(factory.make_ipv6_address())
        interface = factory.make_name('eth')
        self.assertEqual(ip, clean_up_netifaces_address(ip, interface))

    def test__removes_zone_index_suffix(self):
        ip = str(factory.make_ipv6_address())
        interface = factory.make_name('eth')
        self.assertEqual(
            ip,
            clean_up_netifaces_address('%s%%%s' % (ip, interface), interface))


class TestResolveHostToAddrs(MAASTestCase):
    """Tests for `resolve_hostname`."""

    def patch_getaddrinfo(self, *addrs):
        fake = self.patch(network_module, 'getaddrinfo')
        fake.return_value = [
            (None, None, None, None, (str(address), 0))
            for address in addrs
            ]
        return fake

    def patch_getaddrinfo_fail(self, exception):
        fake = self.patch(network_module, 'getaddrinfo')
        fake.side_effect = exception
        return fake

    def test__rejects_weird_IP_version(self):
        self.assertRaises(
            AssertionError,
            resolve_hostname, factory.make_hostname(), ip_version=5)

    def test__integrates_with_getaddrinfo(self):
        result = resolve_hostname('localhost', 4)
        self.assertIsInstance(result, set)
        [localhost] = result
        self.assertIsInstance(localhost, IPAddress)
        self.assertIn(localhost, IPNetwork('127.0.0.0/8'))

    def test__resolves_IPv4_address(self):
        ip = factory.make_ipv4_address()
        fake = self.patch_getaddrinfo(ip)
        hostname = factory.make_hostname()
        result = resolve_hostname(hostname, 4)
        self.assertIsInstance(result, set)
        self.assertEqual({IPAddress(ip)}, result)
        self.assertThat(
            fake, MockCalledOnceWith(
                hostname, 0, family=AF_INET, proto=IPPROTO_TCP))

    def test__resolves_IPv6_address(self):
        ip = factory.make_ipv6_address()
        fake = self.patch_getaddrinfo(ip)
        hostname = factory.make_hostname()
        result = resolve_hostname(hostname, 6)
        self.assertIsInstance(result, set)
        self.assertEqual({IPAddress(ip)}, result)
        self.assertThat(
            fake, MockCalledOnceWith(
                hostname, 0, family=AF_INET6, proto=IPPROTO_TCP))

    def test__returns_empty_if_address_does_not_resolve(self):
        self.patch_getaddrinfo_fail(
            gaierror(EAI_NONAME, "Name or service not known"))
        self.assertEqual(
            set(), resolve_hostname(factory.make_hostname(), 4))

    def test__returns_empty_if_address_resolves_to_no_data(self):
        self.patch_getaddrinfo_fail(
            gaierror(EAI_NODATA, "No data returned"))
        self.assertEqual(
            set(), resolve_hostname(factory.make_hostname(), 4))

    def test__propagates_other_gaierrors(self):
        self.patch_getaddrinfo_fail(gaierror(EAI_BADFLAGS, "Bad parameters"))
        self.assertRaises(
            gaierror,
            resolve_hostname, factory.make_hostname(), 4)

    def test__propagates_unexpected_errors(self):
        self.patch_getaddrinfo_fail(KeyError("Huh what?"))
        self.assertRaises(
            KeyError,
            resolve_hostname, factory.make_hostname(), 4)

    def test_resolve_host_to_addrinfo_returns_full_information(self):
        ip = factory.make_ipv4_address()
        fake = self.patch_getaddrinfo(ip)
        hostname = factory.make_hostname()
        result = resolve_host_to_addrinfo(hostname, 4)
        self.assertIsInstance(result, list)
        self.assertEqual(
            [(None, None, None, None, (ip, 0))], result)
        self.assertThat(
            fake, MockCalledOnceWith(
                hostname, 0, family=AF_INET, proto=IPPROTO_TCP))


class TestIntersectIPRange(MAASTestCase):
    """Tests for `intersect_iprange()`."""

    def test_finds_intersection_between_two_ranges(self):
        range_1 = IPRange('10.0.0.1', '10.0.0.255')
        range_2 = IPRange('10.0.0.128', '10.0.0.200')
        intersect = intersect_iprange(range_1, range_2)
        self.expectThat(
            IPAddress(intersect.first), Equals(IPAddress('10.0.0.128')))
        self.expectThat(
            IPAddress(intersect.last), Equals(IPAddress('10.0.0.200')))

    def test_ignores_non_intersecting_ranges(self):
        range_1 = IPRange('10.0.0.1', '10.0.0.255')
        range_2 = IPRange('10.0.1.128', '10.0.1.200')
        self.assertIsNone(intersect_iprange(range_1, range_2))

    def test_finds_partial_intersection(self):
        range_1 = IPRange('10.0.0.1', '10.0.0.128')
        range_2 = IPRange('10.0.0.64', '10.0.0.200')
        intersect = intersect_iprange(range_1, range_2)
        self.expectThat(
            IPAddress(intersect.first), Equals(IPAddress('10.0.0.64')))
        self.expectThat(
            IPAddress(intersect.last), Equals(IPAddress('10.0.0.128')))


class TestIPRangeWithinNetwork(MAASTestCase):

    def test_returns_true_when_ip_range_is_within_network(self):
        ip_range = IPRange('10.0.0.55', '10.0.255.55')
        ip_network = IPNetwork('10.0.0.0/16')
        self.assertTrue(ip_range_within_network(ip_range, ip_network))

    def test_returns_false_when_ip_range_is_within_network(self):
        ip_range = IPRange('192.0.0.55', '192.0.255.55')
        ip_network = IPNetwork('10.0.0.0/16')
        self.assertFalse(ip_range_within_network(ip_range, ip_network))

    def test_returns_false_when_ip_range_is_partially_within_network(self):
        ip_range = IPRange('10.0.0.55', '10.1.0.55')
        ip_network = IPNetwork('10.0.0.0/16')
        self.assertFalse(ip_range_within_network(ip_range, ip_network))

    def test_works_with_two_ip_networks(self):
        network_1 = IPNetwork('10.0.0.0/16')
        network_2 = IPNetwork('10.0.0.0/24')
        self.assertTrue(ip_range_within_network(network_2, network_1))


class TestMAASIPSet(MAASTestCase):

    def test__contains_method(self):
        s = MAASIPSet([
            make_iprange('10.0.0.1', '10.0.0.100'),
            make_iprange('10.0.0.200', '10.0.0.254'),
        ])
        self.assertThat(s, Contains('10.0.0.1'))
        self.assertThat(s, Contains(IPAddress('10.0.0.1')))
        self.assertThat(s, Contains(IPRange('10.0.0.1', '10.0.0.100')))
        self.assertThat(s, Not(Contains(IPRange('10.0.0.1', '10.0.0.101'))))
        self.assertThat(s, Not(Contains('10.0.0.101')))
        self.assertThat(s, Not(Contains('10.0.0.199')))
        self.assertThat(s, Contains(IPRange('10.0.0.200', '10.0.0.254')))
        self.assertThat(s, Not(Contains(IPRange('10.0.0.99', '10.0.0.254'))))
        self.assertThat(s, Not(Contains('10.0.0.255')))

    def test__normalizes_range(self):
        addr1 = '10.0.0.1'
        addr2 = IPAddress('10.0.0.2')
        range1 = make_iprange('10.0.0.3', purpose="DNS")
        range2 = make_iprange('10.0.0.4', '10.0.0.100', purpose='DHCP')
        s = MAASIPSet([range2, range1, addr1, addr2])
        for item in s:
            self.assertThat(type(item), Equals(MAASIPRange))
        self.assertThat(s, Contains('10.0.0.1'))
        self.assertThat(s, Contains('10.0.0.2'))
        self.assertThat(s, Contains('10.0.0.3'))
        self.assertThat(s, Contains('10.0.0.4'))
        self.assertThat(s, Contains('10.0.0.50'))
        self.assertThat(s, Contains('10.0.0.100'))
        self.assertThat(s, Not(Contains('10.0.0.101')))
        self.assertThat(s, Not(Contains('10.0.0.0')))

    def test__normalizes_ipv6_range(self):
        addr1 = 'fe80::1'
        addr2 = IPAddress('fe80::2')
        range1 = make_iprange('fe80::3', purpose="DNS")
        range2 = make_iprange(
            'fe80::100', 'fe80::ffff:ffff:ffff:ffff', purpose='DHCP')
        s = MAASIPSet([range2, range1, addr1, addr2])
        for item in s:
            self.assertThat(type(item), Equals(MAASIPRange))
        self.assertThat(s, Contains('fe80::1'))
        self.assertThat(s, Contains('fe80::2'))
        self.assertThat(s, Contains('fe80::3'))
        self.assertThat(s, Contains('fe80::100'))
        self.assertThat(s, Contains('fe80::ffff:ffff:ffff:ffff'))
        self.assertThat(s, Not(Contains('fe80::1:ffff:ffff:ffff:ffff')))

    def test__normalizes_range_with_iprange(self):
        addr1 = '10.0.0.1'
        addr2 = IPAddress('10.0.0.2')
        range1 = make_iprange('10.0.0.3', purpose="DNS")
        range2 = IPRange('10.0.0.4', '10.0.0.100')
        s = MAASIPSet([range2, range1, addr1, addr2])
        for item in s:
            self.assertThat(type(item), Equals(MAASIPRange))
        self.assertThat(s, Contains('10.0.0.1'))
        self.assertThat(s, Contains('10.0.0.2'))
        self.assertThat(s, Contains('10.0.0.3'))
        self.assertThat(s, Contains('10.0.0.4'))
        self.assertThat(s, Contains('10.0.0.50'))
        self.assertThat(s, Contains('10.0.0.100'))
        self.assertThat(s, Not(Contains('10.0.0.101')))
        self.assertThat(s, Not(Contains('10.0.0.0')))

    def test__calculates_simple_unused_range(self):
        addr1 = '10.0.0.2'
        addr2 = IPAddress('10.0.0.3')
        range1 = make_iprange('10.0.0.4', purpose="DNS")
        range2 = IPRange('10.0.0.5', '10.0.0.100')
        s = MAASIPSet([range2, range1, addr1, addr2])
        u = s.get_unused_ranges('10.0.0.0/24')
        self.assertThat(u, Not(Contains('10.0.0.0')))
        self.assertThat(u, Contains('10.0.0.1'))
        self.assertThat(u, Contains('10.0.0.101'))
        self.assertThat(u, Contains('10.0.0.150'))
        self.assertThat(u, Contains('10.0.0.254'))
        self.assertThat(u, Not(Contains('10.0.0.255')))

    def test__calculates_simple_unused_range_with_iprange_input(self):
        addr1 = '10.0.0.1'
        addr2 = IPAddress('10.0.0.2')
        range1 = make_iprange('10.0.0.3', purpose="DNS")
        range2 = IPRange('10.0.0.4', '10.0.0.100')
        s = MAASIPSet([range2, range1, addr1, addr2])
        u = s.get_unused_ranges(IPRange('10.0.0.0', '10.0.0.255'))
        self.assertThat(u, Contains('10.0.0.0'))
        self.assertThat(u, Contains('10.0.0.101'))
        self.assertThat(u, Contains('10.0.0.150'))
        self.assertThat(u, Contains('10.0.0.254'))
        self.assertThat(u, Contains('10.0.0.255'))

    def test__calculates_unused_range_with_overlap(self):
        range1 = make_iprange('10.0.0.3', purpose="DNS")
        range2 = make_iprange('10.0.0.3', '10.0.0.20', purpose="DHCP")
        rangeset = MAASIPSet([range2, range1])
        u = rangeset.get_unused_ranges('10.0.0.0/24')
        self.assertThat(u, Contains('10.0.0.1'))
        self.assertThat(u, Contains('10.0.0.2'))
        self.assertThat(u, Not(Contains('10.0.0.3')))
        self.assertThat(u, Not(Contains('10.0.0.4')))
        self.assertThat(u, Not(Contains('10.0.0.20')))
        self.assertThat(u, Contains('10.0.0.21'))

    def test__calculates_unused_range_with_multiple_overlap(self):
        range1 = make_iprange('10.0.0.3', purpose="DNS")
        range2 = make_iprange('10.0.0.3', purpose="WINS")
        range3 = make_iprange('10.0.0.3', '10.0.0.20', purpose="DHCP")
        range4 = make_iprange('10.0.0.5', '10.0.0.20', purpose="DHCP")
        range5 = make_iprange('10.0.0.5', '10.0.0.18', purpose="DHCP")
        s = MAASIPSet([range1, range2, range3, range4, range5])
        u = s.get_unused_ranges('10.0.0.0/24')
        self.assertThat(u, Not(Contains('10.0.0.0')))
        self.assertThat(u, Contains('10.0.0.1'))
        self.assertThat(u, Contains('10.0.0.2'))
        self.assertThat(u, Not(Contains('10.0.0.3')))
        self.assertThat(u, Not(Contains('10.0.0.4')))
        self.assertThat(u, Not(Contains('10.0.0.5')))
        self.assertThat(u, Not(Contains('10.0.0.6')))
        self.assertThat(u, Not(Contains('10.0.0.10')))
        self.assertThat(u, Not(Contains('10.0.0.18')))
        self.assertThat(u, Not(Contains('10.0.0.19')))
        self.assertThat(u, Not(Contains('10.0.0.20')))
        self.assertThat(u, Contains('10.0.0.21'))
        self.assertThat(u, Contains('10.0.0.254'))
        self.assertThat(u, Not(Contains('10.0.0.255')))

    def test__deals_with_small_gaps(self):
        s = MAASIPSet(['10.0.0.2', '10.0.0.4', '10.0.0.6', '10.0.0.8'])
        u = s.get_unused_ranges('10.0.0.0/24')
        self.assertThat(u, Not(Contains('10.0.0.0')))
        self.assertThat(u, Contains('10.0.0.1'))
        self.assertThat(u, Not(Contains('10.0.0.2')))
        self.assertThat(u, Contains('10.0.0.3'))
        self.assertThat(u, Not(Contains('10.0.0.4')))
        self.assertThat(u, Contains('10.0.0.5'))
        self.assertThat(u, Not(Contains('10.0.0.6')))
        self.assertThat(u, Contains('10.0.0.7'))
        self.assertThat(u, Not(Contains('10.0.0.8')))
        self.assertThat(u, Contains('10.0.0.9'))
        self.assertThat(u, Contains('10.0.0.254'))
        self.assertThat(u, Not(Contains('10.0.0.255')))

    def test__calculates_ipv6_unused_range(self):
        addr1 = 'fe80::1'
        addr2 = IPAddress('fe80::2')
        range1 = make_iprange('fe80::3', purpose="DNS")
        range2 = make_iprange(
            'fe80::100', 'fe80::ffff:ffff:ffff:fffe', purpose='DHCP')
        s = MAASIPSet([range2, range1, addr1, addr2])
        u = s.get_unused_ranges('fe80::/64')
        self.assertThat(u, Not(Contains('fe80::1')))
        self.assertThat(u, Not(Contains('fe80::2')))
        self.assertThat(u, Not(Contains('fe80::3')))
        self.assertThat(u, Not(Contains('fe80::100')))
        self.assertThat(u, Not(Contains('fe80::ffff:ffff:ffff:fffe')))
        self.assertThat(u, Contains('fe80::ffff:ffff:ffff:ffff'))
        self.assertThat(u, Contains('fe80::5'))
        self.assertThat(u, Contains('fe80::50'))
        self.assertThat(u, Contains('fe80::99'))
        self.assertThat(u, Contains('fe80::ff'))

    def test__calculates_ipv6_unused_range_for_huge_range(self):
        addr1 = 'fe80::1'
        addr2 = IPAddress('fe80::2')
        range1 = make_iprange('fe80::3', purpose="DNS")
        range2 = make_iprange(
            'fe80::100', 'fe80::ffff:ffff:ffff:fffe', purpose='DHCP')
        s = MAASIPSet([range2, range1, addr1, addr2])
        u = s.get_unused_ranges('fe80::/32')
        self.assertThat(u, Not(Contains('fe80::1')))
        self.assertThat(u, Not(Contains('fe80::2')))
        self.assertThat(u, Not(Contains('fe80::3')))
        self.assertThat(u, Not(Contains('fe80::100')))
        self.assertThat(u, Not(Contains('fe80::ffff:ffff:ffff:fffe')))
        self.assertThat(u, Contains('fe80::ffff:ffff:ffff:ffff'))
        self.assertThat(u, Contains('fe80::5'))
        self.assertThat(u, Contains('fe80::50'))
        self.assertThat(u, Contains('fe80::99'))
        self.assertThat(u, Contains('fe80::ff'))
        self.assertThat(u, Contains('fe80:0:ffff:ffff:ffff:ffff:ffff:ffff'))

    def test__calculates_full_range(self):
        s = MAASIPSet(['10.0.0.2', '10.0.0.4', '10.0.0.6', '10.0.0.8'])
        u = s.get_full_range('10.0.0.0/24')
        for ip in range(1, 254):
            self.assertThat(u, Contains("10.0.0.%d" % ip))
        self.assertThat(u['10.0.0.1'].purpose, Contains('unused'))
        self.assertThat(u['10.0.0.2'].purpose, Not(Contains('unused')))
        self.assertThat(u['10.0.0.254'].purpose, Contains('unused'))


class TestIPRangeStatistics(MAASTestCase):

    def test__statistics_are_accurate(self):
        s = MAASIPSet(['10.0.0.2', '10.0.0.4', '10.0.0.6', '10.0.0.8'])
        u = s.get_full_range('10.0.0.0/24')
        stats = IPRangeStatistics(u)
        json = stats.render_json()
        self.assertThat(json['num_available'], Equals(250))
        self.assertThat(json['largest_available'], Equals(246))
        self.assertThat(json['num_unavailable'], Equals(4))
        self.assertThat(json['usage'], Equals(float(4) / float(254)))
        self.assertThat(json['usage_string'], Equals("2%"))
        self.assertThat(json['available_string'], Equals("98%"))
        self.assertThat(json, Not(Contains("ranges")))

    def test__statistics_are_accurate_and_ranges_are_returned_if_desired(self):
        s = MAASIPSet(['10.0.0.2', '10.0.0.4', '10.0.0.6', '10.0.0.8'])
        u = s.get_full_range('10.0.0.0/24')
        stats = IPRangeStatistics(u)
        json = stats.render_json(include_ranges=True)
        self.assertThat(json['num_available'], Equals(250))
        self.assertThat(json['largest_available'], Equals(246))
        self.assertThat(json['num_unavailable'], Equals(4))
        self.assertThat(json['usage'], Equals(float(4) / float(254)))
        self.assertThat(json['usage_string'], Equals('2%'))
        self.assertThat(json['available_string'], Equals("98%"))
        self.assertThat(json, Contains('ranges'))
        self.assertThat(json['ranges'], Equals(stats.ranges.render_json()))

    def test__statistics_are_accurate_for_full_slash_32(self):
        s = MAASIPSet(['10.0.0.1'])
        u = s.get_full_range('10.0.0.1/32')
        stats = IPRangeStatistics(u)
        json = stats.render_json()
        self.assertThat(json['num_available'], Equals(0))
        self.assertThat(json['largest_available'], Equals(0))
        self.assertThat(json['num_unavailable'], Equals(1))
        self.assertThat(json['usage'], Equals(float(1) / float(1)))
        self.assertThat(json['usage_string'], Equals("100%"))
        self.assertThat(json['available_string'], Equals("0%"))
        self.assertThat(json, Not(Contains("ranges")))

    def test__statistics_are_accurate_for_empty_slash_32(self):
        s = MAASIPSet([])
        u = s.get_full_range('10.0.0.1/32')
        stats = IPRangeStatistics(u)
        json = stats.render_json()
        self.assertThat(json['num_available'], Equals(1))
        self.assertThat(json['largest_available'], Equals(1))
        self.assertThat(json['num_unavailable'], Equals(0))
        self.assertThat(json['usage'], Equals(float(0) / float(1)))
        self.assertThat(json['usage_string'], Equals("0%"))
        self.assertThat(json['available_string'], Equals("100%"))
        self.assertThat(json, Not(Contains("ranges")))

    def test__statistics_are_accurate_for_full_slash_128(self):
        s = MAASIPSet(['2001:db8::1'])
        u = s.get_full_range('2001:db8::1/128')
        stats = IPRangeStatistics(u)
        json = stats.render_json()
        self.assertThat(json['num_available'], Equals(0))
        self.assertThat(json['largest_available'], Equals(0))
        self.assertThat(json['num_unavailable'], Equals(1))
        self.assertThat(json['usage'], Equals(float(1) / float(1)))
        self.assertThat(json['usage_string'], Equals("100%"))
        self.assertThat(json['available_string'], Equals("0%"))
        self.assertThat(json, Not(Contains("ranges")))

    def test__statistics_are_accurate_for_empty_slash_128(self):
        s = MAASIPSet([])
        u = s.get_full_range('2001:db8::1/128')
        stats = IPRangeStatistics(u)
        json = stats.render_json()
        self.assertThat(json['num_available'], Equals(1))
        self.assertThat(json['largest_available'], Equals(1))
        self.assertThat(json['num_unavailable'], Equals(0))
        self.assertThat(json['usage'], Equals(float(0) / float(1)))
        self.assertThat(json['usage_string'], Equals("0%"))
        self.assertThat(json['available_string'], Equals("100%"))
        self.assertThat(json, Not(Contains("ranges")))

    def test__statistics_are_accurate_for_empty_slash_127(self):
        s = MAASIPSet([])
        u = s.get_full_range('2001:db8::1/127')
        stats = IPRangeStatistics(u)
        json = stats.render_json()
        self.assertThat(json['num_available'], Equals(2))
        self.assertThat(json['largest_available'], Equals(2))
        self.assertThat(json['num_unavailable'], Equals(0))
        self.assertThat(json['usage'], Equals(float(0) / float(2)))
        self.assertThat(json['usage_string'], Equals("0%"))
        self.assertThat(json['available_string'], Equals("100%"))
        self.assertThat(json, Not(Contains("ranges")))

    def test__statistics_are_accurate_for_empty_slash_31(self):
        s = MAASIPSet([])
        u = s.get_full_range('10.0.0.0/31')
        stats = IPRangeStatistics(u)
        json = stats.render_json()
        self.assertThat(json['num_available'], Equals(2))
        self.assertThat(json['largest_available'], Equals(2))
        self.assertThat(json['num_unavailable'], Equals(0))
        self.assertThat(json['usage'], Equals(float(0) / float(2)))
        self.assertThat(json['usage_string'], Equals("0%"))
        self.assertThat(json['available_string'], Equals("100%"))
        self.assertThat(json, Not(Contains("ranges")))

    def test__suggests_subnet_anycast_address_for_ipv6(self):
        s = MAASIPSet([])
        u = s.get_full_range('2001:db8::/64')
        stats = IPRangeStatistics(u)
        self.assertThat(stats.suggested_gateway, Equals("2001:db8::"))

    def test__suggests_first_ip_as_default_gateway_if_available(self):
        s = MAASIPSet(['10.0.0.2', '10.0.0.4', '10.0.0.6', '10.0.0.8'])
        u = s.get_full_range('10.0.0.0/24')
        stats = IPRangeStatistics(u)
        self.assertThat(stats.suggested_gateway, Equals("10.0.0.1"))

    def test__suggests_last_ip_as_default_gateway_if_needed(self):
        s = MAASIPSet(['10.0.0.1', '10.0.0.4', '10.0.0.6', '10.0.0.8'])
        u = s.get_full_range('10.0.0.0/24')
        stats = IPRangeStatistics(u)
        self.assertThat(stats.suggested_gateway, Equals("10.0.0.254"))

    def test__suggests_first_available_ip_as_default_gateway_if_needed(self):
        s = MAASIPSet(['10.0.0.1', '10.0.0.4', '10.0.0.6', '10.0.0.254'])
        u = s.get_full_range('10.0.0.0/24')
        stats = IPRangeStatistics(u)
        self.assertThat(stats.suggested_gateway, Equals("10.0.0.2"))

    def test__suggests_no_gateway_if_range_full(self):
        s = MAASIPSet(['10.0.0.1'])
        u = s.get_full_range('10.0.0.1/32')
        stats = IPRangeStatistics(u)
        self.assertThat(stats.suggested_gateway, Is(None))

    def test__suggests_no_dynamic_range_if_dynamic_range_exists(self):
        s = MAASIPSet([
            MAASIPRange(start="10.0.0.2", end="10.0.0.99", purpose="dynamic")])
        u = s.get_full_range('10.0.0.0/24')
        stats = IPRangeStatistics(u)
        json = stats.render_json(include_suggestions=True)
        self.assertThat(stats.suggested_dynamic_range, Is(None))
        self.assertThat(json["suggested_dynamic_range"], Is(None))

    def test__suggests_upper_one_fourth_range_for_dynamic_by_default(self):
        s = MAASIPSet([])
        u = s.get_full_range('10.0.0.0/24')
        stats = IPRangeStatistics(u)
        self.assertThat(stats.suggested_gateway, Equals("10.0.0.1"))
        self.assertThat(stats.suggested_dynamic_range, HasLength(64))
        self.assertThat(stats.suggested_dynamic_range, Contains("10.0.0.191"))
        self.assertThat(stats.suggested_dynamic_range, Contains("10.0.0.254"))
        self.assertThat(
            stats.suggested_dynamic_range, Not(Contains("10.0.0.255")))
        self.assertThat(
            stats.suggested_dynamic_range, Not(Contains("10.0.0.190")))

    def test__suggests_half_available_if_available_less_than_one_fourth(self):
        s = MAASIPSet([MAASIPRange("10.0.0.2", "10.0.0.205")])
        u = s.get_full_range('10.0.0.0/24')
        stats = IPRangeStatistics(u)
        self.assertThat(stats.suggested_gateway, Equals("10.0.0.1"))
        self.assertThat(stats.num_available, Equals(50))
        self.assertThat(stats.suggested_dynamic_range, HasLength(25))
        self.assertThat(stats.suggested_dynamic_range, Contains("10.0.0.230"))
        self.assertThat(stats.suggested_dynamic_range, Contains("10.0.0.254"))
        self.assertThat(
            stats.suggested_dynamic_range, Not(Contains("10.0.0.255")))
        self.assertThat(
            stats.suggested_dynamic_range, Not(Contains("10.0.0.229")))

    def test__suggested_range_excludes_suggested_gateway(self):
        s = MAASIPSet([MAASIPRange("10.0.0.1", "10.0.0.204")])
        u = s.get_full_range('10.0.0.0/24')
        stats = IPRangeStatistics(u)
        self.assertThat(stats.suggested_gateway, Equals("10.0.0.254"))
        self.assertThat(stats.num_available, Equals(50))
        self.assertThat(stats.suggested_dynamic_range, HasLength(25))
        self.assertThat(stats.suggested_dynamic_range, Contains("10.0.0.229"))
        self.assertThat(stats.suggested_dynamic_range, Contains("10.0.0.253"))
        self.assertThat(
            stats.suggested_dynamic_range, Not(Contains("10.0.0.255")))
        self.assertThat(
            stats.suggested_dynamic_range, Not(Contains("10.0.0.228")))

    def test__suggested_range_excludes_suggested_gateway_when_gw_first(self):
        s = MAASIPSet([MAASIPRange("10.0.0.1", "10.0.0.203"), "10.0.0.254"])
        u = s.get_full_range('10.0.0.0/24')
        stats = IPRangeStatistics(u)
        self.assertThat(stats.suggested_gateway, Equals("10.0.0.204"))
        self.assertThat(stats.num_available, Equals(50))
        self.assertThat(stats.suggested_dynamic_range, HasLength(25))
        self.assertThat(stats.suggested_dynamic_range, Contains("10.0.0.229"))
        self.assertThat(stats.suggested_dynamic_range, Contains("10.0.0.253"))
        self.assertThat(
            stats.suggested_dynamic_range, Not(Contains("10.0.0.255")))
        self.assertThat(
            stats.suggested_dynamic_range, Not(Contains("10.0.0.228")))

    def test__suggests_upper_one_fourth_range_for_ipv6(self):
        s = MAASIPSet([])
        u = s.get_full_range('2001:db8::/64')
        stats = IPRangeStatistics(u)
        self.assertThat(stats.suggested_gateway, Equals("2001:db8::"))
        self.assertEqual((2 ** 64) >> 2, stats.suggested_dynamic_range.size)
        self.assertThat(
            stats.suggested_dynamic_range, Contains(
                "2001:db8:0:0:c000::"))
        self.assertThat(
            stats.suggested_dynamic_range, Contains(
                "2001:db8::ffff:ffff:ffff:ffff"))
        self.assertThat(
            stats.suggested_dynamic_range, Not(Contains("2001:db8::1")))
        self.assertThat(
            stats.suggested_dynamic_range, Not(Contains(
                "2001:db8::bfff:ffff:ffff:ffff")))

    def test__suggests_half_available_for_ipv6(self):
        s = MAASIPSet([MAASIPRange(
            "2001:db8::1", "2001:db8::ffff:ffff:ffff:ff00")])
        u = s.get_full_range('2001:db8::/64')
        stats = IPRangeStatistics(u)
        self.assertThat(stats.suggested_gateway, Equals("2001:db8::"))
        self.assertThat(stats.num_available, Equals(255))
        self.assertThat(stats.suggested_dynamic_range, HasLength(127))
        self.assertThat(
            stats.suggested_dynamic_range, Contains(
                "2001:db8::ffff:ffff:ffff:ff81"))
        self.assertThat(
            stats.suggested_dynamic_range, Contains(
                "2001:db8::ffff:ffff:ffff:ffff"))
        self.assertThat(
            stats.suggested_dynamic_range, Not(Contains("2001:db8::1")))
        self.assertThat(
            stats.suggested_dynamic_range, Not(Contains(
                "2001:db8::ffff:ffff:ffff:ff80")))


class TestParseInteger(MAASTestCase):

    def test__parses_decimal_integer(self):
        self.assertThat(parse_integer("0"), Equals(0))
        self.assertThat(parse_integer("1"), Equals(1))
        self.assertThat(parse_integer("-1"), Equals(-1))
        self.assertThat(parse_integer("1000"), Equals(1000))
        self.assertThat(parse_integer("10000000"), Equals(10000000))

    def test__parses_hexadecimal_integer(self):
        self.assertThat(parse_integer("0x0"), Equals(0))
        self.assertThat(parse_integer("0x1"), Equals(1))
        self.assertThat(parse_integer("0x1000"), Equals(0x1000))
        self.assertThat(parse_integer("0x10000000"), Equals(0x10000000))

    def test__parses_binary_integer(self):
        self.assertThat(parse_integer("0b0"), Equals(0))
        self.assertThat(parse_integer("0b1"), Equals(1))
        self.assertThat(parse_integer("0b1000"), Equals(0b1000))
        self.assertThat(parse_integer("0b10000000"), Equals(0b10000000))


class TestGetAllInterfacesDefinition(MAASTestCase):
    """Tests for `get_all_interfaces_definition` and all helper methods."""

    def assertInterfacesResult(
            self, ip_addr, iproute_info, dhclient_info, expected_results,
            in_container=False):
        self.patch(network_module, "get_ip_addr").return_value = ip_addr
        self.patch(network_module, "get_ip_route").return_value = iproute_info
        self.patch(
            network_module, "get_dhclient_info").return_value = dhclient_info
        self.patch(
            network_module, "running_in_container").return_value = in_container
        observed_result = get_all_interfaces_definition()
        self.assertThat(observed_result, expected_results)

    def test__ignores_loopback(self):
        ip_addr = {
            "vnet": {
                "type": "loopback",
                "flags": ["UP"],
                "inet": ["127.0.0.1/32"],
                "inet6": ["::1"],
            },
        }
        self.assertInterfacesResult(ip_addr, {}, {}, MatchesDict({}))

    def test__ignores_ethernet(self):
        ip_addr = {
            "vnet": {
                "type": "ethernet",
                "mac": factory.make_mac_address(),
                "flags": ["UP"],
                "inet": ["192.168.122.2/24"],
            },
        }
        self.assertInterfacesResult(ip_addr, {}, {}, MatchesDict({}))

    def test__ignores_ipip(self):
        ip_addr = {
            "vnet": {
                "type": "ipip",
                "flags": ["UP"],
            },
        }
        self.assertInterfacesResult(ip_addr, {}, {}, MatchesDict({}))

    def test__simple(self):
        ip_addr = {
            "eth0": {
                "type": "ethernet.physical",
                "mac": factory.make_mac_address(),
                "flags": ["UP"],
                "inet": ["192.168.122.2/24"],
            },
        }
        expected_result = MatchesDict({
            "eth0": MatchesDict({
                "type": Equals("physical"),
                "mac_address": Equals(ip_addr["eth0"]["mac"]),
                "enabled": Is(True),
                "parents": Equals([]),
                "links": Equals([{
                    "mode": "static",
                    "address": "192.168.122.2/24",
                }]),
                "source": Equals("ipaddr"),
            }),
        })
        self.assertInterfacesResult(ip_addr, {}, {}, expected_result)

    def test__simple_with_default_gateway(self):
        ip_addr = {
            "eth0": {
                "type": "ethernet.physical",
                "mac": factory.make_mac_address(),
                "flags": ["UP"],
                "inet": ["192.168.122.2/24"],
            },
        }
        iproute_info = {
            "default": {
                "via": "192.168.122.1",
            }
        }
        expected_result = MatchesDict({
            "eth0": MatchesDict({
                "type": Equals("physical"),
                "mac_address": Equals(ip_addr["eth0"]["mac"]),
                "enabled": Is(True),
                "parents": Equals([]),
                "links": Equals([{
                    "mode": "static",
                    "address": "192.168.122.2/24",
                    "gateway": "192.168.122.1",
                }]),
                "source": Equals("ipaddr"),
            }),
        })
        self.assertInterfacesResult(ip_addr, iproute_info, {}, expected_result)

    def test__doesnt_ignore_ethernet_in_container(self):
        ip_addr = {
            "eth0": {
                "type": "ethernet",
                "mac": factory.make_mac_address(),
                "flags": ["UP"],
                "inet": ["192.168.122.2/24"],
            },
        }
        expected_result = MatchesDict({
            "eth0": MatchesDict({
                "type": Equals("physical"),
                "mac_address": Equals(ip_addr["eth0"]["mac"]),
                "enabled": Is(True),
                "parents": Equals([]),
                "links": Equals([{
                    "mode": "static",
                    "address": "192.168.122.2/24",
                }]),
                "source": Equals("ipaddr"),
            }),
        })
        self.assertInterfacesResult(
            ip_addr, {}, {}, expected_result, in_container=True)

    def test__simple_with_dhcp(self):
        ip_addr = {
            "eth0": {
                "type": "ethernet.physical",
                "mac": factory.make_mac_address(),
                "flags": ["UP"],
                "inet": ["192.168.122.2/24", "192.168.122.200/32"],
            },
        }
        dhclient_info = {
            "eth0": "192.168.122.2",
        }
        expected_result = MatchesDict({
            "eth0": MatchesDict({
                "type": Equals("physical"),
                "mac_address": Equals(ip_addr["eth0"]["mac"]),
                "enabled": Is(True),
                "parents": Equals([]),
                "links": MatchesSetwise(
                    MatchesDict({
                        "mode": Equals("dhcp"),
                        "address": Equals("192.168.122.2/24"),
                    }),
                    MatchesDict({
                        "mode": Equals("static"),
                        "address": Equals("192.168.122.200/24"),
                    }),
                ),
                "source": Equals("ipaddr"),
            }),
        })
        self.assertInterfacesResult(
            ip_addr, {}, dhclient_info, expected_result)

    def test__fixing_links(self):
        ip_addr = {
            "eth0": {
                "type": "ethernet.physical",
                "mac": factory.make_mac_address(),
                "flags": ["UP"],
                "inet": [
                    "192.168.122.2/24",
                    "192.168.122.3/32",
                    "192.168.123.3/32",
                ],
                "inet6": [
                    "2001:db8:a0b:12f0::1/96",
                    "2001:db8:a0b:12f0::2/128",
                ]
            },
        }
        expected_result = MatchesDict({
            "eth0": MatchesDict({
                "type": Equals("physical"),
                "mac_address": Equals(ip_addr["eth0"]["mac"]),
                "enabled": Is(True),
                "parents": Equals([]),
                "links": MatchesSetwise(
                    MatchesDict({
                        "mode": Equals("static"),
                        "address": Equals("192.168.122.2/24"),
                    }),
                    MatchesDict({
                        "mode": Equals("static"),
                        "address": Equals("192.168.122.3/24"),
                    }),
                    MatchesDict({
                        "mode": Equals("static"),
                        "address": Equals("192.168.123.3/32"),
                    }),
                    MatchesDict({
                        "mode": Equals("static"),
                        "address": Equals("2001:db8:a0b:12f0::1/96"),
                    }),
                    MatchesDict({
                        "mode": Equals("static"),
                        "address": Equals("2001:db8:a0b:12f0::2/96"),
                    }),
                ),
                "source": Equals("ipaddr"),
            }),
        })
        self.assertInterfacesResult(ip_addr, {}, {}, expected_result)

    def test__complex(self):
        ip_addr = {
            "eth0": {
                "type": "ethernet.physical",
                "mac": factory.make_mac_address(),
                "flags": [],
            },
            "eth1": {
                "type": "ethernet.physical",
                "mac": factory.make_mac_address(),
                "flags": ["UP"],
            },
            "eth2": {
                "type": "ethernet.physical",
                "mac": factory.make_mac_address(),
                "flags": ["UP"],
            },
            "bond0": {
                "type": "ethernet.bond",
                "mac": factory.make_mac_address(),
                "flags": ["UP"],
                "bonded_interfaces": ["eth1", "eth2"],
                "inet": ["192.168.122.2/24", "192.168.122.3/32"],
                "inet6": ["2001:db8::3:2:2/96"],
            },
            "bond0.10": {
                "type": "ethernet.vlan",
                "flags": ["UP"],
                "vid": 10,
                "inet": ["192.168.123.2/24", "192.168.123.3/32"],
                "parent": "bond0",
            },
            "vlan20": {
                "type": "ethernet.vlan",
                "mac": factory.make_mac_address(),
                "flags": ["UP"],
                "vid": 20,
                "parent": "eth0",
            },
            "wlan0": {
                "type": "ethernet.wireless",
                "mac": factory.make_mac_address(),
                "flags": ["UP"],
            },
            "br0": {
                "type": "ethernet.bridge",
                "bridged_interfaces": ["eth0"],
                "mac": factory.make_mac_address(),
                "flags": ["UP"],
                "inet": ["192.168.124.2/24"],
            },
        }
        iproute_info = {
            "default": {
                "via": "192.168.122.1",
            },
            "192.168.124.0/24": {
                "via": "192.168.124.1",
            }
        }
        expected_result = MatchesDict({
            "eth0": MatchesDict({
                "type": Equals("physical"),
                "mac_address": Equals(ip_addr["eth0"]["mac"]),
                "enabled": Is(False),
                "parents": Equals([]),
                "links": Equals([]),
                "source": Equals("ipaddr"),
            }),
            "eth1": MatchesDict({
                "type": Equals("physical"),
                "mac_address": Equals(ip_addr["eth1"]["mac"]),
                "enabled": Is(True),
                "parents": Equals([]),
                "links": Equals([]),
                "source": Equals("ipaddr"),
            }),
            "eth2": MatchesDict({
                "type": Equals("physical"),
                "mac_address": Equals(ip_addr["eth2"]["mac"]),
                "enabled": Is(True),
                "parents": Equals([]),
                "links": Equals([]),
                "source": Equals("ipaddr"),
            }),
            "bond0": MatchesDict({
                "type": Equals("bond"),
                "mac_address": Equals(ip_addr["bond0"]["mac"]),
                "enabled": Is(True),
                "parents": Equals(["eth1", "eth2"]),
                "links": MatchesSetwise(
                    MatchesDict({
                        "mode": Equals("static"),
                        "address": Equals("192.168.122.2/24"),
                        "gateway": Equals("192.168.122.1"),
                    }),
                    MatchesDict({
                        "mode": Equals("static"),
                        "address": Equals("192.168.122.3/24"),
                        "gateway": Equals("192.168.122.1"),
                    }),
                    MatchesDict({
                        "mode": Equals("static"),
                        "address": Equals("2001:db8::3:2:2/96"),
                    }),
                ),
                "source": Equals("ipaddr"),
            }),
            "bond0.10": MatchesDict({
                "type": Equals("vlan"),
                "enabled": Is(True),
                "parents": Equals(["bond0"]),
                "vid": Equals(10),
                "links": MatchesSetwise(
                    MatchesDict({
                        "mode": Equals("static"),
                        "address": Equals("192.168.123.2/24"),
                    }),
                    MatchesDict({
                        "mode": Equals("static"),
                        "address": Equals("192.168.123.3/24"),
                    }),
                ),
                "source": Equals("ipaddr"),
            }),
            "wlan0": MatchesDict({
                "type": Equals("physical"),
                "mac_address": Equals(ip_addr["wlan0"]["mac"]),
                "enabled": Is(True),
                "parents": Equals([]),
                "links": Equals([]),
                "source": Equals("ipaddr"),
            }),
            "vlan20": MatchesDict({
                "type": Equals("vlan"),
                "enabled": Is(True),
                "parents": Equals(["eth0"]),
                "links": Equals([]),
                "source": Equals("ipaddr"),
                "vid": Equals(20),
            }),
            "br0": MatchesDict({
                "type": Equals("bridge"),
                "mac_address": Equals(ip_addr["br0"]["mac"]),
                "enabled": Is(True),
                "parents": Equals(["eth0"]),
                "links": Equals([{
                    "mode": "static",
                    "address": "192.168.124.2/24",
                    "gateway": "192.168.124.1",
                }]),
                "source": Equals("ipaddr"),
            }),
        })
        self.assertInterfacesResult(ip_addr, iproute_info, {}, expected_result)


class TestGetInterfaceChildren(MAASTestCase):
    """Tests for `get_interface_children()`."""

    def test__calculates_children_from_bond_parents(self):
        interfaces = {
            'eth0': {
                'parents': [],
            },
            'eth1': {
                'parents': [],
            },
            'bond0': {
                'parents': ['eth0', 'eth1'],
            },
        }
        children_map = get_interface_children(interfaces)
        self.assertThat(children_map, Equals({
            'eth0': {'bond0'},
            'eth1': {'bond0'},
        }))

    def test__calculates_children_from_vlan_parents(self):
        interfaces = {
            'eth0': {
                'parents': [],
            },
            'eth1': {
                'parents': [],
            },
            'eth0.100': {
                'parents': ['eth0'],
            },
            'eth1.100': {
                'parents': ['eth1'],
            },
        }
        children_map = get_interface_children(interfaces)
        self.assertThat(children_map, Equals({
            'eth0': {'eth0.100'},
            'eth1': {'eth1.100'},
        }))

    def test__calculates_children_from_bond_and_vlan_parents(self):
        interfaces = {
            'eth0': {
                'parents': [],
            },
            'eth1': {
                'parents': [],
            },
            'eth0.100': {
                'parents': ['eth0'],
            },
            'eth1.100': {
                'parents': ['eth1'],
            },
            'bond0': {
                'parents': ['eth0', 'eth1'],
            },
        }
        children_map = get_interface_children(interfaces)
        self.assertThat(children_map, Equals({
            'eth0': {'eth0.100', 'bond0'},
            'eth1': {'eth1.100', 'bond0'},
        }))


class TestInterfaceChildren(MAASTestCase):
    """Tests for `interface_children()`."""

    def test__yields_each_child(self):
        interfaces = {
            'eth0': {
                'parents': [],
            },
            'eth1': {
                'parents': [],
            },
            'eth0.100': {
                'parents': ['eth0'],
            },
            'eth1.100': {
                'parents': ['eth1'],
            },
            'bond0': {
                'parents': ['eth0', 'eth1'],
            },
        }
        children_map = get_interface_children(interfaces)
        eth0_children = list(
            interface_children('eth0', interfaces, children_map))
        self.assertItemsEqual(eth0_children, [
            ('eth0.100', {'parents': ['eth0']}),
            ('bond0', {'parents': ['eth0', 'eth1']}),
        ])
        eth1_children = list(
            interface_children('eth1', interfaces, children_map))
        self.assertItemsEqual(eth1_children, [
            ('eth1.100', {'parents': ['eth1']}),
            ('bond0', {'parents': ['eth0', 'eth1']}),
        ])

    def test__returns_namedtuple(self):
        interfaces = {
            'eth0': {
                'parents': [],
            },
            'eth0.100': {
                'parents': ['eth0'],
            },
        }
        children_map = get_interface_children(interfaces)
        eth0_children = list(
            interface_children('eth0', interfaces, children_map))
        self.assertThat(eth0_children[0].name, Equals("eth0.100"))
        self.assertThat(eth0_children[0].data, Equals({'parents': ['eth0']}))


class TestIsLoopbackAddress(MAASTestCase):
    def test_handles_ipv4_loopback(self):
        network = IPNetwork('127.0.0.0/8')
        address = factory.pick_ip_in_network(network)
        self.assertEqual(is_loopback_address(address), True)

    def test_handles_ipv6_loopback(self):
        address = '::1'
        self.assertEqual(is_loopback_address(address), True)

    def test_handles_random_ipv4_address(self):
        address = factory.make_ipv4_address()
        self.assertEqual(
            is_loopback_address(address), IPAddress(address).is_loopback())

    def test_handles_random_ipv6_address(self):
        address = factory.make_ipv6_address()
        self.assertEqual(
            is_loopback_address(address), IPAddress(address).is_loopback())

    def test_handles_ipv6_format_ipv4_loopback(self):
        network = IPNetwork('127.0.0.0/8')
        address = factory.pick_ip_in_network(network)
        self.assertEqual(is_loopback_address("::ffff:%s" % address), True)

    def test_handles_ipv6_format_ipv4_nonloopback(self):
        address = factory.make_ipv4_address()
        self.assertEqual(
            is_loopback_address("::ffff:%s" % address),
            IPAddress(address).is_loopback())

    def test_does_not_resolve_hostnames(self):
        gai = self.patch(socket, 'getaddrinfo')
        gai.return_value = ((
            socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, '',
            ('::1', None, 0, 1)),)
        name = factory.make_name('name')
        self.assertEqual(is_loopback_address(name), False)
        self.assertThat(gai, MockNotCalled())

    def test_handles_localhost(self):
        gai = self.patch(socket, 'getaddrinfo')
        gai.return_value = ((
            socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, '',
            ('2001:db8::1', None, 0, 1)),)
        self.assertEqual(is_loopback_address('localhost'), True)
        self.assertThat(gai, MockNotCalled())


class TestResolvesToLoopbackAddress(MAASTestCase):
    def test_resolves_hostnames(self):
        gai = self.patch(socket, 'getaddrinfo')
        gai.return_value = ((
            socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, '',
            ('::1', None, 0, 1)),)
        name = factory.make_name('name')
        self.assertEqual(resolves_to_loopback_address(name), True)
        self.assertThat(
            gai, MockCalledOnceWith(name, None, proto=IPPROTO_TCP))

    def test_resolves_hostnames_non_loopback(self):
        gai = self.patch(socket, 'getaddrinfo')
        gai.return_value = ((
            socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, '',
            ('2001:db8::1', None, 0, 1)),)
        name = factory.make_name('name')
        self.assertEqual(resolves_to_loopback_address(name), False)
        self.assertThat(
            gai, MockCalledOnceWith(name, None, proto=IPPROTO_TCP))
