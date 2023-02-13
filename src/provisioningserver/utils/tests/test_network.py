# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import itertools
import json
import socket
from socket import EAI_BADFLAGS, EAI_NODATA, EAI_NONAME, gaierror, IPPROTO_TCP
from typing import List
from unittest import mock, TestCase
from unittest.mock import Mock

from netaddr import EUI, IPAddress, IPNetwork, IPRange
import netifaces
from netifaces import AF_INET, AF_INET6, AF_LINK
from testtools import ExpectedException
from testtools.matchers import (
    ContainsAll,
    Equals,
    HasLength,
    Is,
    MatchesDict,
    MatchesSetwise,
    Not,
    StartsWith,
)
from twisted.internet.defer import inlineCallbacks, succeed
from twisted.names.error import (
    AuthoritativeDomainError,
    DNSQueryTimeoutError,
    DomainError,
    ResolverError,
)

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.matchers import (
    IsNonEmptyString,
    MockCalledOnce,
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.runtest import MAASTwistedRunTest
from maastesting.testcase import MAASTestCase
import provisioningserver.utils
from provisioningserver.utils import network as network_module
from provisioningserver.utils.network import (
    annotate_with_default_monitored_interfaces,
    bytes_to_hex,
    bytes_to_int,
    clean_up_netifaces_address,
    coerce_to_valid_hostname,
    convert_host_to_uri_str,
    enumerate_assigned_ips,
    enumerate_ipv4_addresses,
    find_ip_via_arp,
    find_mac_via_arp,
    fix_link_addresses,
    format_eui,
    generate_mac_address,
    get_all_addresses_for_interface,
    get_all_interface_addresses,
    get_all_interface_source_addresses,
    get_all_interface_subnets,
    get_all_interfaces_definition,
    get_default_monitored_interfaces,
    get_eui_organization,
    get_ifname_for_label,
    get_ifname_ifdata_for_destination,
    get_interface_children,
    get_mac_organization,
    get_source_address,
    has_ipv4_address,
    hex_str_to_bytes,
    inet_ntop,
    interface_children,
    intersect_iprange,
    ip_range_within_network,
    IPRangeStatistics,
    is_loopback_address,
    is_mac,
    LOOPBACK_INTERFACE_INFO,
    MAASIPRange,
    MAASIPSet,
    make_iprange,
    make_network,
    parse_integer,
    preferred_hostnames_sort_key,
    resolve_host_to_addrinfo,
    resolve_hostname,
    resolves_to_loopback_address,
    reverseResolve,
)
from provisioningserver.utils.shell import get_env_with_locale


class TestFixLinkAddresses(TestCase):
    def test_fixes_with_cidr(self):
        links = [
            {"address": "1.2.3.1/24", "mode": "static"},
            {"address": "1.2.3.4/32", "mode": "static"},
            {"address": "2001::1/96", "mode": "static"},
            {"address": "2001::123/128", "mode": "static"},
        ]
        fix_link_addresses(links)
        self.assertEqual(
            links,
            [
                {"address": "1.2.3.1/24", "mode": "static"},
                {"address": "1.2.3.4/24", "mode": "static"},
                {"address": "2001::1/96", "mode": "static"},
                {"address": "2001::123/96", "mode": "static"},
            ],
        )

    def test_fixes_with_netmask(self):
        links = [
            {"address": "1.2.3.1", "netmask": 24, "mode": "static"},
            {"address": "1.2.3.4", "netmask": 32, "mode": "static"},
            {"address": "2001::1", "netmask": 96, "mode": "static"},
            {"address": "2001::123", "netmask": 128, "mode": "static"},
        ]
        fix_link_addresses(links)
        self.assertEqual(
            links,
            [
                {"address": "1.2.3.1", "netmask": 24, "mode": "static"},
                {"address": "1.2.3.4", "netmask": 24, "mode": "static"},
                {"address": "2001::1", "netmask": 96, "mode": "static"},
                {"address": "2001::123", "netmask": 96, "mode": "static"},
            ],
        )


class TestMakeNetwork(MAASTestCase):
    def test_constructs_IPNetwork(self):
        network = make_network("10.22.82.0", 24)
        self.assertIsInstance(network, IPNetwork)
        self.assertEqual(IPNetwork("10.22.82.0/24"), network)

    def test_passes_args_to_IPNetwork(self):
        self.patch(network_module, "IPNetwork")
        make_network("10.1.2.0", 24, foo=9)
        self.assertEqual(
            [mock.call("10.1.2.0/24", foo=9)],
            network_module.IPNetwork.mock_calls,
        )


class TestInetNtop(MAASTestCase):
    def test_ipv4(self):
        ip = factory.make_ipv4_address()
        self.assertEqual(ip, inet_ntop(IPAddress(ip).value))

    def test_ipv6(self):
        ip = factory.make_ipv6_address()
        self.assertEqual(ip, inet_ntop(IPAddress(ip).value))


class TestConversionFunctions(MAASTestCase):
    def test_bytes_to_hex(self):
        self.assertEqual(b"01ff", bytes_to_hex(b"\x01\xff"))
        self.assertEqual(b"0001ff", bytes_to_hex(b"\x00\x01\xff"))

    def test_bytes_to_int(self):
        self.assertEqual(65535, bytes_to_int(b"\xff\xff"))
        self.assertEqual(16777215, bytes_to_int(b"\xff\xff\xff"))
        self.assertEqual(
            281474976710655, bytes_to_int(b"\xff\xff\xff\xff\xff\xff")
        )

    def test_hex_str_to_bytes(self):
        self.assertEqual(b"\x00\x00", hex_str_to_bytes("0x0000"))
        self.assertEqual(b"\xff\xff", hex_str_to_bytes("ff:ff"))
        self.assertEqual(b"\xff\xff", hex_str_to_bytes("ff ff  "))
        self.assertEqual(b"\xff\xff", hex_str_to_bytes("  ff-ff"))
        self.assertEqual(b"\xff\xff", hex_str_to_bytes("ff-ff"))
        self.assertEqual(b"\xff\xff", hex_str_to_bytes("0xffff"))
        self.assertEqual(b"\xff\xff", hex_str_to_bytes(" 0xffff"))
        self.assertEqual(
            b"\x01\x02\x03\x04\x05\x06",
            hex_str_to_bytes("01:02:03:04:05:06"),
        )
        self.assertEqual(
            b"\x0a\x0b\x0c\x0d\x0e\x0f",
            hex_str_to_bytes("0A:0B:0C:0D:0E:0F"),
        )
        self.assertEqual(
            b"\x0a\x0b\x0c\x0d\x0e\x0f",
            hex_str_to_bytes("0a:0b:0c:0d:0e:0f"),
        )

    def test_format_eui(self):
        self.assertEqual(
            "0a:0b:0c:0d:0e:0f", format_eui(EUI("0A-0B-0C-0D-0E-0F"))
        )


class TestFindIPViaARP(MAASTestCase):
    def patch_call(self, output):
        """Replace `call_and_check` with one that returns `output`."""
        fake = self.patch(network_module, "call_and_check")
        fake.return_value = output.encode("ascii")
        return fake

    def test_resolves_MAC_address_to_IP(self):
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
        self.assertThat(call_and_check, MockCalledOnceWith(["arp", "-n"]))
        self.assertEqual("192.168.0.1", ip_address_observed)

    def test_returns_consistent_output(self):
        mac = factory.make_mac_address()
        ips = ["10.0.0.11", "10.0.0.99"]
        lines = [f"{ip} ether {mac} C eth0" for ip in ips]
        self.patch_call("\n".join(lines))
        one_result = find_ip_via_arp(mac)
        self.patch_call("\n".join(reversed(lines)))
        other_result = find_ip_via_arp(mac)

        self.assertIn(one_result, ips)
        self.assertEqual(one_result, other_result)

    def test_ignores_case(self):
        sample = """\
        192.168.0.1 ether   90:f6:52:f6:17:92   C                     eth0
        """
        self.patch_call(sample)
        ip_address_observed = find_ip_via_arp("90:f6:52:f6:17:92".upper())
        self.assertEqual("192.168.0.1", ip_address_observed)


class TestIsMac(MAASTestCase):
    def test_true(self):
        self.assertTrue(is_mac("aa:bb:cc:dd:ee:ff"))

    def test_false(self):
        self.assertFalse(is_mac(factory.make_name("bad")))


class TestGetMACOrganization(MAASTestCase):
    """Tests for `get_mac_organization()` and `get_eui_organization()`."""

    def test_get_mac_organization(self):
        mac_address = "48:51:b7:00:00:00"
        self.assertThat(get_mac_organization(mac_address), IsNonEmptyString)

    def test_get_eui_organization(self):
        mac_address = "48:51:b7:00:00:00"
        self.assertThat(
            get_eui_organization(EUI(mac_address)), IsNonEmptyString
        )

    def test_get_eui_organization_returns_None_for_UnicodeError(self):
        mock_eui = Mock()
        mock_eui.oui = Mock()
        mock_eui.oui.registration = Mock()
        mock_eui.oui.registration.side_effect = UnicodeError
        organization = get_eui_organization(mock_eui)
        self.assertIsNone(organization)

    def test_get_eui_organization_returns_None_for_IndexError(self):
        mock_eui = Mock()
        mock_eui.oui = Mock()
        mock_eui.oui.registration = Mock()
        mock_eui.oui.registration.side_effect = IndexError
        organization = get_eui_organization(mock_eui)
        self.assertIsNone(organization)

    def test_get_eui_organization_returns_none_for_invalid_mac(self):
        organization = get_eui_organization(EUI("FF:FF:b7:00:00:00"))
        self.assertIsNone(organization)


class TestFindMACViaARP(MAASTestCase):
    def patch_call(self, output):
        """Replace `call_and_check` with one that returns `output`."""
        fake = self.patch(provisioningserver.utils.network, "call_and_check")
        fake.return_value = output.encode("ascii")
        return fake

    def make_output(self, ip=None, mac=None, dev=None, state="REACHABLE"):
        """Compose an `ip --json neigh` output for given `ip` and `mac`."""
        if ip is None:
            ip = factory.make_ipv4_address()
        if mac is None:
            mac = factory.make_mac_address()
        if dev is None:
            dev = factory.make_name("eth", sep="")
        entry = {
            "dst": ip,
            "dev": dev,
            "state": [state],
        }
        if state != "FAILED":
            entry["lladdr"] = mac
        return json.dumps([entry])

    def test_calls_ip_neigh(self):
        call_and_check = self.patch_call("")
        find_mac_via_arp(factory.make_ipv4_address())
        env = get_env_with_locale(locale="C")
        self.assertThat(
            call_and_check,
            MockCalledOnceWith(["ip", "--json", "neigh"], env=env),
        )

    def test_works_with_real_call(self):
        # No error.
        find_mac_via_arp(factory.make_ipv4_address())

    def test_fails_on_nonsensical_output(self):
        self.patch_call("Weird output...")
        self.assertRaises(
            Exception, find_mac_via_arp, factory.make_ipv4_address()
        )

    def test_returns_None_if_not_found(self):
        self.patch_call(self.make_output())
        self.assertIsNone(find_mac_via_arp(factory.make_ipv4_address()))

    def test_resolves_IPv4_address_to_MAC(self):
        self.patch_call(
            self.make_output(ip="10.55.60.9", mac="3c:41:92:68:2e:00")
        )
        mac_address_observed = find_mac_via_arp("10.55.60.9")
        self.assertEqual("3c:41:92:68:2e:00", mac_address_observed)

    def test_resolves_IPv6_address_to_MAC(self):
        self.patch_call(
            self.make_output(
                ip="fd10::a76:d7fe:fe93:7cb", mac="3c:41:92:6b:2e:00"
            )
        )
        mac_address_observed = find_mac_via_arp("fd10::a76:d7fe:fe93:7cb")
        self.assertEqual("3c:41:92:6b:2e:00", mac_address_observed)

    def test_ignores_failed_neighbours(self):
        ip = factory.make_ipv4_address()
        self.patch_call(self.make_output(ip=ip, state="FAILED"))
        self.assertIsNone(find_mac_via_arp(ip))

    def test_is_not_fooled_by_different_notations(self):
        mac = factory.make_mac_address()
        self.patch_call(self.make_output(ip="9::0:05", mac=mac))
        self.assertEqual(mac, find_mac_via_arp("09:0::5"))

    def test_returns_consistent_output(self):
        ip = factory.make_ipv4_address()
        macs = ["52:54:00:02:86:4b", "90:f6:52:f6:17:92"]
        entries = [{"dst": ip, "dev": "eth0", "lladdr": mac} for mac in macs]
        self.patch_call(json.dumps(entries))
        one_result = find_mac_via_arp(ip)
        self.patch_call(json.dumps(list(reversed(entries))))
        other_result = find_mac_via_arp(ip)
        self.assertIn(one_result, macs)
        self.assertEqual(one_result, other_result)

    def test_skips_failed(self):
        ip = factory.make_ipv4_address()
        mac = factory.make_mac_address()
        entries = [
            {
                "dst": ip,
                "dev": "eth0",
                "state": ["FAILED"],
            },
            {
                "dst": ip,
                "dev": "eth0",
                "lladdr": mac,
                "state": ["REACHABLE"],
            },
        ]
        self.patch_call(json.dumps(entries))
        self.assertEqual(find_mac_via_arp(ip), mac)


def patch_interfaces(testcase, interfaces):
    """Patch `netifaces` to show the given `interfaces`.

    :param testcase: The testcase that's doing the patching.
    :param interfaces: A dict mapping interface names to `netifaces`
        interface entries: dicts with keys like `AF_INET` etc.
    """
    # These two netifaces functions map conveniently onto dict methods.
    testcase.patch(netifaces, "interfaces", interfaces.keys)
    testcase.patch(netifaces, "ifaddresses", interfaces.get)


class TestGetAllAddressesForInterface(MAASTestCase):
    """Tests for `get_all_addresses_for_interface`."""

    scenarios = [
        (
            "ipv4",
            {
                "inet_class": AF_INET,
                "network_factory": factory.make_ipv4_network,
                "ip_address_factory": factory.make_ipv4_address,
                "loopback_address": "127.0.0.1",
            },
        ),
        (
            "ipv6",
            {
                "inet_class": AF_INET6,
                "network_factory": factory.make_ipv6_network,
                "ip_address_factory": factory.make_ipv6_address,
                "loopback_address": "::1",
            },
        ),
    ]

    def test_returns_address_for_inet_class(self):
        ip = self.ip_address_factory()
        interface = factory.make_name("eth", sep="")
        patch_interfaces(
            self, {interface: {self.inet_class: [{"addr": str(ip)}]}}
        )
        self.assertEqual(
            [ip], list(get_all_addresses_for_interface(interface))
        )

    def test_ignores_non_address_information(self):
        network = self.network_factory()
        ip = factory.pick_ip_in_network(network)
        interface = factory.make_name("eth", sep="")
        patch_interfaces(
            self,
            {
                interface: {
                    self.inet_class: [
                        {
                            "addr": str(ip),
                            "broadcast": str(network.broadcast),
                            "netmask": str(network.netmask),
                            "peer": str(
                                factory.pick_ip_in_network(
                                    network, but_not=[ip]
                                )
                            ),
                        }
                    ]
                }
            },
        )
        self.assertEqual(
            [ip], list(get_all_addresses_for_interface(interface))
        )

    def test_ignores_link_address(self):
        interface = factory.make_name("eth", sep="")
        patch_interfaces(
            self,
            {
                interface: {
                    AF_LINK: [
                        {
                            "addr": str(factory.make_mac_address()),
                            "peer": str(factory.make_mac_address()),
                        }
                    ]
                }
            },
        )
        self.assertEqual([], list(get_all_addresses_for_interface(interface)))

    def test_ignores_interface_without_address(self):
        network = self.network_factory()
        interface = factory.make_name("eth", sep="")
        patch_interfaces(
            self,
            {
                interface: {
                    self.inet_class: [
                        {
                            "broadcast": str(network.broadcast),
                            "netmask": str(network.netmask),
                        }
                    ]
                }
            },
        )
        self.assertEqual([], list(get_all_addresses_for_interface(interface)))


class TestGetAllInterfaceAddresses(MAASTestCase):
    """Tests for get_all_interface_addresses()."""

    def test_includes_loopback(self):
        v4_loopback_address = "127.0.0.1"
        v6_loopback_address = "::1"
        patch_interfaces(
            self,
            {
                "lo": {
                    AF_INET: [{"addr": v4_loopback_address}],
                    AF_INET6: [{"addr": v6_loopback_address}],
                }
            },
        )
        self.assertEqual(
            [v4_loopback_address, v6_loopback_address],
            list(get_all_interface_addresses()),
        )

    def test_returns_all_addresses_for_all_interfaces(self):
        v4_ips = [factory.make_ipv4_address() for _ in range(2)]
        v6_ips = [factory.make_ipv6_address() for _ in range(2)]
        ips = zip(v4_ips, v6_ips)
        interfaces = {
            factory.make_name("eth", sep=""): {
                AF_INET: [{"addr": str(ipv4)}],
                AF_INET6: [{"addr": str(ipv6)}],
            }
            for ipv4, ipv6 in ips
        }
        patch_interfaces(self, interfaces)
        self.assertCountEqual(v4_ips + v6_ips, get_all_interface_addresses())


class TestGetAllInterfaceAddressesWithMultipleClasses(MAASTestCase):
    """Tests for get_all_interface_addresses() with multiple inet classes."""

    def patch_interfaces(self, interfaces):
        """Patch `netifaces` to show the given `interfaces`.

        :param interfaces: A dict mapping interface names to `netifaces`
            interface entries: dicts with keys like `AF_INET` etc.
        """
        # These two netifaces functions map conveniently onto dict methods.
        self.patch(netifaces, "interfaces", interfaces.keys)
        self.patch(netifaces, "ifaddresses", interfaces.get)

    def test_returns_all_addresses_for_interface(self):
        v4_ip = factory.make_ipv4_address()
        v6_ip = factory.make_ipv6_address()
        interface = factory.make_name("eth", sep="")
        patch_interfaces(
            self,
            {
                interface: {
                    AF_INET: [{"addr": str(v4_ip)}],
                    AF_INET6: [{"addr": str(v6_ip)}],
                }
            },
        )
        self.assertEqual([v4_ip, v6_ip], list(get_all_interface_addresses()))


class TestCleanUpNetifacesAddress(MAASTestCase):
    """Tests for `clean_up_netifaces_address`."""

    def test_leaves_IPv4_intact(self):
        ip = str(factory.make_ipv4_address())
        interface = factory.make_name("eth")
        self.assertEqual(ip, clean_up_netifaces_address(ip, interface))

    def test_leaves_clean_IPv6_intact(self):
        ip = str(factory.make_ipv6_address())
        interface = factory.make_name("eth")
        self.assertEqual(ip, clean_up_netifaces_address(ip, interface))

    def test_removes_zone_index_suffix(self):
        ip = str(factory.make_ipv6_address())
        interface = factory.make_name("eth")
        self.assertEqual(
            ip,
            clean_up_netifaces_address(f"{ip}%{interface}", interface),
        )


class TestResolveHostToAddrs(MAASTestCase):
    """Tests for `resolve_hostname`."""

    def patch_getaddrinfo(self, *addrs):
        fake = self.patch(network_module, "getaddrinfo")
        fake.return_value = [
            (None, None, None, None, (str(address), 0)) for address in addrs
        ]
        return fake

    def patch_getaddrinfo_fail(self, exception):
        fake = self.patch(network_module, "getaddrinfo")
        fake.side_effect = exception
        return fake

    def test_rejects_weird_IP_version(self):
        self.assertRaises(
            AssertionError,
            resolve_hostname,
            factory.make_hostname(),
            ip_version=5,
        )

    def test_integrates_with_getaddrinfo(self):
        result = resolve_hostname("localhost", 4)
        self.assertIsInstance(result, set)
        [localhost] = result
        self.assertIsInstance(localhost, IPAddress)
        self.assertIn(localhost, IPNetwork("127.0.0.0/8"))

    def test_resolves_IPv4_address(self):
        ip = factory.make_ipv4_address()
        fake = self.patch_getaddrinfo(ip)
        hostname = factory.make_hostname()
        result = resolve_hostname(hostname, 4)
        self.assertIsInstance(result, set)
        self.assertEqual({IPAddress(ip)}, result)
        self.assertThat(
            fake,
            MockCalledOnceWith(hostname, 0, family=AF_INET, proto=IPPROTO_TCP),
        )

    def test_resolves_IPv6_address(self):
        ip = factory.make_ipv6_address()
        fake = self.patch_getaddrinfo(ip)
        hostname = factory.make_hostname()
        result = resolve_hostname(hostname, 6)
        self.assertIsInstance(result, set)
        self.assertEqual({IPAddress(ip)}, result)
        self.assertThat(
            fake,
            MockCalledOnceWith(
                hostname, 0, family=AF_INET6, proto=IPPROTO_TCP
            ),
        )

    def test_returns_empty_if_address_does_not_resolve(self):
        self.patch_getaddrinfo_fail(
            gaierror(EAI_NONAME, "Name or service not known")
        )
        self.assertEqual(set(), resolve_hostname(factory.make_hostname(), 4))

    def test_returns_empty_if_address_resolves_to_no_data(self):
        self.patch_getaddrinfo_fail(gaierror(EAI_NODATA, "No data returned"))
        self.assertEqual(set(), resolve_hostname(factory.make_hostname(), 4))

    def test_propagates_other_gaierrors(self):
        self.patch_getaddrinfo_fail(gaierror(EAI_BADFLAGS, "Bad parameters"))
        self.assertRaises(
            gaierror, resolve_hostname, factory.make_hostname(), 4
        )

    def test_propagates_unexpected_errors(self):
        self.patch_getaddrinfo_fail(KeyError("Huh what?"))
        self.assertRaises(
            KeyError, resolve_hostname, factory.make_hostname(), 4
        )

    def test_resolve_host_to_addrinfo_returns_full_information(self):
        ip = factory.make_ipv4_address()
        fake = self.patch_getaddrinfo(ip)
        hostname = factory.make_hostname()
        result = resolve_host_to_addrinfo(hostname, 4)
        self.assertIsInstance(result, list)
        self.assertEqual([(None, None, None, None, (ip, 0))], result)
        self.assertThat(
            fake,
            MockCalledOnceWith(hostname, 0, family=AF_INET, proto=IPPROTO_TCP),
        )


class TestIntersectIPRange(MAASTestCase):
    """Tests for `intersect_iprange()`."""

    def test_finds_intersection_between_two_ranges(self):
        range_1 = IPRange("10.0.0.1", "10.0.0.255")
        range_2 = IPRange("10.0.0.128", "10.0.0.200")
        intersect = intersect_iprange(range_1, range_2)
        self.expectThat(
            IPAddress(intersect.first), Equals(IPAddress("10.0.0.128"))
        )
        self.expectThat(
            IPAddress(intersect.last), Equals(IPAddress("10.0.0.200"))
        )

    def test_ignores_non_intersecting_ranges(self):
        range_1 = IPRange("10.0.0.1", "10.0.0.255")
        range_2 = IPRange("10.0.1.128", "10.0.1.200")
        self.assertIsNone(intersect_iprange(range_1, range_2))

    def test_finds_partial_intersection(self):
        range_1 = IPRange("10.0.0.1", "10.0.0.128")
        range_2 = IPRange("10.0.0.64", "10.0.0.200")
        intersect = intersect_iprange(range_1, range_2)
        self.expectThat(
            IPAddress(intersect.first), Equals(IPAddress("10.0.0.64"))
        )
        self.expectThat(
            IPAddress(intersect.last), Equals(IPAddress("10.0.0.128"))
        )


class TestIPRangeWithinNetwork(MAASTestCase):
    def test_returns_true_when_ip_range_is_within_network(self):
        ip_range = IPRange("10.0.0.55", "10.0.255.55")
        ip_network = IPNetwork("10.0.0.0/16")
        self.assertTrue(ip_range_within_network(ip_range, ip_network))

    def test_returns_false_when_ip_range_is_within_network(self):
        ip_range = IPRange("192.0.0.55", "192.0.255.55")
        ip_network = IPNetwork("10.0.0.0/16")
        self.assertFalse(ip_range_within_network(ip_range, ip_network))

    def test_returns_false_when_ip_range_is_partially_within_network(self):
        ip_range = IPRange("10.0.0.55", "10.1.0.55")
        ip_network = IPNetwork("10.0.0.0/16")
        self.assertFalse(ip_range_within_network(ip_range, ip_network))

    def test_works_with_two_ip_networks(self):
        network_1 = IPNetwork("10.0.0.0/16")
        network_2 = IPNetwork("10.0.0.0/24")
        self.assertTrue(ip_range_within_network(network_2, network_1))


class TestMAASIPSet(MAASTestCase):
    def test_contains_method(self):
        s = MAASIPSet(
            [
                make_iprange("10.0.0.1", "10.0.0.100"),
                make_iprange("10.0.0.200", "10.0.0.254"),
            ]
        )
        self.assertIn("10.0.0.1", s)
        self.assertIn(IPAddress("10.0.0.1"), s)
        self.assertIn(IPRange("10.0.0.1", "10.0.0.100"), s)
        self.assertNotIn(IPRange("10.0.0.1", "10.0.0.101"), s)
        self.assertNotIn("10.0.0.101", s)
        self.assertNotIn("10.0.0.199", s)
        self.assertIn(IPRange("10.0.0.200", "10.0.0.254"), s)
        self.assertNotIn(IPRange("10.0.0.99", "10.0.0.254"), s)
        self.assertNotIn("10.0.0.255", s)

    def test_normalizes_range(self):
        addr1 = "10.0.0.1"
        addr2 = IPAddress("10.0.0.2")
        range1 = make_iprange("10.0.0.3", purpose="DNS")
        range2 = make_iprange("10.0.0.4", "10.0.0.100", purpose="DHCP")
        s = MAASIPSet([range2, range1, addr1, addr2])
        for item in s:
            self.assertEqual(MAASIPRange, type(item))
        self.assertIn("10.0.0.1", s)
        self.assertIn("10.0.0.2", s)
        self.assertIn("10.0.0.3", s)
        self.assertIn("10.0.0.4", s)
        self.assertIn("10.0.0.50", s)
        self.assertIn("10.0.0.100", s)
        self.assertNotIn("10.0.0.101", s)
        self.assertNotIn("10.0.0.0", s)

    def test_normalizes_ipv6_range(self):
        addr1 = "fe80::1"
        addr2 = IPAddress("fe80::2")
        range1 = make_iprange("fe80::3", purpose="DNS")
        range2 = make_iprange(
            "fe80::100", "fe80::ffff:ffff:ffff:ffff", purpose="DHCP"
        )
        s = MAASIPSet([range2, range1, addr1, addr2])
        for item in s:
            self.assertEqual(MAASIPRange, type(item))
        self.assertIn("fe80::1", s)
        self.assertIn("fe80::2", s)
        self.assertIn("fe80::3", s)
        self.assertIn("fe80::100", s)
        self.assertIn("fe80::ffff:ffff:ffff:ffff", s)
        self.assertNotIn("fe80::1:ffff:ffff:ffff:ffff", s)

    def test_normalizes_range_with_iprange(self):
        addr1 = "10.0.0.1"
        addr2 = IPAddress("10.0.0.2")
        range1 = make_iprange("10.0.0.3", purpose="DNS")
        range2 = IPRange("10.0.0.4", "10.0.0.100")
        s = MAASIPSet([range2, range1, addr1, addr2])
        for item in s:
            self.assertEqual(MAASIPRange, type(item))
        self.assertIn("10.0.0.1", s)
        self.assertIn("10.0.0.2", s)
        self.assertIn("10.0.0.3", s)
        self.assertIn("10.0.0.4", s)
        self.assertIn("10.0.0.50", s)
        self.assertIn("10.0.0.100", s)
        self.assertNotIn("10.0.0.101", s)
        self.assertNotIn("10.0.0.0", s)

    def test_calculates_simple_unused_range(self):
        addr1 = "10.0.0.2"
        addr2 = IPAddress("10.0.0.3")
        range1 = make_iprange("10.0.0.4", purpose="DNS")
        range2 = IPRange("10.0.0.5", "10.0.0.100")
        s = MAASIPSet([range2, range1, addr1, addr2])
        u = s.get_unused_ranges("10.0.0.0/24")
        self.assertNotIn("10.0.0.0", u)
        self.assertIn("10.0.0.1", u)
        self.assertIn("10.0.0.101", u)
        self.assertIn("10.0.0.150", u)
        self.assertIn("10.0.0.254", u)
        self.assertNotIn("10.0.0.255", u)

    def test_calculates_simple_unused_range_with_iprange_input(self):
        addr1 = "10.0.0.1"
        addr2 = IPAddress("10.0.0.2")
        range1 = make_iprange("10.0.0.3", purpose="DNS")
        range2 = IPRange("10.0.0.4", "10.0.0.100")
        s = MAASIPSet([range2, range1, addr1, addr2])
        u = s.get_unused_ranges(IPRange("10.0.0.0", "10.0.0.255"))
        self.assertIn("10.0.0.0", u)
        self.assertIn("10.0.0.101", u)
        self.assertIn("10.0.0.150", u)
        self.assertIn("10.0.0.254", u)
        self.assertIn("10.0.0.255", u)

    def test_calculates_unused_range_with_overlap(self):
        range1 = make_iprange("10.0.0.3", purpose="DNS")
        range2 = make_iprange("10.0.0.3", "10.0.0.20", purpose="DHCP")
        rangeset = MAASIPSet([range2, range1])
        u = rangeset.get_unused_ranges("10.0.0.0/24")
        self.assertIn("10.0.0.1", u)
        self.assertIn("10.0.0.2", u)
        self.assertNotIn("10.0.0.3", u)
        self.assertNotIn("10.0.0.4", u)
        self.assertNotIn("10.0.0.20", u)
        self.assertIn("10.0.0.21", u)

    def test_calculates_unused_range_with_multiple_overlap(self):
        range1 = make_iprange("10.0.0.3", purpose="DNS")
        range2 = make_iprange("10.0.0.3", purpose="WINS")
        range3 = make_iprange("10.0.0.3", "10.0.0.20", purpose="DHCP")
        range4 = make_iprange("10.0.0.5", "10.0.0.20", purpose="DHCP")
        range5 = make_iprange("10.0.0.5", "10.0.0.18", purpose="DHCP")
        s = MAASIPSet([range1, range2, range3, range4, range5])
        u = s.get_unused_ranges("10.0.0.0/24")
        self.assertNotIn("10.0.0.0", u)
        self.assertIn("10.0.0.1", u)
        self.assertIn("10.0.0.2", u)
        self.assertNotIn("10.0.0.3", u)
        self.assertNotIn("10.0.0.4", u)
        self.assertNotIn("10.0.0.5", u)
        self.assertNotIn("10.0.0.6", u)
        self.assertNotIn("10.0.0.10", u)
        self.assertNotIn("10.0.0.18", u)
        self.assertNotIn("10.0.0.19", u)
        self.assertNotIn("10.0.0.20", u)
        self.assertIn("10.0.0.21", u)
        self.assertIn("10.0.0.254", u)
        self.assertNotIn("10.0.0.255", u)

    def test_deals_with_small_gaps(self):
        s = MAASIPSet(["10.0.0.2", "10.0.0.4", "10.0.0.6", "10.0.0.8"])
        u = s.get_unused_ranges("10.0.0.0/24")
        self.assertNotIn("10.0.0.0", u)
        self.assertIn("10.0.0.1", u)
        self.assertNotIn("10.0.0.2", u)
        self.assertIn("10.0.0.3", u)
        self.assertNotIn("10.0.0.4", u)
        self.assertIn("10.0.0.5", u)
        self.assertNotIn("10.0.0.6", u)
        self.assertIn("10.0.0.7", u)
        self.assertNotIn("10.0.0.8", u)
        self.assertIn("10.0.0.9", u)
        self.assertIn("10.0.0.254", u)
        self.assertNotIn("10.0.0.255", u)

    def test_calculates_ipv6_unused_range(self):
        addr1 = "fe80::1"
        addr2 = IPAddress("fe80::2")
        range1 = make_iprange("fe80::3", purpose="DNS")
        range2 = make_iprange(
            "fe80::100", "fe80::ffff:ffff:ffff:fffe", purpose="DHCP"
        )
        s = MAASIPSet([range2, range1, addr1, addr2])
        u = s.get_unused_ranges("fe80::/64")
        self.assertNotIn("fe80::1", u)
        self.assertNotIn("fe80::2", u)
        self.assertNotIn("fe80::3", u)
        self.assertNotIn("fe80::100", u)
        self.assertNotIn("fe80::ffff:ffff:ffff:fffe", u)
        self.assertIn("fe80::ffff:ffff:ffff:ffff", u)
        self.assertIn("fe80::5", u)
        self.assertIn("fe80::50", u)
        self.assertIn("fe80::99", u)
        self.assertIn("fe80::ff", u)

    def test_calculates_ipv6_unused_range_for_huge_range(self):
        addr1 = "fe80::1"
        addr2 = IPAddress("fe80::2")
        range1 = make_iprange("fe80::3", purpose="DNS")
        range2 = make_iprange(
            "fe80::100", "fe80::ffff:ffff:ffff:fffe", purpose="DHCP"
        )
        s = MAASIPSet([range2, range1, addr1, addr2])
        u = s.get_unused_ranges("fe80::/32")
        self.assertNotIn("fe80::1", u)
        self.assertNotIn("fe80::2", u)
        self.assertNotIn("fe80::3", u)
        self.assertNotIn("fe80::100", u)
        self.assertNotIn("fe80::ffff:ffff:ffff:fffe", u)
        self.assertIn("fe80::ffff:ffff:ffff:ffff", u)
        self.assertIn("fe80::5", u)
        self.assertIn("fe80::50", u)
        self.assertIn("fe80::99", u)
        self.assertIn("fe80::ff", u)
        self.assertIn("fe80:0:ffff:ffff:ffff:ffff:ffff:ffff", u)

    def test_calculates_full_range(self):
        s = MAASIPSet(["10.0.0.2", "10.0.0.4", "10.0.0.6", "10.0.0.8"])
        u = s.get_full_range("10.0.0.0/24")
        for ip in range(1, 254):
            self.assertIn("10.0.0.%d" % ip, u)
        self.assertIn("unused", u["10.0.0.1"].purpose)
        self.assertNotIn("unused", u["10.0.0.2"].purpose)
        self.assertIn("unused", u["10.0.0.254"].purpose)

    def test_calculates_full_range_for_small_ipv6(self):
        s = MAASIPSet([])
        u = s.get_full_range("2001:db8::/127")
        self.assertIn("unused", u["2001:db8::"].purpose)
        self.assertIn("unused", u["2001:db8::1"].purpose)

    def test_supports_ior(self):
        s1 = MAASIPSet(["10.0.0.2", "10.0.0.4", "10.0.0.6", "10.0.0.8"])
        s2 = MAASIPSet(["10.0.0.1", "10.0.0.3", "10.0.0.5", "10.0.0.7"])
        s1 |= s2
        self.assertThat(
            s1, ContainsAll({ip for ip in IPRange("10.0.0.1", "10.0.0.8")})
        )

    def test_ior_coalesces_adjacent_ranges(self):
        s1 = MAASIPSet(["10.0.0.2", "10.0.0.4", "10.0.0.6", "10.0.0.8"])
        s2 = MAASIPSet(["10.0.0.1", "10.0.0.3", "10.0.0.5", "10.0.0.7"])
        s1 |= s2
        # Since all these IP addresses are adjacent (and have the same
        # purpose), we should present them as a single entity. That is,
        # it will appear to the user as "10.0.0.1 through 10.0.0.8".
        self.assertThat(s1.ranges, HasLength(1))
        self.assertEqual("10.0.0.1", str(IPAddress(s1.first)))
        self.assertEqual("10.0.0.8", str(IPAddress(s1.last)))

    def test_ior_doesnt_combine_adjacent_ranges_with_different_purposes(self):
        s1 = MAASIPSet(
            [
                make_iprange("10.0.0.2", purpose="foo"),
                make_iprange("10.0.0.4", purpose="foo"),
                make_iprange("10.0.0.6", purpose="foo"),
                make_iprange("10.0.0.8", purpose="foo"),
            ]
        )
        s2 = MAASIPSet(
            [
                make_iprange("10.0.0.1", purpose="bar"),
                make_iprange("10.0.0.3", purpose="bar"),
                make_iprange("10.0.0.5", purpose="bar"),
                make_iprange("10.0.0.7", purpose="bar"),
            ]
        )
        s1 |= s2
        # Expect the individual addresses to be preserved in unique ranges,
        # since adjacent addresses have different purposes and thus will not
        # be combined.
        self.assertThat(s1.ranges, HasLength(8))
        self.assertEqual("10.0.0.1", str(IPAddress(s1.first)))
        self.assertEqual("10.0.0.8", str(IPAddress(s1.last)))


class TestIPRangeStatistics(MAASTestCase):
    def test_statistics_are_accurate(self):
        s = MAASIPSet(["10.0.0.2", "10.0.0.4", "10.0.0.6", "10.0.0.8"])
        u = s.get_full_range("10.0.0.0/24")
        stats = IPRangeStatistics(u)
        json = stats.render_json()
        self.assertEqual(250, json["num_available"])
        self.assertEqual(246, json["largest_available"])
        self.assertEqual(4, json["num_unavailable"])
        self.assertEqual(float(4) / float(254), json["usage"])
        self.assertEqual("2%", json["usage_string"])
        self.assertEqual("98%", json["available_string"])
        self.assertNotIn("ranges", json)

    def test_statistics_are_accurate_and_ranges_are_returned_if_desired(self):
        s = MAASIPSet(["10.0.0.2", "10.0.0.4", "10.0.0.6", "10.0.0.8"])
        u = s.get_full_range("10.0.0.0/24")
        stats = IPRangeStatistics(u)
        json = stats.render_json(include_ranges=True)
        self.assertEqual(250, json["num_available"])
        self.assertEqual(246, json["largest_available"])
        self.assertEqual(4, json["num_unavailable"])
        self.assertEqual(float(4) / float(254), json["usage"])
        self.assertEqual("2%", json["usage_string"])
        self.assertEqual("98%", json["available_string"])
        self.assertIn("ranges", json)
        self.assertEqual(stats.ranges.render_json(), json["ranges"])

    def test_statistics_are_accurate_for_full_slash_32(self):
        s = MAASIPSet(["10.0.0.1"])
        u = s.get_full_range("10.0.0.1/32")
        stats = IPRangeStatistics(u)
        json = stats.render_json()
        self.assertEqual(0, json["num_available"])
        self.assertEqual(0, json["largest_available"])
        self.assertEqual(1, json["num_unavailable"])
        self.assertEqual(float(1) / float(1), json["usage"])
        self.assertEqual("100%", json["usage_string"])
        self.assertEqual("0%", json["available_string"])
        self.assertNotIn("ranges", json)

    def test_statistics_are_accurate_for_empty_slash_32(self):
        s = MAASIPSet([])
        u = s.get_full_range("10.0.0.1/32")
        stats = IPRangeStatistics(u)
        json = stats.render_json()
        self.assertEqual(1, json["num_available"])
        self.assertEqual(1, json["largest_available"])
        self.assertEqual(0, json["num_unavailable"])
        self.assertEqual(float(0) / float(1), json["usage"])
        self.assertEqual("0%", json["usage_string"])
        self.assertEqual("100%", json["available_string"])
        self.assertNotIn("ranges", json)

    def test_statistics_are_accurate_for_full_slash_128(self):
        s = MAASIPSet(["2001:db8::1"])
        u = s.get_full_range("2001:db8::1/128")
        stats = IPRangeStatistics(u)
        json = stats.render_json()
        self.assertEqual(0, json["num_available"])
        self.assertEqual(0, json["largest_available"])
        self.assertEqual(1, json["num_unavailable"])
        self.assertEqual(float(1) / float(1), json["usage"])
        self.assertEqual("100%", json["usage_string"])
        self.assertEqual("0%", json["available_string"])
        self.assertNotIn("ranges", json)

    def test_statistics_are_accurate_for_empty_slash_128(self):
        s = MAASIPSet([])
        u = s.get_full_range("2001:db8::1/128")
        stats = IPRangeStatistics(u)
        json = stats.render_json()
        self.assertEqual(1, json["num_available"])
        self.assertEqual(1, json["largest_available"])
        self.assertEqual(0, json["num_unavailable"])
        self.assertEqual(float(0) / float(1), json["usage"])
        self.assertEqual("0%", json["usage_string"])
        self.assertEqual("100%", json["available_string"])
        self.assertNotIn("ranges", json)

    def test_statistics_are_accurate_for_empty_slash_127(self):
        s = MAASIPSet([])
        u = s.get_full_range("2001:db8::1/127")
        stats = IPRangeStatistics(u)
        json = stats.render_json()
        self.assertEqual(2, json["num_available"])
        self.assertEqual(2, json["largest_available"])
        self.assertEqual(0, json["num_unavailable"])
        self.assertEqual(float(0) / float(2), json["usage"])
        self.assertEqual("0%", json["usage_string"])
        self.assertEqual("100%", json["available_string"])
        self.assertNotIn("ranges", json)

    def test_statistics_are_accurate_for_empty_slash_31(self):
        s = MAASIPSet([])
        u = s.get_full_range("10.0.0.0/31")
        stats = IPRangeStatistics(u)
        json = stats.render_json()
        self.assertEqual(2, json["num_available"])
        self.assertEqual(2, json["largest_available"])
        self.assertEqual(0, json["num_unavailable"])
        self.assertEqual(float(0) / float(2), json["usage"])
        self.assertEqual("0%", json["usage_string"])
        self.assertEqual("100%", json["available_string"])
        self.assertNotIn("ranges", json)

    def test_suggests_subnet_anycast_address_for_ipv6(self):
        s = MAASIPSet([])
        u = s.get_full_range("2001:db8::/64")
        stats = IPRangeStatistics(u)
        self.assertEqual("2001:db8::", stats.suggested_gateway)

    def test_suggests_first_ip_as_default_gateway_if_available(self):
        s = MAASIPSet(["10.0.0.2", "10.0.0.4", "10.0.0.6", "10.0.0.8"])
        u = s.get_full_range("10.0.0.0/24")
        stats = IPRangeStatistics(u)
        self.assertEqual("10.0.0.1", stats.suggested_gateway)

    def test_suggests_last_ip_as_default_gateway_if_needed(self):
        s = MAASIPSet(["10.0.0.1", "10.0.0.4", "10.0.0.6", "10.0.0.8"])
        u = s.get_full_range("10.0.0.0/24")
        stats = IPRangeStatistics(u)
        self.assertEqual("10.0.0.254", stats.suggested_gateway)

    def test_suggests_first_available_ip_as_default_gateway_if_needed(self):
        s = MAASIPSet(["10.0.0.1", "10.0.0.4", "10.0.0.6", "10.0.0.254"])
        u = s.get_full_range("10.0.0.0/24")
        stats = IPRangeStatistics(u)
        self.assertEqual("10.0.0.2", stats.suggested_gateway)

    def test_suggests_no_gateway_if_range_full(self):
        s = MAASIPSet(["10.0.0.1"])
        u = s.get_full_range("10.0.0.1/32")
        stats = IPRangeStatistics(u)
        self.assertIsNone(stats.suggested_gateway)

    def test_suggests_no_dynamic_range_if_dynamic_range_exists(self):
        s = MAASIPSet(
            [MAASIPRange(start="10.0.0.2", end="10.0.0.99", purpose="dynamic")]
        )
        u = s.get_full_range("10.0.0.0/24")
        stats = IPRangeStatistics(u)
        json = stats.render_json(include_suggestions=True)
        self.assertIsNone(stats.suggested_dynamic_range)
        self.assertIsNone(json["suggested_dynamic_range"])

    def test_suggests_upper_one_fourth_range_for_dynamic_by_default(self):
        s = MAASIPSet([])
        u = s.get_full_range("10.0.0.0/24")
        stats = IPRangeStatistics(u)
        self.assertEqual("10.0.0.1", stats.suggested_gateway)
        self.assertThat(stats.suggested_dynamic_range, HasLength(64))
        self.assertIn("10.0.0.191", stats.suggested_dynamic_range)
        self.assertIn("10.0.0.254", stats.suggested_dynamic_range)
        self.assertNotIn("10.0.0.255", stats.suggested_dynamic_range)
        self.assertNotIn("10.0.0.190", stats.suggested_dynamic_range)

    def test_suggests_half_available_if_available_less_than_one_fourth(self):
        s = MAASIPSet([MAASIPRange("10.0.0.2", "10.0.0.205")])
        u = s.get_full_range("10.0.0.0/24")
        stats = IPRangeStatistics(u)
        self.assertEqual("10.0.0.1", stats.suggested_gateway)
        self.assertEqual(50, stats.num_available)
        self.assertThat(stats.suggested_dynamic_range, HasLength(25))
        self.assertIn("10.0.0.230", stats.suggested_dynamic_range)
        self.assertIn("10.0.0.254", stats.suggested_dynamic_range)
        self.assertNotIn("10.0.0.255", stats.suggested_dynamic_range)
        self.assertNotIn("10.0.0.229", stats.suggested_dynamic_range)

    def test_suggested_range_excludes_suggested_gateway(self):
        s = MAASIPSet([MAASIPRange("10.0.0.1", "10.0.0.204")])
        u = s.get_full_range("10.0.0.0/24")
        stats = IPRangeStatistics(u)
        self.assertEqual("10.0.0.254", stats.suggested_gateway)
        self.assertEqual(50, stats.num_available)
        self.assertThat(stats.suggested_dynamic_range, HasLength(25))
        self.assertIn("10.0.0.229", stats.suggested_dynamic_range)
        self.assertIn("10.0.0.253", stats.suggested_dynamic_range)
        self.assertNotIn("10.0.0.255", stats.suggested_dynamic_range)
        self.assertNotIn("10.0.0.228", stats.suggested_dynamic_range)

    def test_suggested_range_excludes_suggested_gateway_when_gw_first(self):
        s = MAASIPSet([MAASIPRange("10.0.0.1", "10.0.0.203"), "10.0.0.254"])
        u = s.get_full_range("10.0.0.0/24")
        stats = IPRangeStatistics(u)
        self.assertEqual("10.0.0.204", stats.suggested_gateway)
        self.assertEqual(50, stats.num_available)
        self.assertThat(stats.suggested_dynamic_range, HasLength(25))
        self.assertIn("10.0.0.229", stats.suggested_dynamic_range)
        self.assertIn("10.0.0.253", stats.suggested_dynamic_range)
        self.assertNotIn("10.0.0.255", stats.suggested_dynamic_range)
        self.assertNotIn("10.0.0.228", stats.suggested_dynamic_range)

    def test_suggests_upper_one_fourth_range_for_ipv6(self):
        s = MAASIPSet([])
        u = s.get_full_range("2001:db8::/64")
        stats = IPRangeStatistics(u)
        self.assertEqual("2001:db8::", stats.suggested_gateway)
        self.assertEqual((2**64) >> 2, stats.suggested_dynamic_range.size)
        self.assertIn("2001:db8:0:0:c000::", stats.suggested_dynamic_range)
        self.assertIn(
            "2001:db8::ffff:ffff:ffff:ffff",
            stats.suggested_dynamic_range,
        )
        self.assertNotIn("2001:db8::1", stats.suggested_dynamic_range)
        self.assertNotIn(
            "2001:db8::bfff:ffff:ffff:ffff",
            stats.suggested_dynamic_range,
        )

    def test_no_suggestion_for_small_ipv6_slash_126(self):
        s = MAASIPSet([])
        u = s.get_full_range("2001:db8::/126")
        stats = IPRangeStatistics(u)
        self.assertEqual("2001:db8::", stats.suggested_gateway)
        self.assertIsNone(stats.suggested_dynamic_range)

    def test_no_suggestion_for_small_ipv6_slash_127(self):
        s = MAASIPSet([])
        u = s.get_full_range("2001:db8::/127")
        stats = IPRangeStatistics(u)
        self.assertIsNone(stats.suggested_gateway)

    def test_no_suggestion_and_no_gateway_for_small_ipv6_slash_128(self):
        s = MAASIPSet([])
        u = s.get_full_range("2001:db8::/128")
        stats = IPRangeStatistics(u)
        self.assertIsNone(stats.suggested_gateway)

    def test_suggests_half_available_for_ipv6(self):
        s = MAASIPSet(
            [MAASIPRange("2001:db8::1", "2001:db8::ffff:ffff:ffff:ff00")]
        )
        u = s.get_full_range("2001:db8::/64")
        stats = IPRangeStatistics(u)
        self.assertEqual("2001:db8::", stats.suggested_gateway)
        self.assertEqual(255, stats.num_available)
        self.assertThat(stats.suggested_dynamic_range, HasLength(127))
        self.assertIn(
            "2001:db8::ffff:ffff:ffff:ff81",
            stats.suggested_dynamic_range,
        )
        self.assertIn(
            "2001:db8::ffff:ffff:ffff:ffff",
            stats.suggested_dynamic_range,
        )
        self.assertNotIn("2001:db8::1", stats.suggested_dynamic_range)
        self.assertNotIn(
            "2001:db8::ffff:ffff:ffff:ff80",
            stats.suggested_dynamic_range,
        )


class TestParseInteger(MAASTestCase):
    def test_parses_decimal_integer(self):
        self.assertEqual(0, parse_integer("0"))
        self.assertEqual(1, parse_integer("1"))
        self.assertEqual(-1, parse_integer("-1"))
        self.assertEqual(1000, parse_integer("1000"))
        self.assertEqual(10000000, parse_integer("10000000"))

    def test_parses_hexadecimal_integer(self):
        self.assertEqual(0, parse_integer("0x0"))
        self.assertEqual(1, parse_integer("0x1"))
        self.assertEqual(0x1000, parse_integer("0x1000"))
        self.assertEqual(0x10000000, parse_integer("0x10000000"))

    def test_parses_binary_integer(self):
        self.assertEqual(0, parse_integer("0b0"))
        self.assertEqual(1, parse_integer("0b1"))
        self.assertEqual(0b1000, parse_integer("0b1000"))
        self.assertEqual(0b10000000, parse_integer("0b10000000"))


class TestGetAllInterfacesDefinition(MAASTestCase):
    """Tests for `get_all_interfaces_definition` and all helper methods."""

    def assertInterfacesResult(
        self,
        ip_addr,
        iproute_info,
        dhclient_info,
        expected_results,
        in_container=False,
    ):
        self.patch(network_module, "get_ip_addr").return_value = ip_addr
        self.patch(network_module, "get_ip_route").return_value = iproute_info
        self.patch(
            network_module, "get_dhclient_info"
        ).return_value = dhclient_info
        self.patch(
            network_module, "running_in_container"
        ).return_value = in_container
        observed_result = get_all_interfaces_definition(
            annotate_with_monitored=False
        )
        self.assertThat(observed_result, expected_results)

    def test_ignores_loopback(self):
        ip_addr = {
            "vnet": {
                "type": "loopback",
                "enabled": True,
                "addresses": ["127.0.0.1/32", ["::1"]],
                "parents": [],
                "mac": [],
            }
        }
        self.assertInterfacesResult(ip_addr, {}, {}, MatchesDict({}))

    def test_ignores_ethernet(self):
        ip_addr = {
            "vnet": {
                "type": "ethernet",
                "mac": factory.make_mac_address(),
                "enabled": True,
                "addresses": ["192.168.122.2/24"],
                "parents": [],
            }
        }
        self.assertInterfacesResult(ip_addr, {}, {}, MatchesDict({}))

    def test_ignores_ipip(self):
        ip_addr = {
            "vnet": {
                "type": "ipip",
                "enabled": True,
                "mac": factory.make_mac_address(),
            }
        }
        self.assertInterfacesResult(ip_addr, {}, {}, MatchesDict({}))

    def test_ignores_tunnel(self):
        ip_addr = {
            "vnet": {
                "type": "tunnel",
                "enabled": True,
                "mac": factory.make_mac_address(),
            }
        }
        self.assertInterfacesResult(ip_addr, {}, {}, MatchesDict({}))

    def test_simple(self):
        ip_addr = {
            "eth0": {
                "type": "physical",
                "mac": factory.make_mac_address(),
                "enabled": True,
                "addresses": ["192.168.122.2/24"],
                "parents": [],
            }
        }
        expected_result = MatchesDict(
            {
                "eth0": MatchesDict(
                    {
                        "type": Equals("physical"),
                        "mac_address": Equals(ip_addr["eth0"]["mac"]),
                        "enabled": Is(True),
                        "parents": Equals([]),
                        "links": Equals(
                            [{"mode": "static", "address": "192.168.122.2/24"}]
                        ),
                        "source": Equals("machine-resources"),
                    }
                )
            }
        )
        self.assertInterfacesResult(ip_addr, {}, {}, expected_result)

    def test_simple_with_default_gateway(self):
        ip_addr = {
            "eth0": {
                "type": "ethernet.physical",
                "mac": factory.make_mac_address(),
                "enabled": True,
                "addresses": ["192.168.122.2/24"],
                "parents": [],
            }
        }
        iproute_info = {"default": {"gateway": "192.168.122.1"}}
        expected_result = MatchesDict(
            {
                "eth0": MatchesDict(
                    {
                        "type": Equals("physical"),
                        "mac_address": Equals(ip_addr["eth0"]["mac"]),
                        "enabled": Is(True),
                        "parents": Equals([]),
                        "links": Equals(
                            [
                                {
                                    "mode": "static",
                                    "address": "192.168.122.2/24",
                                    "gateway": "192.168.122.1",
                                }
                            ]
                        ),
                        "source": Equals("machine-resources"),
                    }
                )
            }
        )
        self.assertInterfacesResult(ip_addr, iproute_info, {}, expected_result)

    def test_doesnt_ignore_ethernet_in_container(self):
        ip_addr = {
            "eth0": {
                "type": "ethernet",
                "mac": factory.make_mac_address(),
                "enabled": True,
                "addresses": ["192.168.122.2/24"],
                "parents": [],
            }
        }
        expected_result = MatchesDict(
            {
                "eth0": MatchesDict(
                    {
                        "type": Equals("physical"),
                        "mac_address": Equals(ip_addr["eth0"]["mac"]),
                        "enabled": Is(True),
                        "parents": Equals([]),
                        "links": Equals(
                            [{"mode": "static", "address": "192.168.122.2/24"}]
                        ),
                        "source": Equals("machine-resources"),
                    }
                )
            }
        )
        self.assertInterfacesResult(
            ip_addr, {}, {}, expected_result, in_container=True
        )

    def test_simple_with_dhcp(self):
        ip_addr = {
            "eth0": {
                "type": "physical",
                "mac": factory.make_mac_address(),
                "enabled": True,
                "addresses": ["192.168.122.2/24", "192.168.122.200/32"],
                "parents": [],
            }
        }
        dhclient_info = {"eth0": "192.168.122.2"}
        expected_result = MatchesDict(
            {
                "eth0": MatchesDict(
                    {
                        "type": Equals("physical"),
                        "mac_address": Equals(ip_addr["eth0"]["mac"]),
                        "enabled": Is(True),
                        "parents": Equals([]),
                        "links": MatchesSetwise(
                            MatchesDict(
                                {
                                    "mode": Equals("dhcp"),
                                    "address": Equals("192.168.122.2/24"),
                                }
                            ),
                            MatchesDict(
                                {
                                    "mode": Equals("static"),
                                    "address": Equals("192.168.122.200/24"),
                                }
                            ),
                        ),
                        "source": Equals("machine-resources"),
                    }
                )
            }
        )
        self.assertInterfacesResult(
            ip_addr, {}, dhclient_info, expected_result
        )

    def test_fixing_links(self):
        ip_addr = {
            "eth0": {
                "type": "physical",
                "mac": factory.make_mac_address(),
                "enabled": True,
                "addresses": [
                    "192.168.122.2/24",
                    "192.168.122.3/32",
                    "192.168.123.3/32",
                    "2001:db8:a0b:12f0::1/96",
                    "2001:db8:a0b:12f0::2/128",
                ],
                "parents": [],
            }
        }
        expected_result = MatchesDict(
            {
                "eth0": MatchesDict(
                    {
                        "type": Equals("physical"),
                        "mac_address": Equals(ip_addr["eth0"]["mac"]),
                        "enabled": Is(True),
                        "parents": Equals([]),
                        "links": MatchesSetwise(
                            MatchesDict(
                                {
                                    "mode": Equals("static"),
                                    "address": Equals("192.168.122.2/24"),
                                }
                            ),
                            MatchesDict(
                                {
                                    "mode": Equals("static"),
                                    "address": Equals("192.168.122.3/24"),
                                }
                            ),
                            MatchesDict(
                                {
                                    "mode": Equals("static"),
                                    "address": Equals("192.168.123.3/32"),
                                }
                            ),
                            MatchesDict(
                                {
                                    "mode": Equals("static"),
                                    "address": Equals(
                                        "2001:db8:a0b:12f0::1/96"
                                    ),
                                }
                            ),
                            MatchesDict(
                                {
                                    "mode": Equals("static"),
                                    "address": Equals(
                                        "2001:db8:a0b:12f0::2/96"
                                    ),
                                }
                            ),
                        ),
                        "source": Equals("machine-resources"),
                    }
                )
            }
        )
        self.assertInterfacesResult(ip_addr, {}, {}, expected_result)

    def test_complex(self):
        ip_addr = {
            "eth0": {
                "type": "physical",
                "mac": factory.make_mac_address(),
                "enabled": False,
                "parents": [],
                "addresses": [],
            },
            "eth1": {
                "type": "physical",
                "mac": factory.make_mac_address(),
                "enabled": True,
                "parents": [],
                "addresses": [],
            },
            "eth2": {
                "type": "physical",
                "mac": factory.make_mac_address(),
                "enabled": True,
                "parents": [],
                "addresses": [],
            },
            "bond0": {
                "type": "bond",
                "mac": factory.make_mac_address(),
                "enabled": True,
                "parents": ["eth1", "eth2"],
                "addresses": [
                    "192.168.122.2/24",
                    "192.168.122.3/32",
                    "2001:db8::3:2:2/96",
                ],
            },
            "bond0.10": {
                "type": "vlan",
                "mac": factory.make_mac_address(),
                "enabled": True,
                "vid": 10,
                "parents": ["bond0"],
                "addresses": ["192.168.123.2/24", "192.168.123.3/32"],
            },
            "vlan20": {
                "type": "vlan",
                "mac": factory.make_mac_address(),
                "enabled": True,
                "vid": 20,
                "parents": ["eth0"],
                "addresses": [],
            },
            "wlan0": {
                "type": "wireless",
                "mac": factory.make_mac_address(),
                "enabled": True,
                "parents": [],
                "addresses": [],
            },
            "br0": {
                "type": "bridge",
                "mac": factory.make_mac_address(),
                "enabled": True,
                "parents": ["eth0"],
                "addresses": ["192.168.124.2/24"],
            },
            "gretap": {
                "type": "gretap",
                "mac": "",
                "enabled": True,
                "parents": [],
                "addresses": [],
            },
        }
        iproute_info = {
            "default": {"gateway": "192.168.122.1"},
            "192.168.124.0/24": {"gateway": "192.168.124.1"},
        }
        expected_result = MatchesDict(
            {
                "eth0": MatchesDict(
                    {
                        "type": Equals("physical"),
                        "mac_address": Equals(ip_addr["eth0"]["mac"]),
                        "enabled": Is(False),
                        "parents": Equals([]),
                        "links": Equals([]),
                        "source": Equals("machine-resources"),
                    }
                ),
                "eth1": MatchesDict(
                    {
                        "type": Equals("physical"),
                        "mac_address": Equals(ip_addr["eth1"]["mac"]),
                        "enabled": Is(True),
                        "parents": Equals([]),
                        "links": Equals([]),
                        "source": Equals("machine-resources"),
                    }
                ),
                "eth2": MatchesDict(
                    {
                        "type": Equals("physical"),
                        "mac_address": Equals(ip_addr["eth2"]["mac"]),
                        "enabled": Is(True),
                        "parents": Equals([]),
                        "links": Equals([]),
                        "source": Equals("machine-resources"),
                    }
                ),
                "bond0": MatchesDict(
                    {
                        "type": Equals("bond"),
                        "mac_address": Equals(ip_addr["bond0"]["mac"]),
                        "enabled": Is(True),
                        "parents": Equals(["eth1", "eth2"]),
                        "links": MatchesSetwise(
                            MatchesDict(
                                {
                                    "mode": Equals("static"),
                                    "address": Equals("192.168.122.2/24"),
                                    "gateway": Equals("192.168.122.1"),
                                }
                            ),
                            MatchesDict(
                                {
                                    "mode": Equals("static"),
                                    "address": Equals("192.168.122.3/24"),
                                    "gateway": Equals("192.168.122.1"),
                                }
                            ),
                            MatchesDict(
                                {
                                    "mode": Equals("static"),
                                    "address": Equals("2001:db8::3:2:2/96"),
                                }
                            ),
                        ),
                        "source": Equals("machine-resources"),
                    }
                ),
                "bond0.10": MatchesDict(
                    {
                        "type": Equals("vlan"),
                        "enabled": Is(True),
                        "parents": Equals(["bond0"]),
                        "mac_address": Equals(ip_addr["bond0.10"]["mac"]),
                        "vid": Equals(10),
                        "links": MatchesSetwise(
                            MatchesDict(
                                {
                                    "mode": Equals("static"),
                                    "address": Equals("192.168.123.2/24"),
                                }
                            ),
                            MatchesDict(
                                {
                                    "mode": Equals("static"),
                                    "address": Equals("192.168.123.3/24"),
                                }
                            ),
                        ),
                        "source": Equals("machine-resources"),
                    }
                ),
                "vlan20": MatchesDict(
                    {
                        "type": Equals("vlan"),
                        "mac_address": Equals(ip_addr["vlan20"]["mac"]),
                        "enabled": Is(True),
                        "parents": Equals(["eth0"]),
                        "links": Equals([]),
                        "source": Equals("machine-resources"),
                        "vid": Equals(20),
                    }
                ),
                "wlan0": MatchesDict(
                    {
                        "type": Equals("physical"),
                        "mac_address": Equals(ip_addr["wlan0"]["mac"]),
                        "enabled": Is(True),
                        "parents": Equals([]),
                        "links": Equals([]),
                        "source": Equals("machine-resources"),
                    }
                ),
                "br0": MatchesDict(
                    {
                        "type": Equals("bridge"),
                        "mac_address": Equals(ip_addr["br0"]["mac"]),
                        "enabled": Is(True),
                        "parents": Equals(["eth0"]),
                        "links": Equals(
                            [
                                {
                                    "mode": "static",
                                    "address": "192.168.124.2/24",
                                    "gateway": "192.168.124.1",
                                }
                            ]
                        ),
                        "source": Equals("machine-resources"),
                    }
                ),
            }
        )
        self.assertInterfacesResult(ip_addr, iproute_info, {}, expected_result)


class TestGetAllInterfacesSubnets(MAASTestCase):
    """Tests for `get_all_interface_subnets()`."""

    def test_includes_unique_subnets(self):
        interface_definition = {
            "eth0": {
                "links": [
                    {"address": "192.168.122.1/24"},
                    {"address": "192.168.122.3/24"},
                ]
            },
            "eth1": {
                "links": [
                    {"address": "192.168.123.1/24"},
                    {"address": "192.168.123.2/24"},
                ]
            },
        }
        self.patch(
            network_module, "get_all_interfaces_definition"
        ).return_value = interface_definition
        self.assertEqual(
            {IPNetwork("192.168.122.1/24"), IPNetwork("192.168.123.1/24")},
            get_all_interface_subnets(),
        )


class TestGetAllInterfacesSourceAddresses(MAASTestCase):
    """Tests for `get_all_interface_source_addresses()`."""

    def test_includes_unique_subnets(self):
        interface_subnets = {
            IPNetwork("192.168.122.1/24"),
            IPNetwork("192.168.123.1/24"),
        }
        self.patch(
            network_module, "get_all_interface_subnets"
        ).return_value = interface_subnets
        self.patch(network_module, "get_source_address").side_effect = [
            "192.168.122.1",
            None,
        ]
        self.assertEqual(
            {"192.168.122.1"}, get_all_interface_source_addresses()
        )


class InterfaceLinksTestCase(MAASTestCase):
    """Test case for `TestHasIPv4Address` and `TestEnumerateAddresses`."""

    def make_interface(self, addresses=None):
        links = []
        if addresses is not None:
            for address in addresses:
                links.append({"address": address, "mode": "static"})
        return {
            "enabled": True,
            "links": links,
            "mac_address": "52:54:00:e7:d9:2c",
            "monitored": True,
            "parents": [],
            "source": "machine-resources",
            "type": "physical",
        }


class TestHasIPv4Address(InterfaceLinksTestCase):
    """Tests for `has_ipv4_address()`."""

    def test_returns_false_for_no_ip_address(self):
        self.assertFalse(has_ipv4_address(self.make_interface()))

    def test_returns_false_for_ipv6_address(self):
        address = "%s/64" % factory.make_ipv6_address()
        self.assertFalse(
            has_ipv4_address(self.make_interface(addresses=[address]))
        )

    def test_returns_true_for_ipv4_address(self):
        address = "%s/24" % factory.make_ipv4_address()
        self.assertTrue(self.make_interface(addresses=[address]))


class TestGetIfnameIfdataForDestination(MAASTestCase):
    """Tests for `get_ifname_ifdata_for_destination()`."""

    def setUp(self):
        super().setUp()
        self.interfaces = {
            "eth0": {"links": [{"address": "192.168.0.1/24"}]},
            "eth1": {
                "links": [
                    {"address": "2001:db8::1/64"},
                    {"address": "172.16.0.1/24"},
                ]
            },
        }
        self.get_source_address_mock = self.patch(
            network_module, "get_source_address"
        )

    def test_returns_interface_for_expected_source_ip(self):
        self.get_source_address_mock.return_value = "2001:db8::1"
        ifname, ifdata = get_ifname_ifdata_for_destination(
            "2001:db8::2", self.interfaces
        )
        self.assertEqual("eth1", ifname)
        self.assertEqual(self.interfaces["eth1"], ifdata)
        self.get_source_address_mock.return_value = "192.168.0.1"
        ifname, ifdata = get_ifname_ifdata_for_destination(
            "192.168.0.2", self.interfaces
        )
        self.assertEqual("eth0", ifname)
        self.assertEqual(self.interfaces["eth0"], ifdata)
        self.get_source_address_mock.return_value = "172.16.0.1"
        ifname, ifdata = get_ifname_ifdata_for_destination(
            "172.16.0.2", self.interfaces
        )
        self.assertEqual("eth1", ifname)
        self.assertEqual(self.interfaces["eth1"], ifdata)

    def test_handles_loopback_addresses(self):
        self.get_source_address_mock.return_value = "127.0.0.1"
        ifname, ifdata = get_ifname_ifdata_for_destination(
            "127.0.0.1", self.interfaces
        )
        self.assertEqual("lo", ifname)
        self.assertEqual(LOOPBACK_INTERFACE_INFO, ifdata)
        self.get_source_address_mock.return_value = "::1"
        ifname, ifdata = get_ifname_ifdata_for_destination(
            "::1", self.interfaces
        )
        self.assertEqual("lo", ifname)
        self.assertEqual(LOOPBACK_INTERFACE_INFO, ifdata)

    def test_raises_valueerror_if_no_route_to_host(self):
        self.get_source_address_mock.return_value = None
        with ExpectedException(ValueError):
            get_ifname_ifdata_for_destination("2001:db8::2", self.interfaces)

    def test_raises_valueerror_if_source_ip_not_found(self):
        self.get_source_address_mock.return_value = "192.168.0.2"
        with ExpectedException(ValueError):
            get_ifname_ifdata_for_destination("192.168.0.3", self.interfaces)


class TestEnumerateAddresses(InterfaceLinksTestCase):
    """Tests for `enumerate_assigned_ips` and `enumerate_ipv4_addresses()`."""

    def test_returns_appropriate_assigned_ip_addresses(self):
        ipv6_address = factory.make_ipv6_address()
        ipv4_address = factory.make_ipv4_address()
        interface = self.make_interface(
            addresses=[ipv6_address + "/64", ipv4_address + "/24"]
        )
        ip_addresses = list(enumerate_assigned_ips(interface))
        ipv4_addresses = list(enumerate_ipv4_addresses(interface))
        self.assertEqual([ipv6_address, ipv4_address], ip_addresses)
        self.assertEqual([ipv4_address], ipv4_addresses)


class TestGetInterfaceChildren(MAASTestCase):
    """Tests for `get_interface_children()`."""

    def test_calculates_children_from_bond_parents(self):
        interfaces = {
            "eth0": {"parents": []},
            "eth1": {"parents": []},
            "bond0": {"parents": ["eth0", "eth1"]},
        }
        children_map = get_interface_children(interfaces)
        self.assertEqual({"eth0": {"bond0"}, "eth1": {"bond0"}}, children_map)

    def test_calculates_children_from_vlan_parents(self):
        interfaces = {
            "eth0": {"parents": []},
            "eth1": {"parents": []},
            "eth0.100": {"parents": ["eth0"]},
            "eth1.100": {"parents": ["eth1"]},
        }
        children_map = get_interface_children(interfaces)
        self.assertEqual(
            {"eth0": {"eth0.100"}, "eth1": {"eth1.100"}}, children_map
        )

    def test_calculates_children_from_bond_and_vlan_parents(self):
        interfaces = {
            "eth0": {"parents": []},
            "eth1": {"parents": []},
            "eth0.100": {"parents": ["eth0"]},
            "eth1.100": {"parents": ["eth1"]},
            "bond0": {"parents": ["eth0", "eth1"]},
        }
        children_map = get_interface_children(interfaces)
        self.assertThat(
            children_map,
            Equals(
                {"eth0": {"eth0.100", "bond0"}, "eth1": {"eth1.100", "bond0"}}
            ),
        )


class TestInterfaceChildren(MAASTestCase):
    """Tests for `interface_children()`."""

    def test_yields_each_child(self):
        interfaces = {
            "eth0": {"parents": []},
            "eth1": {"parents": []},
            "eth0.100": {"parents": ["eth0"]},
            "eth1.100": {"parents": ["eth1"]},
            "bond0": {"parents": ["eth0", "eth1"]},
        }
        children_map = get_interface_children(interfaces)
        eth0_children = list(
            interface_children("eth0", interfaces, children_map)
        )
        self.assertCountEqual(
            eth0_children,
            [
                ("eth0.100", {"parents": ["eth0"]}),
                ("bond0", {"parents": ["eth0", "eth1"]}),
            ],
        )
        eth1_children = list(
            interface_children("eth1", interfaces, children_map)
        )
        self.assertCountEqual(
            eth1_children,
            [
                ("eth1.100", {"parents": ["eth1"]}),
                ("bond0", {"parents": ["eth0", "eth1"]}),
            ],
        )

    def test_returns_namedtuple(self):
        interfaces = {
            "eth0": {"parents": []},
            "eth0.100": {"parents": ["eth0"]},
        }
        children_map = get_interface_children(interfaces)
        eth0_children = list(
            interface_children("eth0", interfaces, children_map)
        )
        self.assertEqual("eth0.100", eth0_children[0].name)
        self.assertEqual({"parents": ["eth0"]}, eth0_children[0].data)


class TestGetDefaultMonitoredInterfaces(MAASTestCase):
    """Tests for `get_default_monitored_interfaces()`."""

    def test_returns_enabled_physical_interfaces(self):
        interfaces = {
            "eth0": {"parents": [], "type": "physical", "enabled": False},
            "eth1": {"parents": [], "type": "physical", "enabled": True},
        }
        self.assertEqual(
            get_default_monitored_interfaces(interfaces), ["eth1"]
        )

    def test_returns_enabled_bond_interfaces_instead_of_physical(self):
        interfaces = {
            "eth0": {"parents": [], "type": "physical", "enabled": True},
            "eth1": {"parents": [], "type": "physical", "enabled": True},
            "eth2": {"parents": [], "type": "physical", "enabled": True},
            "eth3": {"parents": [], "type": "physical", "enabled": True},
            "bond0": {
                "parents": ["eth0", "eth1"],
                "type": "bond",
                "enabled": True,
            },
            "bond1": {
                "parents": ["eth2", "eth3"],
                "type": "bond",
                "enabled": False,
            },
        }
        self.assertEqual(
            get_default_monitored_interfaces(interfaces), ["bond0"]
        )

    def test_monitors_virtual_bridges_but_not_physical_bridges(self):
        interfaces = {
            "eth0": {"parents": [], "type": "physical", "enabled": True},
            "eth1": {"parents": [], "type": "physical", "enabled": True},
            "br0": {"parents": ["eth0"], "type": "bridge", "enabled": True},
            "virbr0": {"parents": [], "type": "bridge", "enabled": True},
        }
        self.assertEqual(
            get_default_monitored_interfaces(interfaces),
            ["eth0", "eth1", "virbr0"],
        )

    def test_monitors_physical_interfaces_but_not_child_vlans(self):
        interfaces = {
            "eth0": {"parents": [], "type": "physical", "enabled": True},
            "eth0.100": {"parents": ["eth0"], "type": "vlan", "enabled": True},
        }
        self.assertEqual(
            get_default_monitored_interfaces(interfaces), ["eth0"]
        )


class TestAnnotateWithDefaultMonitoredInterfaces(MAASTestCase):
    """Tests for `get_default_monitored_interfaces()`."""

    def test_adds_monitored_bool_to_interfaces_dictionary(self):
        interfaces = {
            "eth0": {"parents": [], "type": "physical", "enabled": False},
            "eth1": {"parents": [], "type": "physical", "enabled": True},
        }
        annotate_with_default_monitored_interfaces(interfaces)
        self.assertEqual(
            interfaces,
            {
                "eth0": {
                    "parents": [],
                    "type": "physical",
                    "enabled": False,
                    "monitored": False,
                },
                "eth1": {
                    "parents": [],
                    "type": "physical",
                    "enabled": True,
                    "monitored": True,
                },
            },
        )


class TestIsLoopbackAddress(MAASTestCase):
    def test_handles_ipv4_loopback(self):
        network = IPNetwork("127.0.0.0/8")
        address = factory.pick_ip_in_network(network)
        self.assertTrue(is_loopback_address(address))

    def test_handles_ipv6_loopback(self):
        address = "::1"
        self.assertTrue(is_loopback_address(address))

    def test_handles_random_ipv4_address(self):
        address = factory.make_ipv4_address()
        self.assertEqual(
            is_loopback_address(address), IPAddress(address).is_loopback()
        )

    def test_handles_random_ipv6_address(self):
        address = factory.make_ipv6_address()
        self.assertEqual(
            is_loopback_address(address), IPAddress(address).is_loopback()
        )

    def test_handles_ipv6_format_ipv4_loopback(self):
        network = IPNetwork("127.0.0.0/8")
        address = factory.pick_ip_in_network(network)
        self.assertTrue(is_loopback_address("::ffff:%s" % address))

    def test_handles_ipv6_format_ipv4_nonloopback(self):
        address = factory.make_ipv4_address()
        self.assertEqual(
            is_loopback_address("::ffff:%s" % address),
            IPAddress(address).is_loopback(),
        )

    def test_does_not_resolve_hostnames(self):
        gai = self.patch(socket, "getaddrinfo")
        gai.return_value = (
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("::1", None, 0, 1),
            ),
        )
        name = factory.make_name("name")
        self.assertFalse(is_loopback_address(name))
        self.assertThat(gai, MockNotCalled())

    def test_handles_localhost(self):
        gai = self.patch(socket, "getaddrinfo")
        gai.return_value = (
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("2001:db8::1", None, 0, 1),
            ),
        )
        self.assertTrue(is_loopback_address("localhost"))
        self.assertThat(gai, MockNotCalled())


