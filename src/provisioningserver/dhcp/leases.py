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


from os import stat

from celeryconfig import DHCP_LEASES_FILE

# Modification time on last-processed leases file.
recorded_leases_time = None

# Leases as last parsed.
recorded_leases = None


def get_leases_timestamp():
    """Return the last modification timestamp of the DHCP leases file."""
    return stat(DHCP_LEASES_FILE).st_mtime


def parse_leases():
    """Parse the DHCP leases file.

    :return: A tuple: (timestamp, leases).  The `timestamp` is the last
        modification time of the leases file, and `leases` is a dict
        mapping leased IP addresses to their associated MAC addresses.
    """
    # TODO: Implement leases-file parser here.


def check_lease_changes():
    """Has the DHCP leases file changed in any significant way?"""
    if get_leases_timestamp() == recorded_leases_time:
        return None
    timestamp, leases = parse_leases()
    if leases == recorded_leases:
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
    global recorded_leases_time
    global recorded_leases
    recorded_leases_time = last_change
    recorded_leases = leases


def send_leases(leases):
    """Send snapshot of current leases to the MAAS server."""
    # TODO: Implement API call for uploading leases.


def upload_leases():
    """Unconditionally send the current DHCP leases to the server.

    Run this periodically just so no changes slip through the cracks.
    Examples of such cracks would be: subtle races, failure to upload,
    server restarts, or zone-file update commands getting lost on their
    way to the DNS server.
    """
    timestamp, leases = parse_leases()
    record_lease_state(timestamp, leases)
    send_leases(leases)


def update_leases():
    """Check for DHCP lease updates, and send them to the server if needed.

    Run this whenever a lease has been added, removed, or changed.  It
    will be very cheap to run if the leases file has not been touched,
    and it won't upload unless there have been relevant changes.
    """
    updated_lease_info = check_lease_changes()
    if updated_lease_info is not None:
        timestamp, leases = updated_lease_info
        record_lease_state(timestamp, leases)
        send_leases(leases)
