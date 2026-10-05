# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Clear removed Microsoft OCS power configurations.

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


def upgrade() -> None:
    conn = op.get_bind()
    bmc = sa.table("maasserver_bmc", sa.column("id"), sa.column("power_type"))
    node = sa.table(
        "maasserver_node",
        sa.column("id"),
        sa.column("bmc_id"),
        sa.column("instance_power_parameters", JSONB),
    )
    bmc_ids = list(
        conn.execute(
            sa.select(bmc.c.id).where(bmc.c.power_type == "msftocs")
        ).scalars()
    )
    if not bmc_ids:
        return

    node_ids = conn.execute(
        node.update()
        .where(node.c.bmc_id.in_(bmc_ids))
        .values(bmc_id=None, instance_power_parameters={})
        .returning(node.c.id)
    ).scalars()
    paths = [f"node/{node_id}/power-parameters" for node_id in node_ids]
    paths.extend(f"bmc/{bmc_id}/power-parameters" for bmc_id in bmc_ids)
    secret = sa.table("maasserver_secret", sa.column("path"))
    conn.execute(secret.delete().where(secret.c.path.in_(paths)))

    # Vault cleanup consumes these tombstones after commit; upgrades must not
    # call Vault or lose the paths needed to delete the external secrets.
    vault_secret = sa.table(
        "maasserver_vaultsecret", sa.column("path"), sa.column("deleted")
    )
    conn.execute(
        vault_secret.update()
        .where(vault_secret.c.path.in_(paths))
        .values(deleted=True)
    )
    relationship = sa.table(
        "maasserver_bmcroutablerackcontrollerrelationship", sa.column("bmc_id")
    )
    conn.execute(
        relationship.delete().where(relationship.c.bmc_id.in_(bmc_ids))
    )
    conn.execute(bmc.delete().where(bmc.c.id.in_(bmc_ids)))

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
    conn.execute(
        notification.insert().values(
            created=sa.func.now(),
            updated=sa.func.now(),
            ident="power_driver_msftocs_removed",
            users=True,
            admins=True,
            category="warning",
            dismissable=True,
            context={},
            message=(
                "Microsoft OCS (msftocs) power driver support has been removed "
                "and its power configuration has been cleared. Configure the "
                "Webhook power driver with a compatible external service to "
                "restore power control. "
                '<a class="p-link--external" href="https://discourse.maas.io/t/'
                "creating-a-web-service-for-the-maas-webhook-power-driver/3756"
                '">Creating a service for the Webhook power driver</a>.'
            ),
        )
    )


def downgrade() -> None:
    # We do not support migration downgrade.
    pass