class TestResolvesToLoopbackAddress(MAASTestCase):
    def test_resolves_hostnames(self):
        gai = self.patch(socket, "getaddrinfo")
        gai.return_value = (
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("::1", None, 0, 1),
            ),
        )
        name = factory.make_name("name")
        self.assertTrue(resolves_to_loopback_address(name))
        self.assertThat(gai, MockCalledOnceWith(name, None, proto=IPPROTO_TCP))

    def test_resolves_hostnames_non_loopback(self):
        gai = self.patch(socket, "getaddrinfo")
        gai.return_value = (
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("2001:db8::1", None, 0, 1),
            ),
        )
        name = factory.make_name("name")
        self.assertFalse(resolves_to_loopback_address(name))
        self.assertThat(gai, MockCalledOnceWith(name, None, proto=IPPROTO_TCP))


class TestPreferredHostnamesSortKey(MAASTestCase):
    """Tests for `preferred_hostnames_sort_key()`."""

    def test_sorts_flat_names(self):
        names = ("c", "b", "a", "z")
        self.assertEqual(
            ["a", "b", "c", "z"],
            sorted(names, key=preferred_hostnames_sort_key),
        )

    def test_sorts_more_qualified_names_first(self):
        names = (
            "diediedie.archive.ubuntu.com",
            "wpps.org.za",
            "ubuntu.com",
            "ubuntu.sets.a.great.example.com",
        )
        self.assertThat(
            sorted(names, key=preferred_hostnames_sort_key),
            Equals(
                [
                    "ubuntu.sets.a.great.example.com",
                    "diediedie.archive.ubuntu.com",
                    "wpps.org.za",
                    "ubuntu.com",
                ]
            ),
        )

    def test_sorts_by_domains_then_hostnames_within_each_domain(self):
        names = (
            "www.ubuntu.com",
            "maas.ubuntu.com",
            "us.archive.ubuntu.com",
            "uk.archive.ubuntu.com",
            "foo.maas.ubuntu.com",
            "archive.ubuntu.com",
            "maas-xenial",
            "juju-xenial",
        )
        self.assertThat(
            sorted(names, key=preferred_hostnames_sort_key),
            Equals(
                [
                    "uk.archive.ubuntu.com",
                    "us.archive.ubuntu.com",
                    "foo.maas.ubuntu.com",
                    "archive.ubuntu.com",
                    "maas.ubuntu.com",
                    "www.ubuntu.com",
                    "juju-xenial",
                    "maas-xenial",
                ]
            ),
        )

    def test_sorts_by_tlds_first(self):
        names = (
            "com.za",
            "com.com",
            "com.org",
            "www.ubuntu.org",
            "www.ubuntu.com",
            "www.ubuntu.za",
        )
        self.assertThat(
            sorted(names, key=preferred_hostnames_sort_key),
            Equals(
                [
                    "www.ubuntu.com",
                    "www.ubuntu.org",
                    "www.ubuntu.za",
                    "com.com",
                    "com.org",
                    "com.za",
                ]
            ),
        )

    def test_ignores_trailing_periods(self):
        names = (
            "com.za.",
            "com.com",
            "com.org.",
            "www.ubuntu.org",
            "www.ubuntu.com.",
            "www.ubuntu.za",
        )
        self.assertThat(
            sorted(names, key=preferred_hostnames_sort_key),
            Equals(
                [
                    "www.ubuntu.com.",
                    "www.ubuntu.org",
                    "www.ubuntu.za",
                    "com.com",
                    "com.org.",
                    "com.za.",
                ]
            ),
        )


