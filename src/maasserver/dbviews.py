# Copyright 2017-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Postgres Views

Views are implemented in the database to better encapsulate complex queries,
and are recreated during the `dbupgrade` process.
"""

from contextlib import closing
from textwrap import dedent

from django.db import connection

from maasserver.utils.orm import transactional


@transactional
def register_all_views():
    """Register all views into the database."""
    for view_name, view_sql in _ALL_VIEWS.items():
        _register_view(view_name, view_sql)


@transactional
def drop_all_views():
    """Drop all views from the database.

    This is intended to be called before the database is upgraded, so that the
    schema can be freely changed without worrying about whether or not the
    views depend on the schema.
    """
    for view_name in _ALL_VIEWS:
        _drop_view_if_exists(view_name)


@transactional
def register_view(view_name):
    """Register a view by name. CAUTION: this is only for use in tests."""
    _register_view(view_name, _ALL_VIEWS[view_name])


# Note that the `Discovery` model object is backed by this view. Any
# changes made to this view should be reflected there.
maasserver_discovery = dedent(
    """\
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
        neigh.vid AS vid,
        neigh.created AS first_seen,
        GREATEST(neigh.updated, mdns.updated) AS last_seen,
        mdns.id AS mdns_id,
        -- Trust reverse-DNS more than multicast DNS.
        COALESCE(rdns.hostname, mdns.hostname) AS hostname,
        node.id AS observer_id,
        node.system_id AS observer_system_id,
        node.hostname AS observer_hostname, -- This will be the rack hostname.
        iface.id AS observer_interface_id,
        iface.name AS observer_interface_name,
        fabric.id AS fabric_id,
        fabric.name AS fabric_name,
        -- Note: This VLAN is associated with the physical interface, so the
        -- actual observed VLAN is actually the 'vid' value on the 'fabric'.
        -- (this may or may not have an associated VLAN interface on the rack;
        -- we can sometimes see traffic from unconfigured VLANs.)
        vlan.id AS vlan_id,
        CASE
            WHEN neigh.ip = vlan.external_dhcp THEN TRUE
            ELSE FALSE
        END AS is_external_dhcp,
        subnet.id AS subnet_id,
        subnet.cidr AS subnet_cidr,
        MASKLEN(subnet.cidr) AS subnet_prefixlen
    FROM maasserver_neighbour neigh
    JOIN maasserver_interface iface ON neigh.interface_id = iface.id
    JOIN maasserver_node node ON node.current_config_id = iface.node_config_id
    JOIN maasserver_vlan vlan ON iface.vlan_id = vlan.id
    JOIN maasserver_fabric fabric ON vlan.fabric_id = fabric.id
    LEFT JOIN maasserver_mdns mdns ON mdns.ip = neigh.ip
    LEFT JOIN maasserver_rdns rdns ON rdns.ip = neigh.ip
    LEFT JOIN maasserver_subnet subnet ON (
        vlan.id = subnet.vlan_id
        -- This checks if the IP address is within a known subnet.
        AND neigh.ip << subnet.cidr
    )
    ORDER BY
        neigh.mac_address,
        neigh.ip,
        neigh.updated DESC, -- We want the most recently seen neighbour.
        rdns.updated DESC, -- We want the most recently seen reverse DNS entry.
        mdns.updated DESC, -- We want the most recently seen mDNS hostname.
        subnet_prefixlen DESC -- We want the best-match CIDR.
    """
)

# Pairs of IP addresses that can route between nodes. In MAAS all addresses in
# a "space" are mutually routable, so this essentially means finding pairs of
# IP addresses that are in subnets with the same space ID. Typically this view
# should not be used without constraining, say, the sets of nodes, to find
# addresses that are mutually routable between region controllers for example.
maasserver_routable_pairs = dedent(
    """\
    SELECT
           -- "Left" node.
           n_left.id AS left_node_id,
           if_left.id AS left_interface_id,
           subnet_left.id AS left_subnet_id,
           vlan_left.id AS left_vlan_id,
           sip_left.ip AS left_ip,

           -- "Right" node.
           n_right.id AS right_node_id,
           if_right.id AS right_interface_id,
           subnet_right.id AS right_subnet_id,
           vlan_right.id AS right_vlan_id,
           sip_right.ip AS right_ip,

           -- Space that left and right have in commmon. Can be NULL.
           vlan_left.space_id AS space_id,

           -- Relative metric; lower is better.
           CASE
             WHEN if_left.node_config_id = if_right.node_config_id THEN 0
             WHEN subnet_left.id = subnet_right.id THEN 1
             WHEN vlan_left.id = vlan_right.id THEN 2
             WHEN vlan_left.space_id IS NOT NULL THEN 3
             ELSE 4  -- The NULL space.
           END AS metric

      FROM maasserver_interface AS if_left
      JOIN maasserver_node AS n_left
        ON n_left.current_config_id = if_left.node_config_id
      JOIN maasserver_interface_ip_addresses AS ifia_left
        ON if_left.id = ifia_left.interface_id
      JOIN maasserver_staticipaddress AS sip_left
        ON ifia_left.staticipaddress_id = sip_left.id
      JOIN maasserver_subnet AS subnet_left
        ON sip_left.subnet_id = subnet_left.id
      JOIN maasserver_vlan AS vlan_left
        ON subnet_left.vlan_id = vlan_left.id
      JOIN maasserver_vlan AS vlan_right
        ON vlan_left.space_id IS NOT DISTINCT FROM vlan_right.space_id
      JOIN maasserver_subnet AS subnet_right
        ON vlan_right.id = subnet_right.vlan_id
      JOIN maasserver_staticipaddress AS sip_right
        ON subnet_right.id = sip_right.subnet_id
      JOIN maasserver_interface_ip_addresses AS ifia_right
        ON sip_right.id = ifia_right.staticipaddress_id
      JOIN maasserver_interface AS if_right
        ON ifia_right.interface_id = if_right.id
      JOIN maasserver_node AS n_right
        ON if_right.node_config_id = n_right.current_config_id
     WHERE if_left.enabled AND sip_left.ip IS NOT NULL
       AND if_right.enabled AND sip_right.ip IS NOT NULL
       AND family(sip_left.ip) = family(sip_right.ip)
    """
)

# Relationship between nodes and pods they host.
maasserver_podhost = dedent(
    """\
    SELECT
            pod.id::bigint << 32 | node.id AS id,
            node.id AS node_id,
            node.system_id as system_id,
            node.hostname as hostname,
            pod.id AS pod_id,
            pod.name AS pod_name,
            pod.power_type,
            if.id AS interface_id,
            if.name AS interface_name,
            ip.id AS staticipaddress_id,
            ip.ip
        FROM maasserver_bmc pod
        LEFT JOIN maasserver_staticipaddress ip
            ON pod.ip_address_id = ip.id AND pod.bmc_type = 1
        LEFT JOIN maasserver_interface_ip_addresses ifip
            ON ifip.staticipaddress_id = ip.id
        LEFT JOIN maasserver_interface if ON if.id = ifip.interface_id
        LEFT JOIN maasserver_node node
            ON node.current_config_id = if.node_config_id
"""
)


_ALL_VIEWS = {
    "maasserver_discovery": maasserver_discovery,
    "maasserver_routable_pairs": maasserver_routable_pairs,
    "maasserver_podhost": maasserver_podhost,
}


def _drop_view_if_exists(view_name):
    """Re-registers the specified view."""
    with closing(connection.cursor()) as cursor:
        cursor.execute(f"DROP VIEW IF EXISTS {view_name}")


def _register_view(view_name, view_sql):
    """Re-registers the specified view."""
    with closing(connection.cursor()) as cursor:
        cursor.execute(f"CREATE OR REPLACE VIEW {view_name} AS ({view_sql})")
