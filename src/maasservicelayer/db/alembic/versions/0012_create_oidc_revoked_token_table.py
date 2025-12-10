"""create_oidc_revoked_token_table

Revision ID: 0012
Revises: 0011
Create Date: 2025-12-07 14:17:23.282060+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "maasserver_oidcrevokedtoken",
        sa.Column(
            "id", sa.Integer(), sa.Identity(always=False), nullable=False
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_email", sa.String(length=150), nullable=False),
        sa.Column("provider_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["maasserver_oidc_provider.id"],
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["user_email"],
            ["auth_user.username"],
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", "provider_id"),
    )
    op.create_index(
        "maasserver_oidcrevokedtoken_provider_id_3d1f3f6b",
        "maasserver_oidcrevokedtoken",
        ["provider_id"],
        unique=False,
    )
    op.create_index(
        "maasserver_oidcrevokedtoken_user_email_5f4d1d18",
        "maasserver_oidcrevokedtoken",
        ["user_email"],
        unique=False,
    )


def downgrade() -> None:
    pass
