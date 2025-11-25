"""oidc_user_creation

Revision ID: 0010
Revises: 0009
Create Date: 2025-11-24 14:54:43.706475+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "maasserver_userprofile",
        sa.Column("provider_id", sa.BigInteger(), nullable=True),
    )

    op.create_foreign_key(
        "maasserver_userprofile_provider_id_fkey",
        "maasserver_userprofile",
        "maasserver_oidc_provider",
        ["provider_id"],
        ["id"],
        ondelete="CASCADE",
        initially="DEFERRED",
        deferrable=True,
    )


def downgrade() -> None:
    pass
