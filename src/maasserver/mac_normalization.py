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
from maasserver.enum import INTERFACE_TYPE
from maasserver.models import Notification
from maasserver.models.interface import Interface

DUPLICATE_MAC_NOTIFICATION_IDENT = "duplicate_mac_addresses"
DUPLICATE_MAC_DOC_URL = (
    "https://canonical.com/maas/docs/latest/how-to-guides/"
    "resolve-duplicate-mac-addresses"
)


def _duplicate_mac_keys():
    """Return the ``(node_config_id, normalized_mac)`` keys stored under more
    than one form.

    MAAS only enforces MAC uniqueness for physical interfaces, scoped per
    ``node_config`` (see the conditional unique constraint on ``Interface``).
    Non-physical interfaces such as bonds, bridges and VLANs legitimately
    reuse the MAC address of one of their children, so they are ignored here.

    A key is returned only when two or more physical interfaces on the same
    ``node_config`` share the same normalized value. Because the database
    constraint already prevents identical stored values from coexisting, such
    rows can only exist when the values were stored in a different format
    (e.g. ``AA:BB:CC:DD:EE:FF`` and ``aa:bb:cc:dd:ee:ff``), which is exactly
    the case that bypasses the uniqueness check.
    """
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

    return {
        key
        for key, stored in interfaces_by_normalized.items()
        if len(stored) > 1
    }


def find_duplicate_mac_addresses():
    """Return the normalized MACs that bypass the physical uniqueness check."""
    return sorted({normalized for _, normalized in _duplicate_mac_keys()})


def print_duplicate_mac_report():
    """Print the physical interfaces whose MAC addresses bypass uniqueness.

    Intended to be run from a region controller shell. For each affected
    machine it lists the colliding interfaces, including the value stored in
    the database, so the duplicates can be identified and removed.
    """
    keys = _duplicate_mac_keys()
    if not keys:
        print("No duplicate MAC addresses found.")
        return

    node_config_ids = {node_config_id for node_config_id, _ in keys}
    grouped = defaultdict(list)
    for interface in (
        Interface.objects.filter(
            type=INTERFACE_TYPE.PHYSICAL,
            node_config_id__in=node_config_ids,
        )
        .exclude(mac_address__isnull=True)
        .select_related("node_config__node")
    ):
        if not interface.mac_address:
            continue
        key = (
            interface.node_config_id,
            normalise_macaddress(interface.mac_address),
        )
        if key in keys:
            grouped[key].append(interface)

    for node_config_id, normalized in sorted(grouped, key=lambda key: key[1]):
        interfaces = grouped[(node_config_id, normalized)]
        node = interfaces[0].node_config.node
        print(f"{node.hostname} ({node.system_id}) -> {normalized}")
        for interface in sorted(interfaces, key=lambda iface: iface.id):
            print(
                f"    interface id={interface.id} "
                f"name={interface.name} stored={interface.mac_address}"
            )


def sync_duplicate_mac_address_notification():
    """Create or clear the duplicate MAC address notification for admins."""
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
        "only once."
        "<br><a class='p-link--external' href='%s'>"
        "How to resolve duplicate MAC addresses...</a>"
    ) % (len(duplicates), DUPLICATE_MAC_DOC_URL)

    if existing.exists():
        existing.update(message=message)
    else:
        Notification.objects.create_warning_for_admins(
            message,
            ident=DUPLICATE_MAC_NOTIFICATION_IDENT,
            dismissable=False,
        )
