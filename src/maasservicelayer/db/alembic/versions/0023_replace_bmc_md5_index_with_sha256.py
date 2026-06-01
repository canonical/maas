# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Replace BMC power_parameters MD5 index with SHA256.

Revision ID: 0023
Revises: 0022
Create Date: 2026-06-10 00:00:00.000000+00:00

The md5() PostgreSQL function is blocked under FIPS mode. Replace the
unique index to use sha256(bytea) instead, which is a built-in function
(no extension required).
"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP INDEX maasserver_bmc_power_type_parameters_idx")
    op.execute(
        """
        CREATE UNIQUE INDEX maasserver_bmc_power_type_parameters_idx
        ON maasserver_bmc USING btree (
            power_type,
            sha256(power_parameters::text::bytea)
        )
        WHERE ((power_type)::text <> 'manual'::text);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX maasserver_bmc_power_type_parameters_idx")
    op.execute(
        """
        CREATE UNIQUE INDEX maasserver_bmc_power_type_parameters_idx
        ON maasserver_bmc USING btree (
            power_type,
            md5((power_parameters)::text)
        )
        WHERE ((power_type)::text <> 'manual'::text);
        """
    )
