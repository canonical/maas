"""Drop django_migrations and maasserver_largefile tables


Environments that are migrating from 3.x must have gone through 3.8,
which already moved the images out of the database and moved away from django
migrations. Hence, we can safely drop everything here.

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
    op.drop_table("django_migrations", if_exists=True)
    op.drop_column(
        "maasserver_bootresourcefile", "largefile_id", if_exists=True
    )
    op.drop_table("maasserver_largefile", if_exists=True)


def downgrade() -> None:
    # we don't support migration downgrade
    pass
