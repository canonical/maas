# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS Agent Enrollment

Revision ID: 0006
Revises: 0005
Create Date: 2025-08-01 08:32:23.685263+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "maasserver_rack",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False
        ),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "maasserver_agent",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False
        ),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("rack_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "rackcontroller_id", sa.BigInteger(), nullable=True
        ),  # change to False once MAE is complete
        sa.ForeignKeyConstraint(
            ["rack_id"],
            ["maasserver_rack.id"],
        ),
        sa.ForeignKeyConstraint(
            ["rackcontroller_id"],
            ["maasserver_node.id"],
        ),
        sa.UniqueConstraint("uuid"),
        sa.UniqueConstraint("rack_id", "rackcontroller_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "maasserver_bootstraptoken",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False
        ),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("secret", sa.String(length=64), nullable=False),
        sa.Column("rack_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["rack_id"],
            ["maasserver_rack.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("secret"),
    )


def downgrade() -> None:
    op.drop_table("maasserver_bootstraptoken")
    op.drop_table("maasserver_agent")
    op.drop_table("maasserver_rack")
