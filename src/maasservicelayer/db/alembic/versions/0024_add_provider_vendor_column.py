"""add provider vendor column

Revision ID: 0024
Revises: 0023
Create Date: 2026-06-26 12:13:41.571567+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add the column with a temporary server_default so existing providers are
    # backfilled with the GENERIC vendor
    op.add_column(
        "maasserver_oidc_provider",
        sa.Column(
            "vendor",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.alter_column(
        "maasserver_oidc_provider",
        "vendor",
        server_default=None,
    )


def downgrade() -> None:
    # we don't support migration downgrade
    pass
