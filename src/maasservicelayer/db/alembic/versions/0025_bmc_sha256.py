# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Migrate BMC unique index from MD5 to SHA-256

Revision ID: 0025
Revises: 0004
Create Date: 2026-06-25 00:00:00.000000+00:00

"""

from typing import Sequence

from alembic import op  # type: ignore

# revision identifiers, used by Alembic.
revision: str = "0025"
down_revision: str = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The unique index keys on a SHA-256 digest of power_parameters because the
    # raw jsonb can exceed the btree index row-size limit. SHA-256 is
    # collision-resistant (so distinct params never collide into a false
    # uniqueness violation) and FIPS-approved, unlike the previous md5().
    #
    # We use pgcrypto's digest(text, 'sha256') rather than the built-in
    # sha256(bytea): digest() accepts text directly (avoiding a lossy
    # text->bytea cast that mis-parses backslash escapes) and routes to the
    # OpenSSL provider, i.e. the FIPS-validated cryptographic module.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    # Drop the old md5-based unique index.
    op.execute("DROP INDEX IF EXISTS maasserver_bmc_power_type_parameters_idx")
    op.execute(
        """
        CREATE UNIQUE INDEX maasserver_bmc_power_type_parameters_idx
        ON maasserver_bmc
        USING btree (power_type, digest((power_parameters)::text, 'sha256'))
        WHERE ((power_type)::text <> 'manual'::text)
        """
    )


def downgrade() -> None:
    pass
