# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for network helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from socket import (
    EAI_BADFLAGS,
    EAI_NODATA,
    EAI_NONAME,
    gaierror,
)
from textwrap import dedent

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
import mock
from mock import sentinel
from netaddr import (
    EUI,
    IPAddress,
    IPNetwork,
    IPRange,
)
import netifaces
from netifaces import (
    AF_LINK,
    AF_INET,
    AF_INET6,
)
from provisioningserver.pserv_services.testing.neighbours import (
    NeighboursServiceFixture,
)
from provisioningserver.rpc.testing import TwistedLoggerFixture
from provisioningserver.utils import network as network_module
from provisioningserver.utils.network import (
    clean_up_netifaces_address,
    find_ip_via_arp,
    find_mac_via_arp,
    get_all_addresses_for_interface,
    get_all_interface_addresses,
    intersect_iprange,
    ip_range_within_network,
    make_network,
    NeighboursProtocol,
    resolve_hostname,
)
from testtools.deferredruntest import extract_result
from testtools.matchers import (
    AfterPreprocessing,
    AllMatch,
    Equals,
    HasLength,
    IsInstance,
    MatchesAll,
    Not,
)
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.error import (
    ProcessDone,
    ProcessTerminated,
)
from twisted.python.failure import Failure


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


class TestFindIPViaARP(MAASTestCase):

    def setUp(self):
        super(TestFindIPViaARP, self).setUp()
        self.neighbours = self.useFixture(NeighboursServiceFixture())

    def test__resolves_MAC_address_to_IP(self):
        sample = dedent("""\
        192.168.122.20 dev virbr0 lladdr 52:54:00:02:86:4b
        192.168.0.1 dev eth0 lladdr 90:f6:52:f6:17:92
        """)
        self.neighbours.setFromOutput(sample)
        ip_address_observed = find_ip_via_arp("90:f6:52:f6:17:92")
        self.assertEqual("192.168.0.1", ip_address_observed)

    def test__returns_consistent_output(self):
        mac = factory.make_mac_address()
        ips = ['10.0.0.11', '10.0.0.99']
        lines = ['%s dev eth0 lladdr %s' % (ip, mac) for ip in ips]
        self.neighbours.setFromOutput('\n'.join(lines))
        one_result = find_ip_via_arp(mac)
        self.neighbours.setFromOutput('\n'.join(reversed(lines)))
        other_result = find_ip_via_arp(mac)

        self.assertIn(one_result, ips)
        self.assertEqual(one_result, other_result)

    def test__ignores_case(self):
        sample = "192.168.0.1 dev eth0 lladdr 90:f6:52:f6:17:92"
        self.neighbours.setFromOutput(sample)
        ip_address_observed = find_ip_via_arp("90:f6:52:f6:17:92".upper())
        self.assertEqual("192.168.0.1", ip_address_observed)


