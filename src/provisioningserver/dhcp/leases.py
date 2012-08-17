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
    get_recorded_nodegroup_name,
    locate_maas_api,
    )
from provisioningserver.cache import cache
from provisioningserver.dhcp.leases_parser import parse_leases
from provisioningserver.logging import task_logger

# Cache key for the modification time on last-processed leases file.
LEASES_TIME_CACHE_KEY = 'leases_time'


# Cache key for the leases as last parsed.
LEASES_CACHE_KEY = 'recorded_leases'


# Cache key for the key we use to authenticate to omshell.
OMAPI_KEY_CACHE_KEY = 'omapi_key'


def record_omapi_key(omapi_key):
    """Record the OMAPI key as received from the server."""
    cache.set(OMAPI_KEY_CACHE_KEY, omapi_key)


def get_recorded_omapi_key():
    """Return the current OMAPI key as received from the server."""
    return cache.get(OMAPI_KEY_CACHE_KEY)


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
    # These variables are shared between threads.  A bit of
    # inconsistency due to concurrent updates is not a problem, but read
    # them both at once here to reduce the scope for trouble.
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


def identify_new_leases(current_leases):
    """Return a dict of those leases that weren't previously recorded.

    :param current_leases: A dict mapping IP addresses to the respective
        MAC addresses that own them.
    """
    # The recorded leases is shared between threads.  Read it
    # just once to reduce the impact of concurrent changes.
    previous_leases = cache.get(LEASES_CACHE_KEY)
    if previous_leases is None:
        return current_leases
    else:
        return {
            ip: current_leases[ip]
            for ip in set(current_leases).difference(previous_leases)}


def register_new_leases(current_leases):
    """Register new DHCP leases with the OMAPI.

    :param current_leases: A dict mapping IP addresses to the respective
        MAC addresses that own them.
    """
    # Avoid circular imports.
    from provisioningserver.tasks import add_new_dhcp_host_map

    # The recorded_omapi_key is shared between threads, so read it just
    # once, atomically.
    omapi_key = cache.get(OMAPI_KEY_CACHE_KEY)
    if omapi_key is None:
        task_logger.info(
            "Not registering new leases: "
            "no OMAPI key received from server yet.")
    else:
        new_leases = identify_new_leases(current_leases)
        add_new_dhcp_host_map(new_leases, 'localhost', omapi_key)


def send_leases(leases):
    """Send lease updates to the server API."""
    api_credentials = get_recorded_api_credentials()
    nodegroup_name = get_recorded_nodegroup_name()
    if None in (api_credentials, nodegroup_name):
        # The MAAS server hasn't sent us enough information for us to do
        # this yet.  Leave it for another time.
        if api_credentials is None:
            task_logger.info(
                "Not sending DHCP leases to server: "
                "No MAAS API credentials received from server yet.")
        if nodegroup_name is None:
            task_logger.info(
                "Not sending DHCP leases to server: "
                "No MAAS API URL received from server yet.")
        return

    api_path = 'nodegroups/%s/' % nodegroup_name
    oauth = MAASOAuth(*api_credentials)
    MAASClient(oauth, MAASDispatcher(), locate_maas_api()).post(
        api_path, 'update_leases', leases=leases)


def process_leases(timestamp, leases):
    """Register leases with the DHCP server, and send to the MAAS server."""
    # Register new leases before recording them.  That way, any
    # failure to register a lease will cause it to be retried at the
    # next opportunity.
    register_new_leases(leases)
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
