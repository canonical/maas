# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestViews:
    _ALL_VIEWS = [
        "maasserver_discovery",
        "maasserver_routable_pairs",
        "maasserver_podhost",
        "maasserver_ui_subnet_view",
        "maasserver_bootsourceselectionstatus_view",
    ]

    async def test_each_view_can_be_used(self, db_connection: AsyncConnection):
        for view_name in self._ALL_VIEWS:
            await db_connection.execute(text(f"SELECT * from {view_name};"))

    async def test_all_views_match_expected(
        self, db_connection: AsyncConnection
    ):
        """Ensure that the DB has exactly the expected views (no more, no less)."""
        query = text("""
            SELECT table_name
            FROM information_schema.views
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        result = await db_connection.execute(query)
        db_views = [row[0] for row in result.fetchall()]

        assert sorted(db_views) == sorted(self._ALL_VIEWS), (
            f"Database views do not match expected list.\n"
            f"Expected: {sorted(self._ALL_VIEWS)}\n"
            f"Found:    {sorted(db_views)}"
        )
