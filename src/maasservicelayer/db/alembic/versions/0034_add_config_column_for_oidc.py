"""add config column for oidc

Revision ID: 0034
Revises: 0030
Create Date: 2026-07-24 11:32:43.402422+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0034"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "maasserver_oidc_provider",
        sa.Column(
            "config", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def downgrade() -> None:
    # we don't support migration downgrade
    pass
