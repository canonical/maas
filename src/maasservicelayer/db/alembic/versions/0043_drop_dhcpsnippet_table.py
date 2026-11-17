#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Drop the DHCP snippet table and its websocket triggers

DHCP snippets were deprecated in 3.6 and are no longer supported. The
``maasserver_versionedtextfile`` rows holding snippet values (including their
previous versions) are only referenced by snippets, so they are removed too.

Revision ID: 0043
Revises: 0042
Create Date: 2026-11-06 00:00:00.000000+00:00

"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for event in ("create", "update", "delete"):
        op.execute(
            f"DROP TRIGGER IF EXISTS dhcpsnippet_dhcpsnippet_{event}_notify "
            "ON maasserver_dhcpsnippet;"
        )
        op.execute(f"DROP FUNCTION IF EXISTS dhcpsnippet_{event}_notify;")

    op.execute(
        """
        CREATE TEMPORARY TABLE dhcpsnippet_value_ids ON COMMIT DROP AS
        WITH RECURSIVE snippet_values(id) AS (
            SELECT value_id FROM maasserver_dhcpsnippet
            UNION
            SELECT vtf.previous_version_id
            FROM maasserver_versionedtextfile vtf
            JOIN snippet_values sv ON vtf.id = sv.id
            WHERE vtf.previous_version_id IS NOT NULL
        )
        SELECT id FROM snippet_values;
        """
    )
    op.execute("DROP TABLE maasserver_dhcpsnippet;")
    op.execute(
        """
        DELETE FROM maasserver_versionedtextfile
        WHERE id IN (SELECT id FROM dhcpsnippet_value_ids);
        """
    )


def downgrade() -> None:
    # we don't support migration downgrade
    pass