class TestReverseResolveMixIn:
    """Test fixture mix-in for unit tests calling `reverseResolve()`."""

    def set_fake_twisted_dns_reply(self, hostnames: List[str]):
        """Sets up the rrset data structure for the mock resolver.

        This method must be called for any test cases in this suite which
        intend to test the data being returned.
        """
        rrset = []
        data = (rrset,)
        for hostname in hostnames:
            rr = Mock()
            decode = rr.payload.name.name.decode
            decode.return_value = hostname
            rrset.append(rr)
        self.reply = data

    def mock_lookupPointer(self, ip, timeout=None):
        self.timeout = timeout
        return succeed(self.reply)

    def get_mock_iresolver(self):
        resolver = Mock()
        resolver.lookupPointer = Mock()
        resolver.lookupPointer.side_effect = self.mock_lookupPointer
        return resolver

    def setUp(self):
        super().setUp()
        self.timeout = object()
        self.resolver = self.get_mock_iresolver()
        self.lookupPointer = self.resolver.lookupPointer
        self.getResolver = self.patch(network_module, "getResolver")
        self.getResolver.return_value = self.resolver


class TestReverseResolve(TestReverseResolveMixIn, MAASTestCase):
    """Tests for `reverseResolve`."""

    run_tests_with = MAASTwistedRunTest.make_factory(
        timeout=get_testing_timeout()
    )

    @inlineCallbacks
    def test_uses_resolver_from_getResolver_by_default(self):
        self.set_fake_twisted_dns_reply([])
        yield reverseResolve(factory.make_ip_address())
        self.assertThat(self.getResolver, MockCalledOnceWith())

    @inlineCallbacks
    def test_uses_passed_in_IResolver_if_specified(self):
        self.set_fake_twisted_dns_reply([])
        some_other_resolver = self.get_mock_iresolver()
        yield reverseResolve(
            factory.make_ip_address(), resolver=some_other_resolver
        )
        self.assertThat(self.getResolver, MockNotCalled())
        self.assertThat(some_other_resolver.lookupPointer, MockCalledOnce())

    @inlineCallbacks
    def test_returns_single_domain(self):
        reverse_dns_reply = ["example.com"]
        self.set_fake_twisted_dns_reply(reverse_dns_reply)
        result = yield reverseResolve(factory.make_ip_address())
        self.expectThat(result, Equals(reverse_dns_reply))

    @inlineCallbacks
    def test_returns_multiple_sorted_domains(self):
        reverse_dns_reply = ["ubuntu.com", "example.com"]
        self.set_fake_twisted_dns_reply(reverse_dns_reply)
        result = yield reverseResolve(factory.make_ip_address())
        self.expectThat(
            result,
            Equals(
                sorted(reverse_dns_reply, key=preferred_hostnames_sort_key)
            ),
        )

    @inlineCallbacks
    def test_empty_list_for_empty_rrset(self):
        reverse_dns_reply = []
        self.set_fake_twisted_dns_reply(reverse_dns_reply)
        result = yield reverseResolve(factory.make_ip_address())
        self.expectThat(result, Equals(reverse_dns_reply))

    @inlineCallbacks
    def test_returns_empty_list_for_domainerror(self):
        self.lookupPointer.side_effect = DomainError
        result = yield reverseResolve(factory.make_ip_address())
        self.expectThat(result, Equals([]))

    @inlineCallbacks
    def test_returns_empty_list_for_authoritativedomainerror(self):
        self.lookupPointer.side_effect = AuthoritativeDomainError
        result = yield reverseResolve(factory.make_ip_address())
        self.expectThat(result, Equals([]))

    @inlineCallbacks
    def test_returns_none_for_dnsquerytimeouterror(self):
        self.lookupPointer.side_effect = DNSQueryTimeoutError(None)
        result = yield reverseResolve(factory.make_ip_address())
        self.expectThat(result, Is(None))

    @inlineCallbacks
    def test_returns_none_for_resolvererror(self):
        self.lookupPointer.side_effect = ResolverError
        result = yield reverseResolve(factory.make_ip_address())
        self.expectThat(result, Is(None))

    @inlineCallbacks
    def test_raises_for_unhandled_error(self):
        self.lookupPointer.side_effect = TypeError
        with ExpectedException(TypeError):
            yield reverseResolve(factory.make_ip_address())


