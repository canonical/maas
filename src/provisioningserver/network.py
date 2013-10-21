# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Discover networks attached to this cluster controller.

A cluster controller uses this when registering itself with the region
controller.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'discover_networks',
    ]


from netifaces import (
    AF_INET,
    ifaddresses,
    interfaces,
    )


class InterfaceInfo:
    """The details of a network interface we are interested in."""

    def __init__(self, interface, ip=None, subnet_mask=None):
        self.interface = interface
        self.ip = ip
        self.subnet_mask = subnet_mask

    def may_be_subnet(self):
        """Could this be a subnet that MAAS is interested in?"""
        return all([
            self.interface != 'lo',
            self.ip is not None,
            self.subnet_mask is not None,
            ])

    def as_dict(self):
        """Return information as a dictionary.

        The return value's format is suitable as an interface description
        for use with the `register` API call.
        """
        return {
            'interface': self.interface,
            'ip': self.ip,
            'subnet_mask': self.subnet_mask,
        }


def get_interface_info(interface):
    """Return a list of `InterfaceInfo` for the named `interface`."""
    addresses = ifaddresses(interface).get(AF_INET)
    if addresses is None:
        return []
    else:
        return [
            InterfaceInfo(
                interface, ip=address.get('addr'),
                subnet_mask=address.get('netmask'))
            for address in addresses]


def discover_networks():
    """Find the networks attached to this system."""
    infos = sum(
        [get_interface_info(interface) for interface in interfaces()], [])
    return [
        info.as_dict()
        for info in infos
        if info.may_be_subnet()
    ]
