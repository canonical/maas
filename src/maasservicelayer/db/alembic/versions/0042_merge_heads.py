#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Merge heads 0040 and 0041

Revision ID: 0042
Revises: 0040, 0041
Create Date: 2026-10-13 00:00:00.000000+00:00

"""

from typing import Sequence

# revision identifiers, used by Alembic.
revision: str = "0042"
down_revision: tuple[str, str] = ("0040", "0041")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