class TestCoerceHostname(MAASTestCase):
    def test_replaces_international_characters(self):
        self.assertEqual("abc-123", coerce_to_valid_hostname("abc青い空123"))

    def test_removes_illegal_dashes(self):
        self.assertEqual("abc123", coerce_to_valid_hostname("-abc123-"))

    def test_replaces_whitespace_and_special_characters(self):
        self.assertEqual(
            "abc123-ubuntu", coerce_to_valid_hostname("abc123 (ubuntu)")
        )

    def test_makes_hostname_lowercase(self):
        self.assertEqual(
            "ubunturocks", coerce_to_valid_hostname("UbuntuRocks")
        )

    def test_preserve_hostname_case(self):
        self.assertEqual(
            "UbuntuRocks", coerce_to_valid_hostname("UbuntuRocks", False)
        )

    def test_returns_none_if_result_empty(self):
        self.assertIsNone(coerce_to_valid_hostname("-人間性-"))

    def test_returns_none_if_result_too_large(self):
        self.assertIsNone(coerce_to_valid_hostname("a" * 65))


class TestGetSourceAddress(MAASTestCase):
    def test_accepts_ipnetwork(self):
        self.assertEqual(
            "127.0.0.1", get_source_address(IPNetwork("127.0.0.1/8"))
        )

    def test_ipnetwork_works_for_ipv4_slash32(self):
        mock = self.patch(network_module, "get_source_address_for_ipaddress")
        mock.return_value = "10.0.0.1"
        self.assertEqual(
            "10.0.0.1", get_source_address(IPNetwork("10.0.0.1/32"))
        )

    def test_ipnetwork_works_for_ipv6_slash128(self):
        mock = self.patch(network_module, "get_source_address_for_ipaddress")
        mock.return_value = "2001:67c:1560::1"
        self.assertEqual(
            "2001:67c:1560::1",
            get_source_address(IPNetwork("2001:67c:1560::/128")),
        )

    def test_ipnetwork_works_for_ipv6_slash48(self):
        mock = self.patch(network_module, "get_source_address_for_ipaddress")
        mock.return_value = "2001:67c:1560::1"
        self.assertEqual(
            "2001:67c:1560::1",
            get_source_address(IPNetwork("2001:67c:1560::/48")),
        )

    def test_ipnetwork_works_for_ipv6_slash64(self):
        mock = self.patch(network_module, "get_source_address_for_ipaddress")
        mock.return_value = "2001:67c:1560::1"
        self.assertEqual(
            "2001:67c:1560::1",
            get_source_address(IPNetwork("2001:67c:1560::1/64")),
        )

    def test_accepts_ipaddress(self):
        self.assertEqual(
            "127.0.0.1", get_source_address(IPAddress("127.0.0.1"))
        )

    def test_accepts_string(self):
        self.assertEqual("127.0.0.1", get_source_address("127.0.0.1"))

    def test_converts_ipv4_mapped_ipv6_to_ipv4(self):
        self.assertEqual("127.0.0.1", get_source_address("::ffff:127.0.0.1"))

    def test_supports_ipv6(self):
        self.assertEqual("::1", get_source_address("::1"))

    def test_returns_none_if_no_route_found(self):
        self.assertIsNone(get_source_address("255.255.255.255"))

    def test_returns_appropriate_address_for_global_ip(self):
        self.assertIsNotNone(get_source_address("8.8.8.8"))


