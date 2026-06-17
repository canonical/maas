# Copyright 2026 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""normalize_interface_mac_addresses

Revision ID: 0023
Revises: 0022
Create Date: 2026-06-16 00:00:00.000000+00:00

"""

from itertools import chain
import re
from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of maascommon.fields.normalise_macaddress. Migrations must not
# depend on application code that can change over time.
_MAC_SPLIT_RE = re.compile(r"[-:.]")

# Canonical stored form: lowercase, colon-separated, zero-padded octets.
_CANONICAL_MAC_RE = "^([0-9a-f]{2}:){5}[0-9a-f]{2}$"

_CHECK_CONSTRAINT_NAME = "maasserver_interface_mac_address_canonical"


def _normalize_mac(mac: str) -> str:
    tokens = _MAC_SPLIT_RE.split(mac.lower())
    match len(tokens):
        case 1:  # no separator
            tokens = re.findall("..", tokens[0])
        case 3:  # each token is two bytes
            tokens = chain(
                *(re.findall("..", token.zfill(4)) for token in tokens)
            )
        case _:  # single-byte tokens
            tokens = (token.zfill(2) for token in tokens)
    return ":".join(tokens)


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT i.id, i.node_config_id, i.mac_address, i.type, "
            "nc.node_id, n.system_id "
            "FROM maasserver_interface i "
            "LEFT JOIN maasserver_nodeconfig nc ON nc.id = i.node_config_id "
            "LEFT JOIN maasserver_node n ON n.id = nc.node_id "
            "WHERE i.mac_address IS NOT NULL"
        )
    ).fetchall()

    changed = []
    # Physical interfaces sharing a MAC are only legitimate when they belong to
    # the same node under different node configs (e.g. the same NIC seen in the
    # commissioning and deployment configs). Sharing within a single node_config
    # violates maasserver_interface_node_config_mac_address_uniq, and sharing
    # across different nodes violates the application-level uniqueness rules;
    # both must be resolved before the canonical format is enforced.
    physical_by_mac: dict[str, list] = {}
    for row in rows:
        # An empty MAC address is a valid "no MAC" marker (e.g. for unknown
        # interfaces); leave it untouched and skip normalization.
        if row.mac_address == "":
            continue
        normalized = _normalize_mac(row.mac_address)
        if normalized != row.mac_address:
            changed.append({"id": row.id, "mac": normalized})
        if row.type == "physical" and row.node_config_id is not None:
            physical_by_mac.setdefault(normalized, []).append(row)

    conflicts: list[str] = []
    for normalized, interfaces in physical_by_mac.items():
        if len(interfaces) < 2:
            continue
        node_ids = {iface.node_id for iface in interfaces}
        node_config_ids = [iface.node_config_id for iface in interfaces]
        same_node = len(node_ids) == 1
        distinct_node_configs = len(set(node_config_ids)) == len(
            node_config_ids
        )
        if same_node and distinct_node_configs:
            continue
        details = ", ".join(
            f"{iface.id} (node {iface.system_id}, "
            f"node_config {iface.node_config_id})"
            for iface in sorted(interfaces, key=lambda iface: iface.id)
        )
        conflicts.append(f"{normalized}: interfaces {details}")

    if conflicts:
        raise RuntimeError(
            "Cannot normalize interface MAC addresses: doing so would create "
            "duplicate physical interfaces. MAAS requires every physical "
            "interface to have a unique MAC address, unless the same node "
            "exposes it under different node configurations. Remove or correct "
            "the conflicting interfaces listed below, then retry the upgrade "
            "(see the MAAS release notes for guidance on resolving duplicate "
            "MAC addresses):\n" + "\n".join(conflicts)
        )

    if changed:
        # A data migration runs in a single transaction and can fire triggers.
        # Disable MAAS's own triggers (USER, not ALL) for the bulk update: ALL
        # also targets internal referential-integrity triggers, which requires
        # superuser privileges the upgrade role does not have.
        op.execute("ALTER TABLE maasserver_interface DISABLE TRIGGER USER;")
        connection.execute(
            sa.text(
                "UPDATE maasserver_interface SET mac_address = :mac "
                "WHERE id = :id"
            ),
            changed,
        )
        op.execute("ALTER TABLE maasserver_interface ENABLE TRIGGER USER;")

    op.create_check_constraint(
        _CHECK_CONSTRAINT_NAME,
        "maasserver_interface",
        "mac_address IS NULL OR mac_address = '' "
        f"OR mac_address ~ '{_CANONICAL_MAC_RE}'",
    )


def downgrade() -> None:
    # We do not support migration downgrade
    pass
