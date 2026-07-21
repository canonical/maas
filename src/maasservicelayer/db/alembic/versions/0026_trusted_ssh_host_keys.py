# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Create trusted SSH host keys table

Revision ID: 0026
Revises: 0025
Create Date: 2026-06-25 00:00:00.000000+00:00

"""

from typing import Sequence

from alembic import op  # type: ignore
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "maasserver_trustedsshhostkey",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("key_type", sa.String(length=64), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "host", "key_type", "public_key", name="uq_trusted_host_key"
        ),
    )


def downgrade() -> None:
    pass
