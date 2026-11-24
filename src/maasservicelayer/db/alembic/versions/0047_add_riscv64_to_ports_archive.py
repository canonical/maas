#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Add riscv64 to the default ports package repository

Revision ID: 0047
Revises: 0041
Create Date: 2026-11-23 00:00:00.000000+00:00

"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0047"
down_revision: str | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Append riscv64 to populated rows without discarding administrator
    # customizations. NULL and empty rows are reset to the complete default
    # ports architecture list because the service layer requires every ports
    # architecture to be present.
    op.execute(
        """
        UPDATE maasserver_packagerepository
        SET arches = CASE
                WHEN COALESCE(cardinality(arches), 0) = 0
                THEN ARRAY[
                    'armhf',
                    'arm64',
                    'ppc64el',
                    'riscv64',
                    's390x'
                ]::text[]
                ELSE array_append(arches, 'riscv64')
            END,
            updated = now()
        WHERE name = 'ports_archive'
          AND "default" = true
          AND NOT (
              COALESCE(arches, ARRAY[]::text[])
              @> ARRAY['riscv64']::text[]
          );
        """
    )


def downgrade() -> None:
    # we don't support migration downgrade
    pass
