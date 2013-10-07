# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
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
from netaddr import IPNetwork
from netifaces import AF_INET
from provisioningserver import network


def make_inet_address(subnet=None):
    """Fake an AF_INET address."""
    if subnet is None:
        subnet = factory.getRandomNetwork()
    return {
        'broadcast': subnet.broadcast,
        'netmask': subnet.netmask,
        'addr': factory.getRandomIPInNetwork(subnet),
    }


def make_loopback():
    """Fake a loopback AF_INET address."""
    return make_inet_address(IPNetwork('127.0.0.0/8'))


def make_interface(inet_address=None):
    """Minimally fake up an interface definition as returned by netifaces."""
    if inet_address is None:
        inet_address = make_inet_address()
    return {AF_INET: [inet_address]}


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

    def test_discover_networks_ignores_loopback(self):
        self.patch_netifaces({'lo': make_interface(make_loopback())})
        self.assertEqual([], network.discover_networks())

    def test_discover_networks_represents_interface(self):
        eth = factory.make_name('eth')
        interface = make_interface()
        self.patch_netifaces({eth: interface})
        self.assertEqual([{
            'interface': eth,
            'ip': interface[AF_INET][0]['addr'],
            'subnet_mask': interface[AF_INET][0]['netmask'],
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

    def test_discover_networks_runs_in_real_life(self):
        interfaces = network.discover_networks()
        self.assertIsInstance(interfaces, list)
