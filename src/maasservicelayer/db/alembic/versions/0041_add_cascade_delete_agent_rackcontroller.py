# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Add CASCADE DELETE to agent rackcontroller_id foreign key.

When a node is deleted, any agents that reference it as their
rackcontroller should be automatically deleted.

Revision ID: 0041
Revises: 0040
Create Date: 2026-10-09 15:18:22.014892-03:00

"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "maasserver_agent_rackcontroller_id_fkey",
        "maasserver_agent",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "maasserver_agent_rackcontroller_id_fkey",
        "maasserver_agent",
        "maasserver_node",
        ["rackcontroller_id"],
        ["id"],
        ondelete="CASCADE",
        initially="DEFERRED",
        deferrable=True,
    )


def downgrade() -> None:
    # We do not support migration downgrade.
    pass