class TestFindMACViaARP(MAASTestCase):

    def setUp(self):
        super(TestFindMACViaARP, self).setUp()
        self.neighbours = self.useFixture(NeighboursServiceFixture())
        self.patch_call = self.neighbours.setFromOutput

    def make_output_line(self, ip=None, mac=None, dev=None):
        """Compose an `ip neigh` output line for given `ip` and `mac`."""
        if ip is None:
            ip = factory.make_ipv4_address()
        if mac is None:
            mac = factory.make_mac_address()
        if dev is None:
            dev = factory.make_name('eth', sep='')
        return "%(ip)s dev %(dev)s lladdr %(mac)s\n" % {
            'ip': ip, 'dev': dev, 'mac': mac}

    def test__returns_None_if_not_found(self):
        self.neighbours.setFromOutput(self.make_output_line())
        self.assertIsNone(find_mac_via_arp(factory.make_ipv4_address()))

    def test__resolves_IPv4_address_to_MAC(self):
        sample = "10.55.60.9 dev eth0 lladdr 3c:41:92:68:2e:00 REACHABLE\n"
        self.neighbours.setFromOutput(sample)
        mac_address_observed = find_mac_via_arp('10.55.60.9')
        self.assertEqual('3c:41:92:68:2e:00', mac_address_observed)

    def test__resolves_IPv6_address_to_MAC(self):
        sample = (
            "fd10::a76:d7fe:fe93:7cb dev eth0 lladdr 3c:41:92:6b:2e:00 "
            "REACHABLE\n")
        self.neighbours.setFromOutput(sample)
        mac_address_observed = find_mac_via_arp('fd10::a76:d7fe:fe93:7cb')
        self.assertEqual('3c:41:92:6b:2e:00', mac_address_observed)

    def test__ignores_failed_neighbours(self):
        ip = factory.make_ipv4_address()
        self.neighbours.setFromOutput("%s dev eth0  FAILED\n" % ip)
        self.assertIsNone(find_mac_via_arp(ip))

    def test__is_not_fooled_by_prefixing(self):
        self.neighbours.setFromOutput(self.make_output_line('10.1.1.10'))
        self.assertIsNone(find_mac_via_arp('10.1.1.1'))
        self.assertIsNone(find_mac_via_arp('10.1.1.100'))

    def test__is_not_fooled_by_different_notations(self):
        mac = factory.make_mac_address()
        self.neighbours.setFromOutput(
            self.make_output_line('9::0:05', mac=mac))
        self.assertEqual(mac, find_mac_via_arp('09:0::5'))

    def test__returns_consistent_output(self):
        ip = factory.make_ipv4_address()
        macs = [
            '52:54:00:02:86:4b',
            '90:f6:52:f6:17:92',
            ]
        lines = [self.make_output_line(ip, mac) for mac in macs]
        self.neighbours.setFromOutput(''.join(lines))
        one_result = find_mac_via_arp(ip)
        self.neighbours.setFromOutput(''.join(reversed(lines)))
        other_result = find_mac_via_arp(ip)

        self.assertIn(one_result, macs)
        self.assertEqual(one_result, other_result)


