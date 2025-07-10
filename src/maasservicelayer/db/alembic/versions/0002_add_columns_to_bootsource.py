# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Add columns to bootsource

Revision ID: 0002
Revises: 0001
Create Date: 2025-06-24 11:16:07.410600+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add priority column
    # - add the column as nullable,
    op.add_column(
        "maasserver_bootsource",
        sa.Column("priority", sa.Integer(), nullable=True),
    )
    # - backfill priority based on creation order
    #   - newer boot sources (later 'created' timestamps) get higher priority
    #   - values are spaced out (e.g., 10, 20, 30...) to leave room for future
    #     insertions without immediate reordering
    #   - a unique constraint will be added later, so all priorities must be
    #     distinct
    op.execute("""
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created ASC) AS priority
            FROM maasserver_bootsource
        )
        UPDATE maasserver_bootsource
        SET priority = ranked.priority*10
        FROM ranked
        WHERE maasserver_bootsource.id = ranked.id
    """)
    # - alter the column to be nullable
    op.alter_column("maasserver_bootsource", "priority", nullable=False)

    # Add skip_keyring_verification column
    # - add the column as nullable,
    op.add_column(
        "maasserver_bootsource",
        sa.Column(
            "skip_keyring_verification",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    # - backfill skip_keyring_verification based with False (until this change
    #   the keyring was verified)
    op.execute("""
        UPDATE maasserver_bootsource
        SET skip_keyring_verification = TRUE
        WHERE url LIKE '%%.json'
    """)
    # - alter the column to be nullable
    op.alter_column(
        "maasserver_bootsource",
        "skip_keyring_verification",
        server_default=None,
    )

    # Add constraints
    op.create_unique_constraint(
        constraint_name="maasserver_bootsource_priority_key",
        table_name="maasserver_bootsource",
        columns=["priority"],
    )


def downgrade() -> None:
    op.drop_constraint(
        constraint_name="maasserver_bootsource_priority_key",
        table_name="maasserver_bootsource",
        type_="unique",
    )
    op.drop_column("maasserver_bootsource", "skip_keyring_verification")
    op.drop_column("maasserver_bootsource", "priority")
