# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Clear configurations for removed power drivers.

Revision ID: 0041
Revises: 0040
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REMOVED_POWER_DRIVERS = {
    "dli": "Digital Loggers, Inc. PDU",
    "eaton": "Eaton PDU",
    "mscm": "HP Moonshot - iLO Chassis Manager",
    "msftocs": "Microsoft OCS",
    "nova": "OpenStack Nova",
    "openbmc": "OpenBMC",
    "ucsm": "Cisco UCS Manager",
    "wedge": "Facebook's Wedge",
}


def upgrade() -> None:
    conn = op.get_bind()
    bmc = sa.table("maasserver_bmc", sa.column("id"), sa.column("power_type"))
    node = sa.table(
        "maasserver_node",
        sa.column("id"),
        sa.column("bmc_id"),
        sa.column("instance_power_parameters", JSONB),
    )
    secret = sa.table("maasserver_secret", sa.column("path"))
    vault_secret = sa.table(
        "maasserver_vaultsecret", sa.column("path"), sa.column("deleted")
    )
    relationship = sa.table(
        "maasserver_bmcroutablerackcontrollerrelationship", sa.column("bmc_id")
    )
    notification = sa.table(
        "maasserver_notification",
        sa.column("created"),
        sa.column("updated"),
        sa.column("ident"),
        sa.column("users"),
        sa.column("admins"),
        sa.column("message"),
        sa.column("context", JSONB),
        sa.column("category"),
        sa.column("dismissable"),
    )
    for power_type, description in REMOVED_POWER_DRIVERS.items():
        bmc_ids = list(
            conn.execute(
                sa.select(bmc.c.id).where(bmc.c.power_type == power_type)
            ).scalars()
        )
        if not bmc_ids:
            continue

        node_ids = conn.execute(
            node.update()
            .where(node.c.bmc_id.in_(bmc_ids))
            .values(bmc_id=None, instance_power_parameters={})
            .returning(node.c.id)
        ).scalars()
        paths = [f"node/{node_id}/power-parameters" for node_id in node_ids]
        paths.extend(f"bmc/{bmc_id}/power-parameters" for bmc_id in bmc_ids)
        conn.execute(secret.delete().where(secret.c.path.in_(paths)))

        # Retain Vault paths for asynchronous cleanup without contacting Vault
        # during the upgrade.
        conn.execute(
            vault_secret.update()
            .where(vault_secret.c.path.in_(paths))
            .values(deleted=True)
        )
        conn.execute(
            relationship.delete().where(relationship.c.bmc_id.in_(bmc_ids))
        )
        conn.execute(bmc.delete().where(bmc.c.id.in_(bmc_ids)))
        conn.execute(
            notification.insert().values(
                created=sa.func.now(),
                updated=sa.func.now(),
                ident=f"power_driver_{power_type}_removed",
                users=True,
                admins=True,
                category="warning",
                dismissable=True,
                context={},
                message=(
                    f"{description} ({power_type}) power driver support has "
                    "been removed and its power configuration has been "
                    "cleared. Configure the Webhook power driver with a "
                    "compatible external service to restore power control. "
                    '<a class="p-link--external" href="https://discourse.maas.io/t/'
                    "creating-a-web-service-for-the-maas-webhook-power-driver/3756"
                    '">Creating a service for the Webhook power driver</a>.'
                ),
            )
        )


def downgrade() -> None:
    # We do not support migration downgrade.
    pass
