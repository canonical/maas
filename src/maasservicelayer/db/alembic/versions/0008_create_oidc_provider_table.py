"""create_oidc_provider_table

Revision ID: 0008
Revises: 0007
Create Date: 2025-10-13 11:11:53.915160+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "maasserver_oidc_provider",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False
        ),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret", sa.String(length=255), nullable=False),
        sa.Column("issuer_url", sa.String(length=512), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("scopes", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )


def downgrade() -> None:
    pass
