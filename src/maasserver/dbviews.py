# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Postgres Views

Views are implemented in the database to better encapsulate complex queries,
and are recreated during the `dbupgrade` process.
"""

__all__ = [
    "register_all_views",
    ]

from contextlib import closing
from textwrap import dedent

from django.db import connection
from maasserver.utils.orm import transactional


def _register_view(view_name, view_sql):
    """Re-registers the specified view."""
    view_sql = dedent("""\
        DROP VIEW IF EXISTS %s;
        CREATE VIEW %s AS (%s);
        """) % (view_name, view_name, view_sql)
    with closing(connection.cursor()) as cursor:
        cursor.execute(view_sql)

# Dictionary of view_name: view_sql tuples which describe the database views.
_ALL_VIEWS = {
    # Note that the `Discovery` model object is backed by this view. Any
    # changes made to this view should be reflected there.
    "maasserver_discovery":
    dedent("""\
    SELECT
        DISTINCT ON (neigh.mac_address, neigh.ip)
        neigh.id AS id, -- Django needs a primary key for the object.
        -- The following will create a string like "<ip>,<mac>", convert
        -- it to base64, and strip out any embedded linefeeds.
        REPLACE(ENCODE(BYTEA(TRIM(TRAILING '/32' FROM neigh.ip::TEXT)
            || ',' || neigh.mac_address::text), 'base64'), CHR(10), '')
            AS discovery_id, -- This can be used as a surrogate key.
        neigh.id AS neighbour_id,
        neigh.ip AS ip,
        neigh.mac_address AS mac_address,
        GREATEST(neigh.updated, mdns.updated) AS last_seen,
        mdns.id AS mdns_id,
        mdns.hostname AS hostname,
        node.id AS observer_id,
        node.system_id AS observer_system_id,
        node.hostname AS observer_hostname, -- This will be the rack hostname.
        iface.id AS observer_interface_id,
        iface.name AS observer_interface_name,
        fabric.id AS fabric_id,
        fabric.name AS fabric_name,
        vlan.id AS vlan_id,
        vlan.vid AS vid
    FROM maasserver_neighbour neigh
    JOIN maasserver_interface iface ON neigh.interface_id = iface.id
    JOIN maasserver_node node ON node.id = iface.node_id
    JOIN maasserver_vlan vlan ON iface.vlan_id = vlan.id
    JOIN maasserver_fabric fabric ON vlan.fabric_id = fabric.id
    LEFT OUTER JOIN maasserver_mdns mdns ON mdns.ip = neigh.ip
    ORDER BY
        neigh.mac_address,
        neigh.ip,
        neigh.updated DESC, -- We want the most recently seen neighbour.
        mdns.updated DESC -- We want the most recently seen hostname.
    """),
}


@transactional
def register_all_views():
    """Register all views into the database."""
    for view_name, view_sql in _ALL_VIEWS.items():
        _register_view(view_name, view_sql)
