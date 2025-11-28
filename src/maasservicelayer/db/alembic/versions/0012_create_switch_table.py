# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""create_switch_table

Revision ID: 0012
Revises: 0011
Create Date: 2025-11-28 12:00:00.000000+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the maasserver_switch table for storing network switch information."""
    op.create_table(
        "maasserver_switch",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False
        ),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("mac_address", sa.Text(), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("manufacturer", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "vlan_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "maasserver_vlan.id", deferrable=True, initially="DEFERRED"
            ),
            nullable=True,
        ),
        sa.Column(
            "subnet_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "maasserver_subnet.id", deferrable=True, initially="DEFERRED"
            ),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mac_address"),
    )

    # Create indexes
    op.create_index(
        "maasserver_switch_vlan_id_idx",
        "maasserver_switch",
        ["vlan_id"],
        unique=False,
    )
    op.create_index(
        "maasserver_switch_subnet_id_idx",
        "maasserver_switch",
        ["subnet_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the maasserver_switch table."""
    op.drop_index(
        "maasserver_switch_subnet_id_idx",
        table_name="maasserver_switch",
    )
    op.drop_index(
        "maasserver_switch_vlan_id_idx",
        table_name="maasserver_switch",
    )
    op.drop_table("maasserver_switch")
