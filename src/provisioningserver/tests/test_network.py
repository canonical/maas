# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `network` module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from netaddr import (
    IPAddress,
    IPNetwork,
)
from netifaces import (
    AF_INET,
    AF_INET6,
)
from provisioningserver import network
from provisioningserver.network import sort_networks_by_priority
from testtools.matchers import (
    Equals,
    HasLength,
)


def make_inet_address(subnet=None):
    """Fake an `AF_INET` or `AF_INET6` address."""
    if subnet is None:
        subnet = factory.make_ipv4_network()
    subnet = IPNetwork(subnet)
    addr = {
        'netmask': unicode(subnet.netmask),
        'addr': factory.pick_ip_in_network(subnet),
    }
    if subnet.version == 4:
        # IPv4 addresses also have a broadcast field.
        addr['broadcast'] = subnet.broadcast
    return addr


def make_loopback():
    """Fake a loopback AF_INET address."""
    return make_inet_address(IPNetwork('127.0.0.0/8'))


def make_interface(inet_address=None):
    """Minimally fake up an interface definition as returned by netifaces."""
    if inet_address is None:
        inet_address = make_inet_address()
    addr = inet_address.get('addr')
    if addr is None or IPAddress(addr).version == 4:
        address_family = AF_INET
    else:
        address_family = AF_INET6
    return {address_family: [inet_address]}


