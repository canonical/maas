"""add hardware profile

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-15 12:50:27.092841+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "maasserver_hardwareprofile",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False
        ),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("node_id", sa.BigInteger(), nullable=False),
        sa.Column("architecture", sa.String(length=31), nullable=False),
        sa.Column("cpu_cores", sa.Integer(), nullable=False),
        sa.Column("cpu_speed_mhz", sa.Integer(), nullable=False),
        sa.Column("memory_mb", sa.Integer(), nullable=False),
        sa.Column("disk_count", sa.Integer(), nullable=False),
        sa.Column("total_storage_bytes", sa.BigInteger(), nullable=False),
        sa.Column("nic_count", sa.Integer(), nullable=False),
        sa.Column("gpu_count", sa.Integer(), nullable=False),
        sa.Column("system_vendor", sa.String(length=256), nullable=True),
        sa.Column("system_product", sa.String(length=256), nullable=True),
        sa.Column(
            "hardware_fingerprint", sa.String(length=64), nullable=False
        ),
        sa.Column(
            "storage", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "network", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "accelerators",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["node_id"],
            ["maasserver_node.id"],
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("node_id"),
    )
    op.create_index(
        "maasserver_hardwareprofile_arch_idx",
        "maasserver_hardwareprofile",
        ["architecture"],
        unique=False,
    )
    op.create_index(
        "maasserver_hardwareprofile_cpu_mem_idx",
        "maasserver_hardwareprofile",
        ["cpu_cores", "memory_mb"],
        unique=False,
    )
    op.create_index(
        "maasserver_hardwareprofile_fingerprint_idx",
        "maasserver_hardwareprofile",
        ["hardware_fingerprint"],
        unique=False,
    )
    op.create_index(
        "maasserver_hardwareprofile_gpu_count_idx",
        "maasserver_hardwareprofile",
        ["gpu_count"],
        unique=False,
    )


def downgrade() -> None:
    pass