class TestGenerateMACAddress(MAASTestCase):
    def test_starts_with_virsh_prefix(self):
        self.assertThat(generate_mac_address(), StartsWith("52:54:00:"))

    def test_never_the_same(self):
        random_macs = [generate_mac_address() for _ in range(10)]
        for mac1, mac2 in itertools.permutations(random_macs, 2):
            self.expectThat(mac1, Not(Equals(mac2)))


class TestConvertHostToUriStr(MAASTestCase):
    def test_hostname(self):
        hostname = factory.make_hostname()
        self.assertEqual(hostname, convert_host_to_uri_str(hostname))

    def test_ipv4(self):
        ipv4 = factory.make_ipv4_address()
        self.assertEqual(ipv4, convert_host_to_uri_str(ipv4))

    def test_ipv6_mapped(self):
        ipv4 = factory.make_ipv4_address()
        ipv6_mapped = IPAddress(ipv4).ipv6()
        self.assertEqual(ipv4, convert_host_to_uri_str(str(ipv6_mapped)))

    def test_ipv6(self):
        ipv6 = factory.make_ipv6_address()
        self.assertEqual("[%s]" % ipv6, convert_host_to_uri_str(ipv6))


class TestGetIfnameForLabel(MAASTestCase):
    scenarios = [
        ("numeric", {"input": "0", "expected": "eth0"}),
        (
            "numeric_zero_pad",
            {
                "input": "0000000000000000000000000000000000000000000000000000200",
                "expected": "eth200",
            },
        ),
        ("normal_interface_name", {"input": "eth0", "expected": "eth0"}),
        (
            "long_but_not_too_long_name",
            {"input": "eth012345678901", "expected": "eth012345678901"},
        ),
        (
            "name_a_little_too_long",
            {"input": "eth0123456789012", "expected": "eth-ff5c2-89012"},
        ),
        (
            "crazy_long_numeric_name",
            {
                "input": "1000000000000000000000000000000000000000000000000000001",
                "expected": "eth-8d3de-00001",
            },
        ),
    ]

    def test_scenarios(self):
        self.assertEqual(self.expected, get_ifname_for_label(self.input))