class TestNetworks(MAASTestCase):

    def patch_netifaces(self, interfaces):
        """Patch up netifaces to pretend we have given `interfaces`.

        :param interfaces: A dict mapping each interface's name to its
            definition as `netifaces` would return it.
        """
        self.patch(network, 'interfaces').return_value = interfaces.keys()
        self.patch(
            network, 'ifaddresses', lambda interface: interfaces[interface])

    def test_discover_networks_ignores_interface_without_IP_address(self):
        self.patch_netifaces({factory.make_name('eth'): {}})
        self.assertEqual([], network.discover_networks())

    def test_discover_networks_ignores_IPv4_loopback(self):
        self.patch_netifaces({'lo': make_interface(make_loopback())})
        self.assertEqual([], network.discover_networks())

    def test_discover_networks_ignores_IPv6_loopback(self):
        self.patch_netifaces(
            {'lo': make_interface(make_inet_address('::1/128'))})
        self.assertEqual([], network.discover_networks())

    def test_discover_networks_discovers_IPv4_network(self):
        eth = factory.make_name('eth')
        interface = make_interface()
        self.patch_netifaces({eth: interface})
        self.assertEqual([{
            'interface': eth,
            'ip': interface[AF_INET][0]['addr'],
            'subnet_mask': interface[AF_INET][0]['netmask'],
            }],
            network.discover_networks())

    def test_discover_networks_discovers_IPv6_network(self):
        eth = factory.make_name('eth')
        addr = make_inet_address(factory.make_ipv6_network())
        interface = make_interface(addr)
        self.patch_netifaces({eth: interface})
        self.assertEqual([{
            'interface': eth,
            'ip': addr['addr'],
            'subnet_mask': addr['netmask'],
            }],
            network.discover_networks())

    def test_discover_networks_returns_suitable_interfaces(self):
        eth = factory.make_name('eth')
        self.patch_netifaces({
            eth: make_interface(),
            'lo': make_interface(make_loopback()),
            factory.make_name('dummy'): make_interface({}),
            })
        self.assertEqual(
            [eth], [
                interface['interface']
                for interface in network.discover_networks()])

    def test_discover_networks_coalesces_networks_on_interface(self):
        eth = factory.make_name('eth')
        net = factory.make_ipv6_network()
        self.patch_netifaces({
            eth: {
                AF_INET6: [
                    make_inet_address(net),
                    make_inet_address(net),
                    ],
                },
            })
        interfaces = network.discover_networks()
        self.assertThat(interfaces, HasLength(1))
        [interface] = interfaces
        self.assertEqual(eth, interface['interface'])
        self.assertIn(IPAddress(interface['ip']), net)

    def test_discover_networks_discovers_multiple_networks_per_interface(self):
        eth = factory.make_name('eth')
        net1 = factory.make_ipv6_network()
        net2 = factory.make_ipv6_network(disjoint_from=[net1])
        addr1 = factory.pick_ip_in_network(net1)
        addr2 = factory.pick_ip_in_network(net2)
        self.patch_netifaces({
            eth: {
                AF_INET6: [
                    make_inet_address(addr1),
                    make_inet_address(addr2),
                    ],
                },
            })
        interfaces = network.discover_networks()
        self.assertThat(interfaces, HasLength(2))
        self.assertEqual(
            [eth, eth],
            [interface['interface'] for interface in interfaces])
        self.assertItemsEqual(
            [addr1, addr2],
            [interface['ip'] for interface in interfaces])

    def test_discover_networks_discovers_IPv4_and_IPv6_on_same_interface(self):
        eth = factory.make_name('eth')
        ipv4_net = factory.make_ipv4_network()
        ipv6_net = factory.make_ipv6_network()
        ipv4_addr = factory.pick_ip_in_network(ipv4_net)
        ipv6_addr = factory.pick_ip_in_network(ipv6_net)
        self.patch_netifaces({
            eth: {
                AF_INET: [make_inet_address(ipv4_addr)],
                AF_INET6: [make_inet_address(ipv6_addr)],
                },
            })
        interfaces = network.discover_networks()
        self.assertThat(interfaces, HasLength(2))
        self.assertEqual(
            [eth, eth],
            [interface['interface'] for interface in interfaces])
        self.assertItemsEqual(
            [ipv4_addr, ipv6_addr],
            [interface['ip'] for interface in interfaces])

    def test_discover_networks_ignores_link_local_IPv4_addresses(self):
        interface = factory.make_name('eth')
        ip = factory.pick_ip_in_network(IPNetwork('169.254.0.0/16'))
        self.patch_netifaces({interface: {AF_INET: [make_inet_address(ip)]}})
        self.assertEqual([], network.discover_networks())

    def test_discover_networks_ignores_link_local_IPv6_addresses(self):
        interface = factory.make_name('eth')
        ip = factory.pick_ip_in_network(IPNetwork('fe80::/10'))
        self.patch_netifaces({interface: {AF_INET6: [make_inet_address(ip)]}})
        self.assertEqual([], network.discover_networks())

    def test_discover_networks_runs_in_real_life(self):
        interfaces = network.discover_networks()
        self.assertIsInstance(interfaces, list)

    def test_filter_unique_networks_returns_networks(self):
        net = network.AttachedNetwork('eth0', '10.1.1.1', '255.255.255.0')
        self.assertEqual([net], network.filter_unique_networks([net]))

    def test_filter_unique_networks_drops_redundant_networks(self):
        entry1 = network.AttachedNetwork('eth0', '10.1.1.1', '255.255.255.0')
        entry2 = network.AttachedNetwork('eth0', '10.1.1.2', '255.255.255.0')
        networks = network.filter_unique_networks([entry1, entry2])
        self.assertThat(networks, HasLength(1))
        self.assertIn(networks[0], [entry1, entry2])

    def test_filter_unique_networks_orders_consistently(self):
        networks = [
            network.AttachedNetwork('eth1', '10.1.1.1', '255.255.255.0'),
            network.AttachedNetwork('eth2', '10.2.2.2', '255.255.255.0'),
            ]
        self.assertEqual(
            network.filter_unique_networks(networks),
            network.filter_unique_networks(reversed(networks)))


class TestSortNetworksByPriority(MAASTestCase):

    def test__sorts_by_type_then_ip_version(self):
        interfaces = [
            {'ip': "2001:db8::1",
             'type': "ethernet.vlan",
             'interface': 'vlan40'},
            {'ip': "10.0.0.1",
             'type': "ethernet.vlan",
             'interface': 'vlan40'},
            {'ip': "2001:db8:1::1",
             'type': "ethernet.physical",
             'interface': 'eth1'},
            {'ip': "10.0.1.1",
             'type': "ethernet.physical",
             'interface': 'eth1'},
            {'ip': "10.0.2.1",
             'type': "ethernet.bridge",
             'interface': 'br0'},
        ]
        sorted_interfaces = sort_networks_by_priority(interfaces)
        self.expectThat(sorted_interfaces[0], Equals(interfaces[3]))
        self.expectThat(sorted_interfaces[1], Equals(interfaces[2]))
        self.expectThat(sorted_interfaces[2], Equals(interfaces[4]))
        self.expectThat(sorted_interfaces[3], Equals(interfaces[1]))
        self.expectThat(sorted_interfaces[4], Equals(interfaces[0]))
