#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Detect interface MAC addresses that bypass uniqueness checks.

Historically MAAS did not always normalize the MAC addresses of interfaces
before storing them. As a result the same physical MAC could be stored more
than once using a different case (e.g. ``AA:BB:CC:DD:EE:FF`` and
``aa:bb:cc:dd:ee:ff``) and MAAS would treat them as distinct addresses.

Pre-existing rows like these cannot be fixed automatically without a database
migration. This module detects such rows so administrators can be warned to fix
them manually before upgrading to a release that enforces uniqueness.
"""

from collections import defaultdict
from typing import NamedTuple

from maascommon.fields import normalise_macaddress
from maasserver.enum import INTERFACE_TYPE
from maasserver.models.interface import Interface


class _InterfaceRow(NamedTuple):
    """A lightweight projection of the interface fields used for detection.

    Avoids materializing full ``Interface``/``NodeConfig``/``Node`` model
    instances, which is significant when scanning every physical interface in
    a large deployment.
    """

    node_config_id: int
    node_id: int


def _group_has_conflict(interfaces):
    """Return whether a group of physical interfaces sharing a MAC conflicts.

    This mirrors the conflict detection performed by the 3.8 database migration
    that normalizes MAC addresses and enforces their uniqueness. Physical
    interfaces sharing a MAC are only legitimate when they belong to the same
    node under different node configs (e.g. the same NIC seen in the
    commissioning and deployment configs). Sharing within a single
    ``node_config`` violates the database uniqueness constraint, and sharing
    across different nodes violates the application-level uniqueness rules;
    both are reported as conflicts.
    """
    if len(interfaces) < 2:
        return False
    node_ids = {interface.node_id for interface in interfaces}
    node_config_ids = [interface.node_config_id for interface in interfaces]
    same_node = len(node_ids) == 1
    distinct_node_configs = len(set(node_config_ids)) == len(node_config_ids)
    return not (same_node and distinct_node_configs)


def find_duplicate_mac_addresses():
    """Return the normalized MACs that bypass the physical uniqueness check.

    Non-physical interfaces such as bonds, bridges and VLANs are excluded
    because they legitimately reuse the MAC address of one of their children.
    MACs that are used consistently, or that only repeat across different
    ``node_config`` of the same node, are omitted.

    The detection is kept in sync with the 3.8 database migration that
    normalizes MAC addresses, so an administrator who resolves every reported
    MAC here will not have the upgrade to 3.8 fail on duplicate interfaces.
    """
    interfaces_by_normalized = defaultdict(list)
    rows = (
        Interface.objects.filter(type=INTERFACE_TYPE.PHYSICAL)
        .exclude(mac_address__isnull=True)
        .exclude(node_config_id__isnull=True)
        .values_list(
            "mac_address",
            "node_config_id",
            "node_config__node_id",
        )
        .iterator()
    )
    for mac_address, node_config_id, node_id in rows:
        if not mac_address:
            continue
        try:
            normalized = normalise_macaddress(mac_address)
        except (ValueError, AttributeError):
            # A malformed value that can't be normalized can't collide with a
            # normalized one either, so it's not relevant to this check.
            continue
        interfaces_by_normalized[normalized].append(
            _InterfaceRow(
                node_config_id=node_config_id,
                node_id=node_id,
            )
        )

    return sorted(
        normalized
        for normalized, interfaces in interfaces_by_normalized.items()
        if _group_has_conflict(interfaces)
    )
