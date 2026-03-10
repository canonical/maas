# Copyright 2026 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""create_switch_table

Revision ID: 0021
Revises: 0020
Create Date: 2026-03-04 12:00:00.000000+00:00

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
    """Create the maasserver_switch and maasserver_switchinterface tables."""
    # Create Switch table
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

    # Create index for Switch table
    op.create_index(
        "maasserver_switch_target_image_id_idx",
        "maasserver_switch",
        ["target_image_id"],
        unique=False,
    )

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
        ondelete="CASCADE",
        initially="DEFERRED",
        deferrable=True,
    )

    # Create indexes for SwitchInterface table
    op.create_index(
        "maasserver_interface_switch_id_idx",
        "maasserver_interface",
        ["switch_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the maasserver_switch table and remove the FK from maasserver_interface table."""
    op.drop_index(
        "maasserver_interface_switch_id_idx",
        table_name="maasserver_interface",
    )

    op.drop_constraint(
        "maasserver_interface_switch_id_fkey",
        "maasserver_interface",
        type_="foreignkey",
    )

    op.drop_column("maasserver_interface", "switch_id")

    # Drop Switch table
    op.drop_index(
        "maasserver_switch_target_image_id_idx",
        table_name="maasserver_switch",
    )
    op.drop_table("maasserver_switch")
