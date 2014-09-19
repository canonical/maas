# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test helpers related to DHCP configuration."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'make_subnet_config',
    ]

from maastesting.factory import factory
from netaddr import IPAddress


def make_subnet_config(network=None):
    """Return complete DHCP configuration dict for a subnet."""
    if network is None:
        network = factory.make_ipv4_network()
    ip_low, ip_high = factory.make_ip_range(network)
    return {
        'interface': factory.make_name('eth', sep=''),
        'subnet': unicode(IPAddress(network.first)),
        'subnet_mask': unicode(network.netmask),
        'subnet_cidr': unicode(network.cidr),
        'broadcast_ip': unicode(network.broadcast),
        'dns_servers': unicode(factory.pick_ip_in_network(network)),
        'ntp_server': unicode(factory.pick_ip_in_network(network)),
        'domain_name': '%s.example.com' % factory.make_name('domain'),
        'router_ip': unicode(factory.pick_ip_in_network(network)),
        'ip_range_low': unicode(ip_low),
        'ip_range_high': unicode(ip_high),
        }
