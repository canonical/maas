# Copyright 2026 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""add_operation_tables

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-08 19:06:32.000000+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create the maasserver_operation table
    op.create_table(
        "maasserver_operation",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False
        ),
        sa.Column("uuid", sa.String(36), nullable=False),
        sa.Column("op_type", sa.String(255), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("resource_type", sa.String(255), nullable=True),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_task", sa.String(255), nullable=True),
        sa.Column("parameters", postgresql.JSONB(), nullable=True),
        sa.Column("result_errors", postgresql.JSONB(), nullable=True),
        sa.Column("is_bulk", sa.Boolean(), nullable=False),
        sa.Column(
            "parent_id",
            sa.String(36),
            sa.ForeignKey("maasserver_operation.uuid"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("auth_user.id"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
    )

    op.create_index(
        "maasserver_operation_parent_id_idx",
        "maasserver_operation",
        ["parent_id"],
    )

    # Create the maasserver_operation_task table
    op.create_table(
        "maasserver_operation_task",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("result_errors", postgresql.JSONB(), nullable=True),
        sa.Column("task_number", sa.Integer(), nullable=False),
        sa.Column(
            "operation_uuid",
            sa.String(36),
            sa.ForeignKey("maasserver_operation.uuid"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "maasserver_operation_task_operation_uuid_idx",
        "maasserver_operation_task",
        ["operation_uuid"],
    )

    # Create the maasserver_machine_operation table
    op.create_table(
        "maasserver_machine_operation",
        sa.Column(
            "operation_uuid",
            sa.String(36),
            sa.ForeignKey("maasserver_operation.uuid"),
        ),
        sa.Column(
            "node_id",
            sa.BigInteger(),
            sa.ForeignKey("maasserver_node.id"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("operation_uuid"),
    )
    op.create_index(
        "maasserver_machine_operation_node_id_idx",
        "maasserver_machine_operation",
        ["node_id"],
    )


def downgrade() -> None:
    # We do not support migration downgrade
    pass
