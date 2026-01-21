"""create_refresh_token_table

Revision ID: 0016
Revises: 0015
Create Date: 2026-01-20 09:38:39.361969+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "maasserver_refreshtoken",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False
        ),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_user.id"],
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(
        "maasserver_refreshtoken_user_id_5f4d1d1a",
        "maasserver_refreshtoken",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    # We do not support migration downgrade
    pass
