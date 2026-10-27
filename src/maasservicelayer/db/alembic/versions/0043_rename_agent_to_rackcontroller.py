# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Rename the MAAS agent to rack controller.

The maasserver_agent table becomes maasserver_rackcontroller and its
rackcontroller_id column, which references the rack controller node,
becomes node_id. Constraints and the identity sequence are renamed to
match, and the per-node service status entry is renamed accordingly.

Revision ID: 0043
Revises: 0042
Create Date: 2026-10-27 00:00:00.000000+00:00

"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT_RENAMES = [
    ("maasserver_agent_pkey", "maasserver_rackcontroller_pkey"),
    ("maasserver_agent_uuid_key", "maasserver_rackcontroller_uuid_key"),
    (
        "maasserver_agent_rack_id_rackcontroller_id_key",
        "maasserver_rackcontroller_rack_id_node_id_key",
    ),
    (
        "maasserver_agent_rack_id_fkey",
        "maasserver_rackcontroller_rack_id_fkey",
    ),
    (
        "maasserver_agent_rackcontroller_id_fkey",
        "maasserver_rackcontroller_node_id_fkey",
    ),
]


def upgrade() -> None:
    op.rename_table("maasserver_agent", "maasserver_rackcontroller")
    op.alter_column(
        "maasserver_rackcontroller",
        "rackcontroller_id",
        new_column_name="node_id",
    )
    op.execute(
        "ALTER SEQUENCE maasserver_agent_id_seq "
        "RENAME TO maasserver_rackcontroller_id_seq"
    )
    for old_name, new_name in _CONSTRAINT_RENAMES:
        op.execute(
            f"ALTER TABLE maasserver_rackcontroller "
            f"RENAME CONSTRAINT {old_name} TO {new_name}"
        )
    # PostgreSQL 18+ catalogs NOT NULL constraints with generated names;
    # older versions don't have them, so rename whatever exists.
    op.execute(
        """
        DO $$
        DECLARE
            constraint_name text;
        BEGIN
            FOR constraint_name IN
                SELECT conname FROM pg_constraint
                WHERE conrelid = 'maasserver_rackcontroller'::regclass
                  AND conname LIKE 'maasserver\\_agent\\_%'
            LOOP
                EXECUTE format(
                    'ALTER TABLE maasserver_rackcontroller '
                    'RENAME CONSTRAINT %I TO %I',
                    constraint_name,
                    replace(
                        constraint_name,
                        'maasserver_agent_',
                        'maasserver_rackcontroller_'
                    )
                );
            END LOOP;
        END
        $$;
        """
    )
    op.execute(
        "UPDATE maasserver_service SET name = 'rack-controller' "
        "WHERE name = 'agent'"
    )


def downgrade() -> None:
    # We do not support migration downgrade.
    pass
