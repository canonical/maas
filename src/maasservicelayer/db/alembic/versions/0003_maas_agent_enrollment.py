"""MAAS Agent Enrollment

Revision ID: 0003
Revises: 0002
Create Date: 2025-08-01 08:32:23.685263+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "maasserver_rack",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False
        ),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "maasserver_agent",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False
        ),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("secret", sa.String(length=64), nullable=False),
        sa.Column("rack_id", sa.BigInteger(), nullable=False),
        sa.Column("rackcontroller_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["rack_id"],
            ["maasserver_rack.id"],
        ),
        sa.ForeignKeyConstraint(
            ["rackcontroller_id"],
            ["maasserver_node.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("secret"),
    )
    op.create_table(
        "maasserver_bootstraptoken",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False
        ),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("secret", sa.String(length=64), nullable=False),
        sa.Column("rack_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["rack_id"],
            ["maasserver_rack.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("secret"),
    )
    op.create_table(
        "maasserver_agentcertificate",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False
        ),
        sa.Column(
            "certificate_fingerprint", sa.String(length=64), nullable=False
        ),
        sa.Column("certificate", sa.LargeBinary(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["maasserver_agent.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("certificate"),
        sa.UniqueConstraint("certificate_fingerprint"),
    )


def downgrade() -> None:
    op.drop_table("maasserver_agentcertificate")
    op.drop_table("maasserver_bootstraptoken")
    op.drop_table("maasserver_agent")
    op.drop_table("maasserver_rack")
