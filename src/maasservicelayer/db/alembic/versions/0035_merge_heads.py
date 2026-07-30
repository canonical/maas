#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Merge heads 0033 and 0034

Revision ID: 0035
Revises: 0033, 0034
Create Date: 2026-07-24 00:00:00.000000+00:00

"""

from typing import Sequence

# revision identifiers, used by Alembic.
revision: str = "0035"
down_revision: tuple[str, str] = ("0033", "0034")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
