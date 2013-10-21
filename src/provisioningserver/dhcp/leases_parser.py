# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Parser for ISC dhcpd leases file.

The parser is very minimal.  All we really care about is which IP
addresses are currently associated with which respective MAC addresses.
The parser works out no other information than that, and does not
pretend to parse the full format of the leases file faithfully.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'parse_leases',
    ]

from datetime import datetime

from pyparsing import (
    CaselessKeyword,
    Dict,
    Group,
    oneOf,
    QuotedString,
    Regex,
    restOfLine,
    Suppress,
    ZeroOrMore,
    )


ip = Regex("[0-9]{1,3}(\.[0-9]{1,3}){3}")
mac = Regex("[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}")
hardware_type = Regex('[A-Za-z0-9_-]+')
args = Regex('[^"{;]+') | QuotedString('"')
expiry = Regex('[0-9]\s+[0-9/-]+\s+[0-9:]+') | 'never'
identifier = Regex("[A-Za-z_][0-9A-Za-z_-]*")
set_statement = (
    CaselessKeyword('set') +
    identifier +
    Suppress('=') +
    QuotedString('"'))

# For our purposes, leases and host declarations are similar enough that
# we can parse them as the same construct with different names.
lease_or_host = oneOf(['lease', 'host'], caseless=True)

hardware = CaselessKeyword("hardware") + hardware_type("type") + mac("mac")
ends = CaselessKeyword("ends") + expiry("expiry")
deleted = CaselessKeyword("deleted")

lone_statement_names = [
    'abandoned',
    'bootp',
    'deleted',
    'dynamic',
    'reserved',
    ]
lone_statement = oneOf(lone_statement_names, caseless=True)

other_statement_names = [
    'atsfp',
    'binding',
    'bootp',
    'client-hostname',
    'cltt',
    'ddns-client-fqdn',
    'ddns-fwd-name',
    'ddns-rev-name',
    'ddns-text',
    'fixed-address',
    'next',
    'option',
    'reserved',
    'rewind',
    'starts',
    'tstp',
    'tsfp',
    'uid',
    'vendor-class-identifier',
    ]
other_statement = oneOf(other_statement_names, caseless=True) + args

lease_statement = (
    hardware | deleted | ends | set_statement | lone_statement |
    other_statement
    ) + Suppress(';')
lease_parser = (
    lease_or_host("lease_or_host") + ip("ip") +
    Suppress('{') +
    Dict(ZeroOrMore(Group(lease_statement))) +
    Suppress('}')
    )
lease_parser.ignore('#' + restOfLine)


def is_lease(entry):
    """Is `entry` a lease declaration?"""
    entry_type = entry.lease_or_host.lower()
    assert entry_type in {'host', 'lease'}, (
        "Unknown entry type (not a host or lease): %s" % entry_type)
    return entry_type == 'lease'


def is_host(entry):
    """Is `entry` a host declaration?"""
    return not is_lease(entry)


def get_expiry_date(lease):
    """Get the expiry date for a lease, if any.

    :param lease: A lease as returned by the parser.
    :return: A UTC-based timestamp representing the lease's moment of
        expiry, or None if the lease has no expiry date.
    """
    assert is_lease(lease)
    ends = getattr(lease, 'ends', None)
    if ends is None or len(ends) == 0 or ends.lower() == 'never':
        return None
    else:
        return datetime.strptime(ends, '%w %Y/%m/%d %H:%M:%S')


def has_expired(lease, now):
    """Has `lease` expired?

    :param lease: A lease as returned by the parser.
    :param now: The current UTC-based timestamp to check expiry against.
    :return: Whether the lease has expired.
    """
    assert is_lease(lease)
    expiry_date = get_expiry_date(lease)
    if expiry_date is None:
        return False
    else:
        return expiry_date < now


def gather_leases(hosts_and_leases):
    """Find current leases among `hosts_and_leases`."""
    now = datetime.utcnow()
    # If multiple leases for the same address are valid at the same
    # time, for whatever reason, the dict will contain the one that was
    # last appended to the leases file.
    return {
        lease.ip: lease.hardware.mac
        for lease in filter(is_lease, hosts_and_leases)
        if not has_expired(lease, now)
    }


def get_host_mac(host):
    """Get the MAC address from a host declaration.  A rubout has none."""
    assert is_host(host)
    if 'deleted' in host:
        return None
    hardware = getattr(host, 'hardware', None)
    if hardware in (None, '', b''):
        return None
    else:
        return hardware.mac


def gather_hosts(hosts_and_leases):
    """Find current host declarations among `hosts_and_leases`."""
    # Get MAC address mappings for host entries.  A newer entry
    # overwrites an older one for the same IP address.  A rubout entry
    # will have no MAC address.
    host_maps = {
        host.ip: get_host_mac(host)
        for host in filter(is_host, hosts_and_leases)}
    # Now filter out mappings where the last entry was a rubout.
    return {
        ip: mac
        for ip, mac in host_maps.items()
        if mac is not None
    }


def combine_entries(entries):
    """Combine the hosts and leases declarations in a parsed leases file.

    :param entries: Parsed host/leases entries from a leases file.
    :return: A dict mapping leased IP addresses to the respective MAC
        addresses that currently own them (regardless of whether they
        were found in a lease or in a host declaration).
    """
    leases = gather_leases(entries)
    leases.update(gather_hosts(entries))
    return leases


def parse_leases(leases_contents):
    """Parse contents of a leases file.

    :param leases_contents: Contents (as unicode) of the leases file.
    :return: A dict mapping each currently leased IP address to the MAC
        address that it is associated with.
    """
    entries = lease_parser.searchString(leases_contents)
    return combine_entries(entries)
