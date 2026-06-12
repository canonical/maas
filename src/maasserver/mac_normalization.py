#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Detect MAC addresses that bypass uniqueness because of inconsistent format.

Historically MAAS did not always normalize the MAC addresses of interfaces
before storing them. As a result the same physical MAC could be stored more
than once using a different case (e.g. ``AA:BB:CC:DD:EE:FF`` and
``aa:bb:cc:dd:ee:ff``) and MAAS would treat them as distinct addresses.

Normalization is now applied on every write path, but pre-existing rows cannot
be fixed automatically without a database migration. This module detects such
rows so administrators can be warned to fix them manually.
"""

from collections import defaultdict

from maascommon.fields import normalise_macaddress

DUPLICATE_MAC_NOTIFICATION_IDENT = "duplicate_mac_addresses"


def find_duplicate_mac_addresses():
    """Return the normalized MACs that bypass the physical uniqueness check.

    MAAS only enforces MAC uniqueness for physical interfaces, scoped per
    ``node_config`` (see the conditional unique constraint on ``Interface``).
    Non-physical interfaces such as bonds, bridges and VLANs legitimately
    reuse the MAC address of one of their children, so they are ignored here.

    A MAC is reported only when two or more physical interfaces on the same
    ``node_config`` share the same normalized value. Because the database
    constraint already prevents identical stored values from coexisting, such
    rows can only exist when the values were stored in a different format
    (e.g. ``AA:BB:CC:DD:EE:FF`` and ``aa:bb:cc:dd:ee:ff``), which is exactly
    the case that bypasses the uniqueness check.
    """
    from maasserver.enum import INTERFACE_TYPE
    from maasserver.models.interface import Interface

    interfaces_by_normalized = defaultdict(set)
    for node_config_id, mac_address in (
        Interface.objects.filter(type=INTERFACE_TYPE.PHYSICAL)
        .exclude(mac_address__isnull=True)
        .values_list("node_config_id", "mac_address")
        .iterator()
    ):
        if not mac_address:
            continue
        try:
            normalized = normalise_macaddress(mac_address)
        except (ValueError, AttributeError):
            # A malformed value that can't be normalized can't collide with a
            # normalized one either, so it's not relevant to this check.
            continue
        interfaces_by_normalized[(node_config_id, normalized)].add(mac_address)

    return sorted(
        {
            normalized
            for (_, normalized), stored in interfaces_by_normalized.items()
            if len(stored) > 1
        }
    )


def sync_duplicate_mac_address_notification():
    """Create or clear the duplicate MAC address notification for admins."""
    from maasserver.models import Notification

    duplicates = find_duplicate_mac_addresses()

    existing = Notification.objects.filter(
        ident=DUPLICATE_MAC_NOTIFICATION_IDENT
    )

    if not duplicates:
        existing.delete()
        return

    message = (
        "%d MAC address(es) are stored in more than one format and are "
        "treated as distinct interfaces by MAAS. Please review the affected "
        "interfaces and update them so each physical MAC address is used "
        "only once." % len(duplicates)
    )

    if existing.exists():
        existing.update(message=message)
    else:
        Notification.objects.create_warning_for_admins(
            message,
            ident=DUPLICATE_MAC_NOTIFICATION_IDENT,
            dismissable=False,
        )
