#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Merge heads 0024 and 0026

Revision ID: 0030
Revises: 0024, 0026
Create Date: 2026-07-20 00:00:00.000000+00:00

"""

from typing import Sequence

# revision identifiers, used by Alembic.
revision: str = "0030"
down_revision: tuple[str, str] = ("0024", "0026")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
