"""update_oidc_provider_columns

Revision ID: 0017
Revises: 0016
Create Date: 2026-02-02 13:37:34.650628+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "maasserver_oidc_provider",
        sa.Column("token_type", sa.Integer(), nullable=False),
    )
    op.drop_constraint(
        "maasserver_oidcrevokedtoken_provider_id_fkey",
        "maasserver_oidcrevokedtoken",
        type_="foreignkey",
    )
    op.create_foreign_key(
        None,
        "maasserver_oidcrevokedtoken",
        "maasserver_oidc_provider",
        ["provider_id"],
        ["id"],
        ondelete="CASCADE",
        initially="DEFERRED",
        deferrable=True,
    )


def downgrade() -> None:
    # We do not support migration downgrade
    pass
