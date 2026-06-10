# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Replace BMC power_parameters MD5 index with SHA256.

Revision ID: 0023
Revises: 0022
Create Date: 2026-06-10 00:00:00.000000+00:00

The md5() PostgreSQL function is blocked under FIPS mode. Replace the
unique index to use sha256(bytea) instead, which is a built-in function
(no extension required).

convert_to(text, 'UTF8') is the correct way to obtain the raw UTF-8
bytes of a text value, but it is only STABLE, not IMMUTABLE, so it
cannot be used directly in an index expression.  We wrap it in a small
IMMUTABLE SQL function so that PostgreSQL accepts it as an index
expression.
"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CREATE_HELPER = """
CREATE OR REPLACE FUNCTION maasserver_text_to_bytea(t text)
RETURNS bytea LANGUAGE SQL IMMUTABLE AS $$
    SELECT pg_catalog.decode(
        pg_catalog.encode(pg_catalog.convert_to(t, 'UTF8'), 'hex'),
        'hex'
    );
$$;
"""

_DROP_HELPER = "DROP FUNCTION IF EXISTS maasserver_text_to_bytea(text);"


def upgrade() -> None:
    op.execute(_CREATE_HELPER)
    op.execute("DROP INDEX maasserver_bmc_power_type_parameters_idx")
    op.execute(
        """
        CREATE UNIQUE INDEX maasserver_bmc_power_type_parameters_idx
        ON maasserver_bmc USING btree (
            power_type,
            sha256(public.maasserver_text_to_bytea(power_parameters::text))
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
    op.execute(_DROP_HELPER)
