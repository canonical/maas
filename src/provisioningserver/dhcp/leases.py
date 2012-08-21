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

__metaclass__ = type
__all__ = [
    'upload_leases',
    'update_leases',
    ]


from os import (
    fstat,
    stat,
    )

from apiclient.maas_client import (
    MAASClient,
    MAASDispatcher,
    MAASOAuth,
    )
from celeryconfig import DHCP_LEASES_FILE
from provisioningserver.auth import (
    get_recorded_api_credentials,
    get_recorded_maas_url,
    get_recorded_nodegroup_name,
    )
from provisioningserver.cache import cache
from provisioningserver.dhcp.leases_parser import parse_leases
from provisioningserver.logging import task_logger

# Cache key for the modification time on last-processed leases file.
LEASES_TIME_CACHE_KEY = 'leases_time'


# Cache key for the leases as last parsed.
LEASES_CACHE_KEY = 'recorded_leases'


def get_leases_timestamp():
    """Return the last modification timestamp of the DHCP leases file."""
    return stat(DHCP_LEASES_FILE).st_mtime


def parse_leases_file():
    """Parse the DHCP leases file.

    :return: A tuple: (timestamp, leases).  The `timestamp` is the last
        modification time of the leases file, and `leases` is a dict
        mapping leased IP addresses to their associated MAC addresses.
    """
    with open(DHCP_LEASES_FILE, 'rb') as leases_file:
        contents = leases_file.read().decode('utf-8')
        return fstat(leases_file.fileno()).st_mtime, parse_leases(contents)


def check_lease_changes():
    """Has the DHCP leases file changed in any significant way?"""
    # These variables are shared between worker threads/processes.
    # A bit of inconsistency due to concurrent updates is not a problem,
    # but read them both at once here to reduce the scope for trouble.
    previous_leases = cache.get(LEASES_CACHE_KEY)
    previous_leases_time = cache.get(LEASES_TIME_CACHE_KEY)

    if get_leases_timestamp() == previous_leases_time:
        return None
    timestamp, leases = parse_leases_file()
    if leases == previous_leases:
        return None
    else:
        return timestamp, leases


def record_lease_state(last_change, leases):
    """Record a snapshot of the state of DHCP leases.

    :param last_change: Modification date on the leases file with the given
        leases.
    :param leases: A dict mapping each leased IP address to the MAC address
        that it has been assigned to.
    """
    cache.set(LEASES_TIME_CACHE_KEY, last_change)
    cache.set(LEASES_CACHE_KEY, leases)


def list_missing_items(knowledge):
    """Report items from dict `knowledge` that are still `None`."""
    return sorted(name for name, value in knowledge.items() if value is None)


def send_leases(leases):
    """Send lease updates to the server API."""
    # Items that the server must have sent us before we can do this.
    knowledge = {
        'maas_url': get_recorded_maas_url(),
        'api_credentials': get_recorded_api_credentials(),
        'nodegroup_name': get_recorded_nodegroup_name(),
    }
    if None in knowledge.values():
        # The MAAS server hasn't sent us enough information for us to do
        # this yet.  Leave it for another time.
        task_logger.info(
            "Not sending DHCP leases to server: not all required knowledge "
            "received from server yet.  "
            "Missing: %s"
            % ', '.join(list_missing_items(knowledge)))
        return

    api_path = 'nodegroups/%s/' % knowledge['nodegroup_name']
    oauth = MAASOAuth(*knowledge['api_credentials'])
    MAASClient(oauth, MAASDispatcher(), knowledge['maas_url']).post(
        api_path, 'update_leases', leases=leases)


def process_leases(timestamp, leases):
    """Send new leases to the MAAS server."""
    record_lease_state(timestamp, leases)
    send_leases(leases)


def upload_leases():
    """Unconditionally send the current DHCP leases to the server.

    Run this periodically just so no changes slip through the cracks.
    Examples of such cracks would be: subtle races, failure to upload,
    server restarts, or zone-file update commands getting lost on their
    way to the DNS server.
    """
    timestamp, leases = parse_leases_file()
    process_leases(timestamp, leases)


def update_leases():
    """Check for DHCP lease updates, and send them to the server if needed.

    Run this whenever a lease has been added, removed, or changed.  It
    will be very cheap to run if the leases file has not been touched,
    and it won't upload unless there have been relevant changes.
    """
    updated_lease_info = check_lease_changes()
    if updated_lease_info is not None:
        timestamp, leases = updated_lease_info
        process_leases(timestamp, leases)
