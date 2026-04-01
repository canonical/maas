# Copyright 2026 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""add_ztp_fields_to_switch

Revision ID: 0022
Revises: 0021
Create Date: 2026-04-01 00:00:00.000000+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add ZTP-related fields to the maasserver_switch table."""
    op.add_column(
        "maasserver_switch",
        sa.Column(
            "ztp_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "maasserver_switch",
        sa.Column("ztp_script_key", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "maasserver_switch",
        sa.Column(
            "ztp_delivery_mechanism", sa.String(length=32), nullable=True
        ),
    )
    op.add_column(
        "maasserver_switch",
        sa.Column("mgmt_mac_address", sa.String(length=17), nullable=True),
    )


def downgrade() -> None:
    # We do not support migration downgrade
    pass
