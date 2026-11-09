# Copyright 2026 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Add operation concurrency and resource lookup indexes

Revision ID: 0040
Revises: 0039
Create Date: 2026-09-30 00:00:00.000000+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "maasserver_operation_resource_type_resource_id_idx",
        "maasserver_operation",
        ["resource_type", "resource_id"],
    )
    op.create_index(
        "maasserver_operation_one_in_progress_per_resource_idx",
        "maasserver_operation",
        ["resource_type", "resource_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('ACCEPTED', 'RUNNING', 'CANCELLING')"
        ),
    )


def downgrade() -> None:
    # We do not support migration downgrade
    pass
