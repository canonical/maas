"""create_usergroup_table

Revision ID: 0019
Revises: 0018
Create Date: 2026-02-27 07:49:00.000000+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "maasserver_usergroup",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False
        ),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        "maasserver_usergroup_name_idx",
        "maasserver_usergroup",
        ["name"],
        unique=True,
    )

    # Create the users/administrator group automatically.
    op.execute("""
    INSERT INTO maasserver_usergroup (created, updated, name, description)
    VALUES (now(), now(), 'Administrators', 'Default administrators group');
    """)

    op.execute("""
    INSERT INTO maasserver_usergroup (created, updated, name, description)
    VALUES (now(), now(), 'Users', 'Default users group');
    """)


def downgrade() -> None:
    # We do not support migration downgrade
    pass