class TestFindingAddressesWhenNeighboursServiceNotRunning(MAASTestCase):
    """Behaviour of `find_ip_via_arp` and `find_mac_via_arp`."""

    def test_ip_via_arp_returns_None(self):
        self.assertIsNone(find_ip_via_arp(sentinel.ignored))

    def test_mac_via_arg_returns_None(self):
        self.assertIsNone(find_mac_via_arp(sentinel.ignored))


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
            self, {interface: {self.inet_class: [{'addr': unicode(ip)}]}})
        self.assertEqual(
            [ip], list(get_all_addresses_for_interface(interface)))

    def test__ignores_non_address_information(self):
        network = self.network_factory()
        ip = factory.pick_ip_in_network(network)
        interface = factory.make_name('eth', sep='')
        patch_interfaces(self, {
            interface: {
                self.inet_class: [{
                    'addr': unicode(ip),
                    'broadcast': unicode(network.broadcast),
                    'netmask': unicode(network.netmask),
                    'peer': unicode(
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
                    'addr': unicode(factory.make_mac_address()),
                    'peer': unicode(factory.make_mac_address()),
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
                    'broadcast': unicode(network.broadcast),
                    'netmask': unicode(network.netmask),
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
                AF_INET: [{'addr': unicode(ipv4)}],
                AF_INET6: [{'addr': unicode(ipv6)}],
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
                    {'addr': unicode(v4_ip)}],
                AF_INET6: [
                    {'addr': unicode(v6_ip)}],
                }
            })
        self.assertEqual([v4_ip, v6_ip], list(get_all_interface_addresses()))


class TestCleanUpNetifacesAddress(MAASTestCase):
    """Tests for `clean_up_netifaces_address`."""

    def test__leaves_IPv4_intact(self):
        ip = unicode(factory.make_ipv4_address())
        interface = factory.make_name('eth')
        self.assertEqual(ip, clean_up_netifaces_address(ip, interface))

    def test__leaves_clean_IPv6_intact(self):
        ip = unicode(factory.make_ipv6_address())
        interface = factory.make_name('eth')
        self.assertEqual(ip, clean_up_netifaces_address(ip, interface))

    def test__removes_zone_index_suffix(self):
        ip = unicode(factory.make_ipv6_address())
        interface = factory.make_name('eth')
        self.assertEqual(
            ip,
            clean_up_netifaces_address('%s%%%s' % (ip, interface), interface))


class TestResolveHostname(MAASTestCase):
    """Tests for `resolve_hostname`."""

    def patch_getaddrinfo(self, *addrs):
        fake = self.patch(network_module, 'getaddrinfo')
        fake.return_value = [
            (None, None, None, None, (unicode(address), None))
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
        self.assertThat(fake, MockCalledOnceWith(hostname, mock.ANY, AF_INET))

    def test__resolves_IPv6_address(self):
        ip = factory.make_ipv6_address()
        fake = self.patch_getaddrinfo(ip)
        hostname = factory.make_hostname()
        result = resolve_hostname(hostname, 6)
        self.assertIsInstance(result, set)
        self.assertEqual({IPAddress(ip)}, result)
        self.assertThat(fake, MockCalledOnceWith(hostname, mock.ANY, AF_INET6))

    def test__returns_empty_if_address_does_not_resolve(self):
        self.patch_getaddrinfo_fail(
            gaierror(EAI_NONAME, "Name or service not known"))
        self.assertEqual(set(), resolve_hostname(factory.make_hostname(), 4))

    def test__returns_empty_if_address_resolves_to_no_data(self):
        self.patch_getaddrinfo_fail(
            gaierror(EAI_NODATA, "No data returned"))
        self.assertEqual(set(), resolve_hostname(factory.make_hostname(), 4))

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


class TestNeighboursProtocol(MAASTestCase):
    """Tests for `NeighboursProtocol`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    is_set = IsInstance(set)
    is_not_empty = Not(HasLength(0))

    is_ip_address = IsInstance(IPAddress)
    is_ip_address_set = MatchesAll(
        is_set, is_not_empty, AllMatch(is_ip_address), first_only=True)

    is_mac_address = IsInstance(EUI)
    is_mac_address_set = MatchesAll(
        is_set, is_not_empty, AllMatch(is_mac_address), first_only=True)

    @inlineCallbacks
    def test__works_with_real_call(self):
        proto = NeighboursProtocol()
        reactor.spawnProcess(proto, b"ip", (b"ip", b"neigh"))
        result = yield proto.done

        self.assertThat(result, HasLength(2))
        ip_to_mac, mac_to_ip = result

        # ip_to_mac is a mapping of IP addresses to sets of MAC addresses.
        self.expectThat(ip_to_mac, AfterPreprocessing(
            dict.keys, AllMatch(self.is_ip_address)))
        self.expectThat(ip_to_mac, AfterPreprocessing(
            dict.values, AllMatch(self.is_mac_address_set)))

        # mac_to_ip is a mapping of MAC addresses to sets of IP addresses.
        self.expectThat(mac_to_ip, AfterPreprocessing(
            dict.keys, AllMatch(self.is_mac_address)))
        self.expectThat(mac_to_ip, AfterPreprocessing(
            dict.values, AllMatch(self.is_ip_address_set)))

    def test__fails_on_nonsensical_output_from_ip_neigh(self):
        proto = NeighboursProtocol()
        proto.connectionMade()
        proto.outReceived(b"Weird output...")
        proto.processEnded(Failure(ProcessDone(0)))
        self.assertRaises(AssertionError, extract_result, proto.done)

    def test__captures_stderr_and_prints_it_when_process_ends(self):
        logger = TwistedLoggerFixture()
        self.useFixture(logger)

        message = factory.make_name("message")

        proto = NeighboursProtocol()
        proto.connectionMade()
        proto.errReceived(message.encode("ascii"))
        proto.processEnded(Failure(ProcessDone(0)))

        self.assertThat(extract_result(proto.done), Equals(({}, {})))
        self.assertThat(logger.output, Equals(
            "`ip neigh` wrote to stderr (an error may be reported "
            "separately): %s" % message))

    def test__propagates_errors_when_processing_output(self):
        proto = NeighboursProtocol()
        exception = factory.make_exception_type()
        self.patch(proto, "collateNeighbours").side_effect = exception
        proto.connectionMade()
        proto.outReceived(b"Weird output...")
        proto.processEnded(Failure(ProcessDone(0)))
        self.assertRaises(exception, extract_result, proto.done)

    def test__propagates_errors_from_ip_neigh(self):
        proto = NeighboursProtocol()
        proto.connectionMade()
        reason = Failure(ProcessTerminated(1))
        proto.processEnded(reason)
        self.assertRaises(ProcessTerminated, extract_result, proto.done)

    def test_parseOutput_parses_example_output(self):
        example_output = dedent("""\
        fe80::9e97:26ff:fe94:f884 dev eth0 lladdr \
            9c:97:26:94:f8:84 router REACHABLE
        2001:8b0:1219::fe94:f884 dev eth0 lladdr \
            9c:97:26:94:f8:84 router STALE
        172.16.1.254 dev eth1 lladdr 00:50:56:f9:33:8e STALE
        192.168.1.254 dev eth0 lladdr 9c:97:26:94:f8:84 DELAY
        172.16.1.1 dev eth1 lladdr 00:50:56:c0:00:01 STALE
        10.0.3.166 dev lxcbr0 lladdr 00:16:3e:da:8b:9e STALE
        """)
        parsed = NeighboursProtocol.parseOutput(example_output.splitlines())
        self.assertThat(list(parsed), Equals([
            (IPAddress("fe80::9e97:26ff:fe94:f884"), EUI("9c:97:26:94:f8:84")),
            (IPAddress("2001:8b0:1219::fe94:f884"), EUI("9c:97:26:94:f8:84")),
            (IPAddress("172.16.1.254"), EUI("00:50:56:f9:33:8e")),
            (IPAddress("192.168.1.254"), EUI("9c:97:26:94:f8:84")),
            (IPAddress("172.16.1.1"), EUI("00:50:56:c0:00:01")),
            (IPAddress("10.0.3.166"), EUI("00:16:3e:da:8b:9e")),
        ]))

    def test_parseOutput_ignores_failed_neighbours(self):
        ipaddr = factory.make_ipv4_address()
        example_output = "%s dev eth0  FAILED\n" % ipaddr
        parsed = NeighboursProtocol.parseOutput(example_output.splitlines())
        self.assertThat(list(parsed), Equals([]))

    def test_collateNeighbours_collates_results(self):
        example_results = [
            (IPAddress("192.168.1.1"), EUI("12:34:56:78:90:01")),
            (IPAddress("192.168.1.2"), EUI("12:34:56:78:90:01")),
            (IPAddress("192.168.1.1"), EUI("12:34:56:78:90:02")),
            (IPAddress("192.168.1.2"), EUI("12:34:56:78:90:02")),
        ]
        collates = NeighboursProtocol.collateNeighbours(example_results)
        self.assertThat(collates, Equals((
            # IP address to MAC address mapping.
            {
                IPAddress('192.168.1.2'): {
                    EUI('12-34-56-78-90-01'),
                    EUI('12-34-56-78-90-02'),
                },
                IPAddress('192.168.1.1'): {
                    EUI('12-34-56-78-90-01'),
                    EUI('12-34-56-78-90-02'),
                },
            },
            # MAC address to IP address mapping.
            {
                EUI('12-34-56-78-90-01'): {
                    IPAddress('192.168.1.2'),
                    IPAddress('192.168.1.1'),
                },
                EUI('12-34-56-78-90-02'): {
                    IPAddress('192.168.1.2'),
                    IPAddress('192.168.1.1'),
                },
            },
        )))
