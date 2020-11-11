# Copyright 2017 Canonical Ltd.  This software is licensed under the
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


def _drop_view_if_exists(view_name):
    """Re-registers the specified view."""
    view_sql = "DROP VIEW IF EXISTS %s;" % view_name
    with closing(connection.cursor()) as cursor:
        cursor.execute(view_sql)


def _register_view(view_name, view_sql):
    """Re-registers the specified view."""
    view_sql = (
        dedent(
            """\
        CREATE OR REPLACE VIEW %s AS (%s);
        """
        )
        % (view_name, view_sql)
    )
    with closing(connection.cursor()) as cursor:
        cursor.execute(view_sql)


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
    JOIN maasserver_node node ON node.id = iface.node_id
    JOIN maasserver_vlan vlan ON iface.vlan_id = vlan.id
    JOIN maasserver_fabric fabric ON vlan.fabric_id = fabric.id
    LEFT OUTER JOIN maasserver_mdns mdns ON mdns.ip = neigh.ip
    LEFT OUTER JOIN maasserver_rdns rdns ON rdns.ip = neigh.ip
    LEFT OUTER JOIN maasserver_subnet subnet ON (
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
           if_left.node_id AS left_node_id,
           if_left.id AS left_interface_id,
           subnet_left.id AS left_subnet_id,
           vlan_left.id AS left_vlan_id,
           sip_left.ip AS left_ip,

           -- "Right" node.
           if_right.node_id AS right_node_id,
           if_right.id AS right_interface_id,
           subnet_right.id AS right_subnet_id,
           vlan_right.id AS right_vlan_id,
           sip_right.ip AS right_ip,

           -- Space that left and right have in commmon. Can be NULL.
           vlan_left.space_id AS space_id,

           -- Relative metric; lower is better.
           CASE
             WHEN if_left.node_id = if_right.node_id THEN 0
             WHEN subnet_left.id = subnet_right.id THEN 1
             WHEN vlan_left.id = vlan_right.id THEN 2
             WHEN vlan_left.space_id IS NOT NULL THEN 3
             ELSE 4  -- The NULL space.
           END AS metric

      FROM maasserver_interface AS if_left
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
        LEFT OUTER JOIN maasserver_staticipaddress ip
            ON pod.ip_address_id = ip.id AND pod.bmc_type = 1
        LEFT OUTER JOIN maasserver_interface_ip_addresses ifip
             ON ifip.staticipaddress_id = ip.id
        LEFT OUTER JOIN maasserver_interface if ON if.id = ifip.interface_id
        LEFT OUTER JOIN maasserver_node node ON node.id = if.node_id
"""
)

# Views that are helpful for supporting MAAS.
# These can be batch-run using the maas-region-support-dump script.
maas_support__node_overview = dedent(
    """\
    SELECT
        hostname,
        system_id,
        cpu_count "cpu",
        memory
    FROM maasserver_node
    WHERE
        node_type = 0 -- Machine
    ORDER BY hostname
    """
)

maas_support__device_overview = dedent(
    """\
    SELECT
        node.hostname,
        node.system_id,
        parent.hostname "parent"
    FROM maasserver_node node
    LEFT OUTER JOIN maasserver_node parent
        on node.parent_id = parent.id
    WHERE
        node.node_type = 1
    ORDER BY hostname
    """
)

maas_support__node_networking = dedent(
    """\
    SELECT
        node.hostname,
        iface.id "ifid",
        iface.name,
        iface.type,
        iface.mac_address,
        sip.ip,
        CASE
            WHEN sip.alloc_type = 0 THEN 'AUTO'
            WHEN sip.alloc_type = 1 THEN 'STICKY'
            WHEN sip.alloc_type = 4 THEN 'USER_RESERVED'
            WHEN sip.alloc_type = 5 THEN 'DHCP'
            WHEN sip.alloc_type = 6 THEN 'DISCOVERED'
            ELSE CAST(sip.alloc_type as CHAR)
        END "alloc_type",
        subnet.cidr,
        vlan.vid,
        fabric.name fabric
    FROM maasserver_interface iface
        LEFT OUTER JOIN maasserver_interface_ip_addresses ifip
            on ifip.interface_id = iface.id
        LEFT OUTER JOIN maasserver_staticipaddress sip
            on ifip.staticipaddress_id = sip.id
        LEFT OUTER JOIN maasserver_subnet subnet
            on sip.subnet_id = subnet.id
        LEFT OUTER JOIN maasserver_node node
            on node.id = iface.node_id
        LEFT OUTER JOIN maasserver_vlan vlan
            on vlan.id = subnet.vlan_id
        LEFT OUTER JOIN maasserver_fabric fabric
            on fabric.id = vlan.fabric_id
        ORDER BY
            node.hostname, iface.name, sip.alloc_type
    """
)

maas_support__ip_allocation = dedent(
    """\
    SELECT
        sip.ip,
        CASE
            WHEN sip.alloc_type = 0 THEN 'AUTO'
            WHEN sip.alloc_type = 1 THEN 'STICKY'
            WHEN sip.alloc_type = 4 THEN 'USER_RESERVED'
            WHEN sip.alloc_type = 5 THEN 'DHCP'
            WHEN sip.alloc_type = 6 THEN 'DISCOVERED'
            ELSE CAST(sip.alloc_type as CHAR)
        END "alloc_type",
        subnet.cidr,
        node.hostname,
        iface.id AS "ifid",
        iface.name AS "ifname",
        iface.type AS "iftype",
        iface.mac_address,
        bmc.power_type
        FROM maasserver_staticipaddress sip
            LEFT OUTER JOIN maasserver_subnet subnet
                ON subnet.id = sip.subnet_id
            LEFT OUTER JOIN maasserver_interface_ip_addresses ifip
                ON sip.id = ifip.staticipaddress_id
            LEFT OUTER JOIN maasserver_interface iface
                ON iface.id = ifip.interface_id
            LEFT OUTER JOIN maasserver_node node
                ON iface.node_id = node.id
            LEFT OUTER JOIN maasserver_bmc bmc
                ON bmc.ip_address_id = sip.id
        ORDER BY sip.ip
    """
)

maas_support__boot_source_selections = dedent(
    """\
    SELECT
        bs.url,
        bss.release,
        bss.arches,
        bss.subarches,
        bss.labels,
        bss.os
    FROM
        maasserver_bootsource bs
    LEFT OUTER JOIN maasserver_bootsourceselection bss
        ON bss.boot_source_id = bs.id
     """
)

maas_support__boot_source_cache = dedent(
    """\
    SELECT
        bs.url,
        bsc.label,
        bsc.os,
        bsc.release,
        bsc.arch,
        bsc.subarch
    FROM
        maasserver_bootsource bs
    LEFT OUTER JOIN maasserver_bootsourcecache bsc
        ON bsc.boot_source_id = bs.id
    ORDER BY
        bs.url,
        bsc.label,
        bsc.os,
        bsc.release,
        bsc.arch,
        bsc.subarch
     """
)

maas_support__configuration__excluding_rpc_shared_secret = dedent(
    """\
    SELECT
        name,
        value
    FROM
        maasserver_config
    WHERE
        name != 'rpc_shared_secret'
    """
)

maas_support__license_keys_present__excluding_key_material = dedent(
    """\
    SELECT
        osystem,
        distro_series
    FROM
        maasserver_licensekey
    """
)

maas_support__ssh_keys__by_user = dedent(
    """\
    SELECT
        u.username,
        sshkey.key
    FROM
        auth_user u
    LEFT OUTER JOIN maasserver_sshkey sshkey
        ON u.id = sshkey.user_id
    ORDER BY
        u.username,
        sshkey.key
    """
)

# Dictionary of view_name: view_sql tuples which describe the database views.
_ALL_VIEWS = {
    "maasserver_discovery": maasserver_discovery,
    "maasserver_routable_pairs": maasserver_routable_pairs,
    "maasserver_podhost": maasserver_podhost,
    "maas_support__node_overview": maas_support__node_overview,
    "maas_support__device_overview": maas_support__device_overview,
    "maas_support__node_networking": maas_support__node_networking,
    "maas_support__ip_allocation": maas_support__ip_allocation,
    "maas_support__boot_source_selections": maas_support__boot_source_selections,
    "maas_support__boot_source_cache": maas_support__boot_source_cache,
    "maas_support__configuration__excluding_rpc_shared_secret": maas_support__configuration__excluding_rpc_shared_secret,
    "maas_support__license_keys_present__excluding_key_material": maas_support__license_keys_present__excluding_key_material,
    "maas_support__ssh_keys__by_user": maas_support__ssh_keys__by_user,
}


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
    for view_name in _ALL_VIEWS.keys():
        _drop_view_if_exists(view_name)


@transactional
def register_view(view_name):
    """Register a view by name. CAUTION: this is only for use in tests."""
    _register_view(view_name, _ALL_VIEWS[view_name])
