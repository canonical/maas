# Copyright 2026 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""add_rack_power_drivers

Revision ID: 0022
Revises: 0021
Create Date: 2026-03-17 14:00:00.000000+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the rack_power_drivers table."""
    op.create_table(
        "rack_power_drivers",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False
        ),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rack_system_id", sa.String(255), nullable=False),
        sa.Column("driver_name", sa.String(255), nullable=False),
        sa.Column("driver_version", sa.String(255), nullable=False),
        sa.Column(
            "schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.UniqueConstraint(
            "rack_system_id",
            "driver_name",
            "driver_version",
            name="uk_rack_power_drivers_rack_driver_version",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    # We do not support migration downgrade
    pass
