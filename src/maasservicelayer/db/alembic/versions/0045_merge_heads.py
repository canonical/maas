#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Merge heads 0043 and 0044

Revision ID: 0045
Revises: 0043, 0044
Create Date: 2026-10-20 00:00:00.000000+00:00

"""

from typing import Sequence

# revision identifiers, used by Alembic.
revision: str = "0045"
down_revision: tuple[str, str] = ("0043", "0044")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
