"""Drop install_rackd column from maasserver_node table

Revision ID: 0031
Revises: 0030
Create Date: 2026-07-21 09:13:41.571567+00:00

"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column(
        "maasserver_node",
        "install_rackd",
    )


def downgrade() -> None:
    # we don't support migration downgrade
    pass
