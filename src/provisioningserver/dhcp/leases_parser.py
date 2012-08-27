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

hardware = CaselessKeyword("hardware") + hardware_type("type") + mac("mac")
ends = CaselessKeyword("ends") + expiry("expiry")
other_statement = (
    oneOf(
        ['starts', 'tstp', 'tsfp', 'cltt', 'uid', 'binding', 'next'],
        caseless=True) + args
    )

lease_statement = (hardware | ends | set_statement | other_statement) + Suppress(';')
lease_parser = (
    CaselessKeyword("lease") + ip("ip") +
    Suppress('{') +
    Dict(ZeroOrMore(Group(lease_statement))) +
    Suppress('}')
    )
lease_parser.ignore('#' + restOfLine)


def get_expiry_date(lease):
    """Get the expiry date for a lease, if any.

    :param lease: A lease as returned by the parser.
    :return: A UTC-based timestamp representing the lease's moment of
        expiry, or None if the lease has no expiry date.
    """
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
    expiry_date = get_expiry_date(lease)
    if expiry_date is None:
        return False
    else:
        return expiry_date < now


def parse_leases(leases_contents):
    """Parse contents of a leases file.

    :param leases_contents: Contents (as unicode) of the leases file.
    :return: A dict mapping each currently leased IP address to the MAC
        address that it is associated with.
    """
    now = datetime.utcnow()
    leases = lease_parser.searchString(leases_contents)
    # If multiple leases for the same address are valid at the same
    # time, for whatever reason, the dict will contain the one that was
    # last appended to the leases file.
    return {
        lease.ip: lease.hardware.mac
        for lease in leases
            if not has_expired(lease, now)}
