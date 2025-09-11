# Copyright 2017-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Postgres Views

Views are implemented in the database to better encapsulate complex queries,
and are recreated during the `dbupgrade` process.
"""

from contextlib import closing

from django.db import connection

from maasserver.utils.orm import transactional

# The views that were defined in django before 3.7. Remove this in 4.0 when we can assume that every environment has already
# initialized alembic.
_ALL_VIEWS = {
    "maasserver_discovery",
    "maasserver_routable_pairs",
    "maasserver_podhost",
    "maasserver_ui_subnet_view",
}


@transactional
def drop_all_views():
    """Drop all views from the database.

    This is intended to be called before the database is upgraded, so that the
    schema can be freely changed without worrying about whether or not the
    views depend on the schema.
    """
    for view_name in _ALL_VIEWS:
        _drop_view_if_exists(view_name)


def _drop_view_if_exists(view_name):
    """Re-registers the specified view."""
    with closing(connection.cursor()) as cursor:
        cursor.execute(f"DROP VIEW IF EXISTS {view_name}")
