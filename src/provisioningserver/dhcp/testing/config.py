# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test helpers related to DHCP configuration."""

__all__ = [
    'make_subnet_config',
    ]

from maastesting.factory import factory
from netaddr import IPAddress


def make_subnet_host(
        network, hostname=None, interface_name=None,
        mac_address=None, ip=None):
    """Return a host entry for a subnet from network."""
    if hostname is None:
        hostname = factory.make_name("host")
    if interface_name is None:
        interface_name = factory.make_name("eth")
    if mac_address is None:
        mac_address = factory.make_mac_address()
    if ip is None:
        ip = str(factory.pick_ip_in_network(network))
    return {
        "host": "%s-%s" % (hostname, interface_name),
        "mac": mac_address,
        "ip": ip,
    }


def make_subnet_config(network=None, hosts=None):
    """Return complete DHCP configuration dict for a subnet."""
    if network is None:
        network = factory.make_ipv4_network()
    if hosts is None:
        hosts = [
            make_subnet_host(network)
            for _ in range(3)
        ]
    ip_low, ip_high = factory.make_ip_range(network)
    return {
        'interface': factory.make_name('eth', sep=''),
        'subnet': str(IPAddress(network.first)),
        'subnet_mask': str(network.netmask),
        'subnet_cidr': str(network.cidr),
        'broadcast_ip': str(network.broadcast),
        'dns_servers': str(factory.pick_ip_in_network(network)),
        'ntp_server': str(factory.pick_ip_in_network(network)),
        'domain_name': '%s.example.com' % factory.make_name('domain'),
        'router_ip': str(factory.pick_ip_in_network(network)),
        'ip_range_low': str(ip_low),
        'ip_range_high': str(ip_high),
        'hosts': hosts,
        }
