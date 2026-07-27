"""Drop install_kvm and register_vmhost columns from maasserver_node table

Revision ID: 0036
Revises: 0035
Create Date: 2026-07-27 07:28:14.898000+00:00

"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column(
        "maasserver_node",
        "install_kvm",
    )
    op.drop_column(
        "maasserver_node",
        "register_vmhost",
    )


def downgrade() -> None:
    # we don't support migration downgrade
    pass
