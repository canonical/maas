"""drop django_migrations table

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-15 17:13:41.571567+00:00

"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("django_migrations", if_exists=True)


def downgrade() -> None:
    # we don't support migration downgrade
    pass
