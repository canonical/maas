"""Migrate BMC unique index from MD5 to SHA-256

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-25 00:00:00.000000+00:00

"""

from typing import Sequence

from alembic import op  # type: ignore

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the old md5-based unique index.
    op.execute("DROP INDEX IF EXISTS maasserver_bmc_power_type_parameters_idx")
    # Recreate with SHA-256 (native PostgreSQL 11+ function).
    op.execute(
        """
        CREATE UNIQUE INDEX maasserver_bmc_power_type_parameters_idx
        ON maasserver_bmc
        USING btree (power_type, sha256((power_parameters)::text::bytea))
        WHERE ((power_type)::text <> 'manual'::text)
        """
    )


def downgrade() -> None:
    pass
