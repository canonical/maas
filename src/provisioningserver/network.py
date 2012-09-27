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

__metaclass__ = type
__all__ = [
    'discover_networks',
    ]

from io import BytesIO
import os
from subprocess import check_call


class InterfaceInfo:
    """The details of a network interface we are interested in."""

    def __init__(self, interface):
        self.interface = interface
        self.ip = None
        self.mask = None

    def may_be_subnet(self):
        """Could this be a subnet that MAAS is interested in?"""
        return all([
            self.interface != 'lo',
            self.ip is not None,
            self.mask is not None,
            ])

    def as_dict(self):
        return {
            'interface': self.interface,
            'ip': self.ip,
            'mask': self.mask,
        }


def run_ifconfig():
    """Run `ifconfig` to list active interfaces.  Return output."""
    env = dict(os.environ, LC_ALL='C')
    stdout = BytesIO()
    check_call(['/sbin/ifconfig'], env=env, stdout=stdout)
    stdout.seek(0)
    return stdout.read().decode('ascii')


def extract_ip_and_mask(line):
    """Get IP address and subnet mask from an inet address line."""
    # This line consists of key:value pairs separated by double spaces.
    # The "inet addr" key contains a space.  There is typically a
    # trailing separator.
    settings = dict(
        tuple(pair.split(':', 1))
        for pair in line.split('  '))
    return settings.get('inet addr'), settings.get('Mask')


def parse_stanza(stanza):
    """Return a :class:`InterfaceInfo` representing this ifconfig stanza.

    May return `None` if it's immediately clear that the interface is not
    relevant for MAAS.
    """
    lines = [line.strip() for line in stanza.splitlines()]
    header = lines[0]
    if 'Link encap:Ethernet' not in header:
        return None
    info = InterfaceInfo(header.split()[0])
    for line in lines[1:]:
        if line.split()[0] == 'inet':
            info.ip, info.mask = extract_ip_and_mask(line)
    return info


def split_stanzas(output):
    """Split `ifconfig` output into stanzas, one per interface."""
    stanzas = [stanza.strip() for stanza in output.strip().split('\n\n')]
    return [stanza for stanza in stanzas if len(stanza) > 0]


def parse_ifconfig(output):
    """List `InterfaceInfo` for each interface found in `ifconfig` output."""
    infos = [parse_stanza(stanza) for stanza in split_stanzas(output)]
    return [info for info in infos if info is not None]


def discover_networks():
    """Find the networks attached to this system."""
    output = run_ifconfig()
    return [
        interface
        for interface in parse_ifconfig(output)
            if interface.may_be_subnet()]
