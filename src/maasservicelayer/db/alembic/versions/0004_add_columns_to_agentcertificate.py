# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Add columns to agentcertificate

Revision ID: 0004
Revises: 0003
Create Date: 2025-08-14 08:59:33.954732+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add created and updated columns
    # - add columns as nullable,
    op.add_column(
        "maasserver_agentcertificate",
        sa.Column("created", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "maasserver_agentcertificate",
        sa.Column("updated", sa.DateTime(timezone=True), nullable=True),
    )
    # - backfill columns with current timestamp
    op.execute("""
        UPDATE maasserver_agentcertificate
        SET created = NOW(), updated = NOW()
        WHERE created IS NULL OR updated IS NULL
    """)
    # - alter the column to be non-nullable
    op.alter_column("maasserver_agentcertificate", "created", nullable=False)
    op.alter_column("maasserver_agentcertificate", "updated", nullable=False)


def downgrade() -> None:
    op.drop_column("maasserver_agentcertificate", "updated")
    op.drop_column("maasserver_agentcertificate", "created")
