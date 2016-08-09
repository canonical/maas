# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test helpers related to DHCP configuration."""

__all__ = [
    'DHCPConfigNameResolutionDisabled',
    'make_failover_peer_config',
    'make_global_dhcp_snippets',
    'make_host',
    'make_host_dhcp_snippets',
    'make_shared_network',
    'make_subnet_config',
    'make_subnet_dhcp_snippets',
    'make_subnet_pool',
]

import random

from fixtures import Fixture
from maastesting.factory import factory
from netaddr import IPAddress
from provisioningserver.dhcp import config
from testtools.monkey import patch


def make_subnet_pool(
        network, start_ip=None, end_ip=None, failover_peer=None):
    """Return a pool entry for a subnet from network."""
    if start_ip is None and end_ip is None:
        start_ip, end_ip = factory.make_ip_range(network)
    if failover_peer is None:
        failover_peer = factory.make_name("failover")
    return {
        "ip_range_low": str(start_ip),
        "ip_range_high": str(end_ip),
        "failover_peer": failover_peer,
    }


def _make_snippets(count, template):
    names = (factory.make_name("name") for _ in range(count))
    return [
        {'name': name, 'description': factory.make_name('description'),
         'value': template % name} for name in names
    ]


def make_global_dhcp_snippets(allow_empty=True):
    count = random.randrange((0 if allow_empty else 1), 3)
    return _make_snippets(count, "group { next-server %s; }")


def make_subnet_dhcp_snippets(allow_empty=True):
    count = random.randrange((0 if allow_empty else 1), 3)
    return _make_snippets(count, "option pop-server %s;")


def make_host_dhcp_snippets(allow_empty=True):
    count = random.randrange((0 if allow_empty else 1), 3)
    return _make_snippets(count, "option smtp-server %s;")


def make_host(
        hostname=None, interface_name=None,
        mac_address=None, ip=None, ipv6=False, dhcp_snippets=None):
    """Return a host entry for a subnet from network."""
    if hostname is None:
        hostname = factory.make_name("host")
    if interface_name is None:
        interface_name = factory.make_name("eth")
    if mac_address is None:
        mac_address = factory.make_mac_address()
    if ip is None:
        ip = factory.make_ip_address(ipv6=ipv6)
    if dhcp_snippets is None:
        dhcp_snippets = make_host_dhcp_snippets()
    return {
        "host": "%s-%s" % (hostname, interface_name),
        "mac": mac_address,
        "ip": ip,
        "dhcp_snippets": dhcp_snippets,
    }


def make_subnet_config(network=None, pools=None, ipv6=False,
                       dhcp_snippets=None):
    """Return complete DHCP configuration dict for a subnet."""
    if network is None:
        if ipv6 is True:
            network = factory.make_ipv6_network()
        else:
            network = factory.make_ipv4_network()
    if pools is None:
        pools = [make_subnet_pool(network)]
    if dhcp_snippets is None:
        dhcp_snippets = make_subnet_dhcp_snippets()
    return {
        'subnet': str(IPAddress(network.first)),
        'subnet_mask': str(network.netmask),
        'subnet_cidr': str(network.cidr),
        'broadcast_ip': str(network.broadcast),
        'dns_servers': " ".join((
            factory.pick_ip_in_network(network),
            factory.pick_ip_in_network(network),
        )),
        'ntp_servers': " ".join((
            factory.make_ipv4_address(),
            factory.make_ipv6_address(),
            factory.make_name("ntp-server"),
        )),
        'domain_name': '%s.example.com' % factory.make_name('domain'),
        'router_ip': factory.pick_ip_in_network(network),
        'pools': pools,
        'dhcp_snippets': dhcp_snippets,
    }


def make_shared_network(name=None, subnets=None, ipv6=False):
    """Return complete DHCP configuration dict for a shared network."""
    if name is None:
        name = factory.make_name("vlan")
    if subnets is None:
        subnets = [
            make_subnet_config(ipv6=ipv6)
            for _ in range(3)
        ]
    return {
        "name": name,
        "subnets": subnets,
    }


def make_failover_peer_config(
        name=None, mode=None, address=None, peer_address=None):
    """Return complete DHCP configuration dict for a failover peer."""
    if name is None:
        name = factory.make_name("failover")
    if mode is None:
        mode = random.choice(["primary", "secondary"])
    if address is None:
        # XXX: GavinPanella 2016-07-26 bug=1606508: Only IPv4 peers are
        # supported. Failover may not actually be necessary for IPv6.
        address = factory.make_ipv4_address()
    if peer_address is None:
        # XXX: GavinPanella 2016-07-26 bug=1606508: Only IPv4 peers are
        # supported. Failover may not actually be necessary for IPv6.
        peer_address = factory.make_ipv4_address()
    return {
        'name': name,
        'mode': mode,
        'address': address,
        'peer_address': peer_address,
    }


def make_interface(name=None):
    if name is None:
        name = factory.make_name("eth")
    return {
        'name': name,
    }


class DHCPConfigNameResolutionDisabled(Fixture):
    """Prevent hostname resolution when generating DHCP configuration."""

    def _setUp(self):
        assert hasattr(config, "gen_addresses")
        restore = patch(config, "gen_addresses", self._genRandomAddresses)
        self.addCleanup(restore)

    def _genRandomAddresses(self, hostname):
        # Mimic config.gen_addresses by yielding a random IPv4 address and a
        # random IPv6 address.
        yield 4, factory.make_ipv4_address()
        yield 6, factory.make_ipv6_address()
