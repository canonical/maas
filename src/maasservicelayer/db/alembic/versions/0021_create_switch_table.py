# Copyright 2026 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""create_switch_table

Revision ID: 0021
Revises: 0020
Create Date: 2026-03-17 13:50:56.078535+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the maasserver_switch table."""
    op.create_table(
        "maasserver_switch",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False
        ),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "target_image_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "maasserver_bootresource.id",
                deferrable=True,
                initially="DEFERRED",
            ),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "maasserver_switch_target_image_id_idx",
        "maasserver_switch",
        ["target_image_id"],
        unique=False,
    )

    """Add a nullable switch_id column to the maasserver_interface table."""
    op.add_column(
        "maasserver_interface",
        sa.Column("switch_id", sa.BigInteger(), nullable=True),
    )

    op.create_foreign_key(
        "maasserver_interface_switch_id_fkey",
        "maasserver_interface",
        "maasserver_switch",
        ["switch_id"],
        ["id"],
        initially="DEFERRED",
        deferrable=True,
    )

    op.create_index(
        "maasserver_interface_switch_id_idx",
        "maasserver_interface",
        ["switch_id"],
        unique=False,
    )


def downgrade() -> None:
    # We do not support migration downgrade
    pass
