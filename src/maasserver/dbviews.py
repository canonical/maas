# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Postgres Views

Views are implemented in the database to better encapsulate complex queries,
and are recreated every time MAAS starts up in order to avoid the need to
create migrations for views.
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

# Tuple of (view_name, view_sql) tuples which describe the database views.
_ALL_VIEWS = (
    ("maasserver_discovery",
        dedent("""\
        SELECT
            DISTINCT ON (neigh.mac_address, neigh.ip)
            neigh.id as neigh_id,
            neigh.ip as ip,
            neigh.mac_address as mac,
            neigh.updated as last_seen,
            mdns.id as mdns_id,
            mdns.hostname as hostname,
            node.id as node_id,
            node.system_id as node_system_id,
            node.hostname as node_hostname, -- This will be the rack's hostname
            fabric.id as fabric_id,
            fabric.name as fabric_name,
            vlan.id as vlan_id,
            vlan.vid as vid
        FROM maasserver_neighbour neigh
        JOIN maasserver_interface iface ON neigh.interface_id = iface.id
        JOIN maasserver_node node ON node.id = iface.node_id
        JOIN maasserver_vlan vlan ON iface.vlan_id = vlan.id
        JOIN maasserver_fabric fabric ON vlan.fabric_id = fabric.id
        LEFT OUTER JOIN maasserver_mdns mdns ON mdns.ip = neigh.ip
        ORDER BY
            neigh.mac_address,
            neigh.ip,
            neigh.updated DESC, -- we want the most recently seen neighbour
            mdns.updated DESC -- we want the most recently seen hostname
        """)),
)


@transactional
def register_all_views():
    """Register all views into the database."""
    for view_name, view_sql in _ALL_VIEWS:
        _register_view(view_name, view_sql)
