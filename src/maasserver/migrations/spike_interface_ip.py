alloc_type_dhcp = 5
alloc_type_discovered = 6
interface_physical = "physical"


MIGRATE_IPS_SQL = f"""
    WITH
      storage AS (
        SELECT
          maasserver_node.id AS id,
          count(maasserver_physicalblockdevice.blockdevice_ptr_id) AS disk_count,
          sum(coalesce(maasserver_blockdevice.size, 0)) AS storage
        FROM maasserver_physicalblockdevice
          JOIN maasserver_blockdevice ON maasserver_blockdevice.id = maasserver_physicalblockdevice.blockdevice_ptr_id
          JOIN maasserver_nodeconfig ON maasserver_nodeconfig.id = maasserver_blockdevice.node_config_id
          JOIN maasserver_node ON maasserver_node.id = maasserver_nodeconfig.node_id
        GROUP BY maasserver_node.id
      ),
      vlans AS (
        SELECT
          maasserver_vlan.id AS id, maasserver_node.id AS machine_id
        FROM maasserver_vlan
          JOIN maasserver_interface ON maasserver_interface.vlan_id = maasserver_vlan.id
          JOIN maasserver_nodeconfig ON maasserver_nodeconfig.id = maasserver_interface.node_config_id
          JOIN maasserver_node ON maasserver_node.current_config_id = maasserver_nodeconfig.id
      ),
      fabrics AS (
        SELECT
          vlans.machine_id AS machine_id,
          array_agg(distinct(maasserver_fabric.name)) AS names
        FROM maasserver_fabric
          JOIN maasserver_vlan ON maasserver_vlan.fabric_id = maasserver_fabric.id
          JOIN vlans ON vlans.id = maasserver_vlan.id
        GROUP BY vlans.machine_id
      ),
      spaces AS (
        SELECT
          vlans.machine_id AS machine_id,
          array_agg(distinct(maasserver_space.name)) AS names
        FROM maasserver_space
          JOIN maasserver_vlan ON maasserver_vlan.space_id = maasserver_space.id
          JOIN vlans ON vlans.id = maasserver_vlan.id
        GROUP BY vlans.machine_id
      ),
      extra_macs AS (
        SELECT
          maasserver_node.id AS id,
          array_agg(maasserver_interface.mac_address) AS extra_macs
        FROM maasserver_node
          JOIN maasserver_nodeconfig ON maasserver_nodeconfig.id = maasserver_node.current_config_id
          JOIN maasserver_interface ON maasserver_interface.node_config_id = maasserver_nodeconfig.id
        WHERE maasserver_interface.id != maasserver_node.boot_interface_id
          AND maasserver_interface.type = '{interface_physical}'
        GROUP BY maasserver_node.id
      ),
      interfaces AS (
        SELECT
          maasserver_node.id AS machine_id,
          maasserver_interface.id AS interface_id
        FROM maasserver_interface
          JOIN maasserver_nodeconfig ON maasserver_nodeconfig.id = maasserver_interface.node_config_id
          JOIN maasserver_node ON maasserver_node.current_config_id = maasserver_nodeconfig.id
      ),
      dhcp_address AS (
        SELECT DISTINCT ON (maasserver_staticipaddress.id)
          maasserver_staticipaddress.id AS id,
          discovered_ip.ip AS ip
        FROM maasserver_staticipaddress
          JOIN maasserver_interface_ip_addresses ON maasserver_interface_ip_addresses.staticipaddress_id = maasserver_staticipaddress.id
          JOIN maasserver_interface_ip_addresses AS discovered_interface_ip ON discovered_interface_ip.interface_id = maasserver_interface_ip_addresses.interface_id
          JOIN maasserver_staticipaddress AS discovered_ip ON discovered_ip.id = maasserver_interface_ip_addresses.staticipaddress_id
        WHERE maasserver_staticipaddress.alloc_type = {alloc_type_dhcp}
          AND discovered_ip.alloc_type = {alloc_type_discovered}
          AND discovered_ip.ip IS NOT NULL
        ORDER BY maasserver_staticipaddress.id, discovered_ip.id DESC
      ),
      interface_addresses AS (
        SELECT
          maasserver_interface.id AS interface_id,
          CASE
            WHEN (maasserver_staticipaddress.alloc_type = {alloc_type_dhcp}) THEN dhcp_address.id
            ELSE maasserver_staticipaddress.id
          END AS ip_id,
          maasserver_staticipaddress.alloc_type
        FROM maasserver_interface
          JOIN maasserver_interface_ip_addresses ON maasserver_interface.id = maasserver_interface_ip_addresses.interface_id
          JOIN maasserver_staticipaddress ON maasserver_interface_ip_addresses.staticipaddress_id = maasserver_staticipaddress.id
          LEFT OUTER JOIN dhcp_address ON dhcp_address.id = maasserver_staticipaddress.id
      )
      INSERT INTO spike_interface_ip (interface_id, ip_id, configured)
      SELECT
        interface_addresses.interface_id,
        interface_addresses.ip_id,
        (interface_addresses.alloc_type = {alloc_type_discovered})
        FROM maasserver_interface
        JOIN interface_addresses
          ON maasserver_interface.id = interface_addresses.interface_id
        WHERE interface_addresses.ip_id IS NOT NULL
"""
