"""add config column for oidc

This migration descends from 0030 (the common ancestor shared with the
3.8 branch) so it can be backported to 3.8 without introducing a
conflicting definition of revision 0033. On master it branches alongside
0032, and the resulting heads are reconciled by the 0034 merge migration.

Revision ID: 0033
Revises: 0030
Create Date: 2026-07-22 11:32:43.402422+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0033"
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
