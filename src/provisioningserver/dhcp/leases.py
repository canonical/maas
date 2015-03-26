# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Send lease updates to the server.

This code runs inside node-group workers.  It watches for changes to DHCP
leases, and notifies the MAAS server so that it can rewrite DNS zone files
as appropriate.

Leases in this module are represented as dicts, mapping each leased IP
address to the MAC address that it belongs to.

The modification time and leases of the last-uploaded leases are cached,
so as to suppress unwanted redundant updates.  This cache is updated
*before* the actual upload, so as to prevent thundering-herd problems:
if an upload takes too long for whatever reason, subsequent updates
should not be uploaded until the first upload is done.  Some uploads may
be lost due to concurrency or failures, but the situation will right
itself eventually.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'check_lease_changes',
    'record_lease_state',
    ]


from collections import defaultdict
import errno
from os import (
    fstat,
    stat,
)

from provisioningserver.dhcp.leases_parser_fast import parse_leases
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.shell import objectfork


maaslog = get_maas_logger("dhcp.leases")

# Cache for leases, and lease times.
cache = defaultdict()

# Cache key for the modification time on last-processed leases file.
LEASES_TIME_CACHE_KEY = 'leases_time'

# Cache key for the leases as last parsed.
LEASES_CACHE_KEY = 'recorded_leases'


def get_leases_file():
    """Return the location of the DHCP leases file."""
    # This used to be configuration-based so that the development env could
    # have a different location. However, nobody seems to be provisioning from
    # a dev environment so it's hard-coded until that need arises, as
    # converting to the pserv config would be wasted work right now.
    return "/var/lib/maas/dhcp/dhcpd.leases"


def get_leases_timestamp():
    """Return the last modification timestamp of the DHCP leases file.

    None will be returned if the DHCP lease file cannot be found.
    """
    try:
        return stat(get_leases_file()).st_mtime
    except OSError as exception:
        # Return None only if the exception is a "No such file or
        # directory" exception.
        if exception.errno == errno.ENOENT:
            return None
        else:
            raise


def parse_leases_file():
    """Parse the DHCP leases file.

    :return: A tuple: (timestamp, leases).  The `timestamp` is the last
        modification time of the leases file, and `leases` is a dict
        mapping leased IP addresses to their associated MAC addresses.
        None will be returned if the DHCP lease file cannot be found.
    """
    try:
        with open(get_leases_file(), 'rb') as leases_file:
            contents = leases_file.read().decode('utf-8')
            return fstat(leases_file.fileno()).st_mtime, parse_leases(contents)
    except IOError as exception:
        # Return None only if the exception is a "No such file or
        # directory" exception.
        if exception.errno == errno.ENOENT:
            return None
        else:
            raise


def check_lease_changes():
    """Has the DHCP leases file changed in any significant way?"""
    # These variables are shared between worker threads/processes.
    # A bit of inconsistency due to concurrent updates is not a problem,
    # but read them both at once here to reduce the scope for trouble.
    previous_leases = cache.get(LEASES_CACHE_KEY)
    previous_leases_time = cache.get(LEASES_TIME_CACHE_KEY)

    if get_leases_timestamp() == previous_leases_time:
        return None

    with objectfork() as (pid, recv, send):
        if pid == 0:
            # Child, where we'll do the parsing.
            send(parse_leases_file())
        else:
            # Parent, where we'll receive the results.
            parse_result = recv()

    if parse_result is not None:
        timestamp, leases = parse_result
        if leases == previous_leases:
            return None
        else:
            return timestamp, leases
    else:
        return None


def record_lease_state(last_change, leases):
    """Record a snapshot of the state of DHCP leases.

    :param last_change: Modification date on the leases file with the given
        leases.
    :param leases: A dict mapping each leased IP address to the MAC address
        that it has been assigned to.
    """
    cache[LEASES_TIME_CACHE_KEY] = last_change
    cache[LEASES_CACHE_KEY] = leases
