"""Create maasserver_usergroup_members_view SQL view.

Revision ID: 0020
Revises: 0019
Create Date: 2026-03-03 16:34:42.720984+00:00
"""

from textwrap import dedent
from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    sql = dedent("""\
        SELECT
            (t.object_id)::bigint AS group_id,
            u.id as id,
            u.username as username,
            u.email as email
        FROM
            openfga.tuple t
        JOIN
            auth_user u
            ON u.id = split_part(t._user, ':', 2)::integer
        WHERE
            t.object_type = 'group'
            AND t.relation = 'member'
            AND t.user_type = 'user'
        """)

    op.execute(
        f"""CREATE OR REPLACE VIEW maasserver_usergroup_members_view AS ({sql});"""
    )


def downgrade() -> None:
    # We do not support migration downgrade
    pass
