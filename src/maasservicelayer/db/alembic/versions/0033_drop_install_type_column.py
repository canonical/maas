"""Drop install_type column from maasserver_controllerinfo table

Revision ID: 0033
Revises: 0032
Create Date: 2026-07-22 09:13:41.571567+00:00

"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column(
        "maasserver_controllerinfo",
        "install_type",
    )


def downgrade() -> None:
    # we don't support migration downgrade
    pass
