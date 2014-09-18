# Copyright 2014 Canonical Ltd.  This software is licensed under the
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

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
import mock
from netaddr import (
    IPAddress,
    IPNetwork,
    )
import netifaces
from netifaces import (
    AF_LINK,
    AF_INET,
    AF_INET6,
    )
import provisioningserver.utils
from provisioningserver.utils import network as network_module
from provisioningserver.utils.network import (
    clean_up_netifaces_address,
    find_ip_via_arp,
    find_mac_via_arp,
    get_all_addresses_for_interface,
    get_all_interface_addresses,
    make_network,
    resolve_hostname,
    )


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

    def patch_call(self, output):
        """Replace `call_and_check` with one that returns `output`."""
        fake = self.patch(network_module, 'call_and_check')
        fake.return_value = output
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
        fake.return_value = output
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
            'network_factory': factory.getRandomNetwork,
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
