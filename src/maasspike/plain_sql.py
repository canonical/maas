import logging

from psycopg2.extras import NamedTupleCursor

from maasserver.enum import INTERFACE_TYPE, IPADDRESS_TYPE, NODE_TYPE
from metadataserver.enum import HARDWARE_TYPE, RESULT_TYPE, SCRIPT_STATUS

from .sqlalchemy_core import get_machines


def list_machines_one_query(conn, admin, limit=None):
    query, params = get_query(limit=limit)
    rows = get_rows(conn, query, params)
    return get_machines(rows, admin)


def list_machines_materialized_view(conn, view_name, admin, limit=None):
    rows = get_rows_from_view(conn, view_name, limit=limit)
    return get_machines(rows, admin)


def get_query(limit=None):
    query = """
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
          AND maasserver_interface.type = %(interface_physical)s
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
      interface_addresses AS (
        SELECT
          maasserver_interface.id AS id,
          maasserver_staticipaddress.ip,
          spike_interface_ip.configured
        FROM maasserver_interface
          JOIN spike_interface_ip ON maasserver_interface.id = spike_interface_ip.interface_id
          JOIN maasserver_staticipaddress ON spike_interface_ip.ip_id = maasserver_staticipaddress.id
      ),
      ip_addresses AS (
        SELECT
          maasserver_node.id AS id,
          array_agg(interface_addresses.ip) AS ips,
          array_agg(interface_addresses.id = maasserver_node.boot_interface_id) AS is_boot_ips,
          array_agg(interface_addresses.configured) AS ips_configured
        FROM maasserver_node
          JOIN interfaces ON interfaces.machine_id = maasserver_node.id
          JOIN interface_addresses ON interface_addresses.id = interfaces.interface_id
        GROUP BY maasserver_node.id),
      testing_status AS (
        SELECT
          maasserver_node.id AS id,
          sum(
            CASE
              WHEN (metadataserver_scriptresult.status = %(script_status_pending)s) THEN 1
              ELSE 0
            END
          ) AS testing_status_pending,
          sum(
            CASE
              WHEN (metadataserver_scriptresult.status = %(script_status_running)s) THEN 1
              ELSE 0
            END
          ) AS testing_status_running,
          sum(
            CASE
              WHEN (metadataserver_scriptresult.status = %(script_status_passed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_skipped)s) THEN 1
              ELSE 0
            END
          ) AS testing_status_passed,
          sum(
            CASE
              WHEN (metadataserver_scriptresult.status = %(script_status_failed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_timedout)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_aborted)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_installing)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_applying_netconf)s) THEN 1
              ELSE 0
            END
          ) AS testing_status_failed,
          sum(
            CASE
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_running)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_applying_netconf)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_installing)s) THEN 1
              ELSE 0
            END
          ) AS testing_status_combined_running,
          sum(
            CASE
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_failed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_timedout)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_installing)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_applying_netconf)s) THEN 1
              ELSE 0
            END
          ) AS testing_status_combined_failed,
          sum(
            CASE
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_pending)s) THEN 1
              ELSE 0
            END
          ) AS testing_status_combined_pending,
          sum(
            CASE
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_aborted)s) THEN 1
              ELSE 0
            END
          ) AS testing_status_combined_aborted,
          sum(
            CASE
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_degraded)s) THEN 1
              ELSE 0
            END
          ) AS testing_status_combined_degraded,
          sum(
            CASE
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_passed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_skipped)s) THEN 1
              ELSE 0
            END
          ) AS testing_status_combined_passed,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_storage)s) THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_pending)s) THEN 1
              ELSE 0
            END
          ) AS storage_test_status_pending,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_storage)s) THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_running)s) THEN 1
              ELSE 0
            END
          ) AS storage_test_status_running,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_storage)s) THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_passed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_skipped)s) THEN 1
              ELSE 0
            END
          ) AS storage_test_status_passed,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_storage)s) THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_failed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_timedout)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_aborted)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_installing)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_applying_netconf)s) THEN 1
              ELSE 0
            END
          ) AS storage_test_status_failed,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_storage)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_running)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_applying_netconf)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_installing)s) THEN 1
              ELSE 0
            END
          ) AS storage_test_status_combined_running,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_storage)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_failed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_timedout)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_installing)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_applying_netconf)s) THEN 1
              ELSE 0
            END
          ) AS storage_test_status_combined_failed,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_storage)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_pending)s) THEN 1
              ELSE 0
            END
          ) AS storage_test_status_combined_pending,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_storage)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_aborted)s) THEN 1
              ELSE 0
            END
          ) AS storage_test_status_combined_aborted,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_storage)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_degraded)s) THEN 1
              ELSE 0
            END
          ) AS storage_test_status_combined_degraded,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_storage)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_passed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_skipped)s) THEN 1
              ELSE 0
            END
          ) AS storage_test_status_combined_passed,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_network)s) THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_pending)s) THEN 1
              ELSE 0
            END
          ) AS network_test_status_pending,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_network)s) THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_running)s) THEN 1
              ELSE 0
            END
          ) AS network_test_status_running,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_network)s) THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_passed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_skipped)s) THEN 1
              ELSE 0
            END
          ) AS network_test_status_passed,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_network)s) THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_failed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_timedout)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_aborted)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_installing)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_applying_netconf)s) THEN 1
              ELSE 0
            END
          ) AS network_test_status_failed,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_network)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_running)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_applying_netconf)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_installing)s) THEN 1
              ELSE 0
            END
          ) AS network_test_status_combined_running,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_network)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_failed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_timedout)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_installing)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_applying_netconf)s) THEN 1
              ELSE 0
            END
          ) AS network_test_status_combined_failed,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_network)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_pending)s) THEN 1
              ELSE 0
            END
          ) AS network_test_status_combined_pending,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_network)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_aborted)s) THEN 1
              ELSE 0
            END
          ) AS network_test_status_combined_aborted,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_network)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_degraded)s) THEN 1
              ELSE 0
            END
          ) AS network_test_status_combined_degraded,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_network)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_passed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_skipped)s) THEN 1
              ELSE 0
            END
          ) AS network_test_status_combined_passed,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_memory)s) THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_pending)s) THEN 1
              ELSE 0
            END
          ) AS memory_test_status_pending,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_memory)s) THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_running)s) THEN 1
              ELSE 0
            END
          ) AS memory_test_status_running,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_memory)s) THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_passed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_skipped)s) THEN 1
              ELSE 0
            END
          ) AS memory_test_status_passed,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_memory)s) THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_failed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_timedout)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_aborted)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_installing)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_applying_netconf)s) THEN 1
              ELSE 0
            END
          ) AS memory_test_status_failed,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_memory)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_running)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_applying_netconf)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_installing)s) THEN 1
              ELSE 0
            END
          ) AS memory_test_status_combined_running,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_memory)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_failed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_timedout)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_installing)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_applying_netconf)s) THEN 1
              ELSE 0
            END
          ) AS memory_test_status_combined_failed,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_memory)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_pending)s) THEN 1
              ELSE 0
            END
          ) AS memory_test_status_combined_pending,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_memory)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_aborted)s) THEN 1
              ELSE 0
            END
          ) AS memory_test_status_combined_aborted,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_memory)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_degraded)s) THEN 1
              ELSE 0
            END
          ) AS memory_test_status_combined_degraded,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_memory)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_passed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_skipped)s) THEN 1
              ELSE 0
            END
          ) AS memory_test_status_combined_passed,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_cpu)s) THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_pending)s) THEN 1
              ELSE 0
            END
          ) AS cpu_test_status_pending,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_cpu)s) THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_running)s) THEN 1
              ELSE 0
            END
          ) AS cpu_test_status_running,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_cpu)s) THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_passed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_skipped)s) THEN 1
              ELSE 0
            END
          ) AS cpu_test_status_passed,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_cpu)s) THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_failed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_timedout)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_aborted)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_installing)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_applying_netconf)s) THEN 1
              ELSE 0
            END
          ) AS cpu_test_status_failed,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_cpu)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_running)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_applying_netconf)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_installing)s) THEN 1
              ELSE 0
            END
          ) AS cpu_test_status_combined_running,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_cpu)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_failed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_timedout)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_installing)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_failed_applying_netconf)s) THEN 1
              ELSE 0
            END
          ) AS cpu_test_status_combined_failed,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_cpu)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_pending)s) THEN 1
              ELSE 0
            END
          ) AS cpu_test_status_combined_pending,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_cpu)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_aborted)s) THEN 1
              ELSE 0
            END
          ) AS cpu_test_status_combined_aborted,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_cpu)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_degraded)s) THEN 1
              ELSE 0
            END
          ) AS cpu_test_status_combined_degraded,
          sum(
            CASE
              WHEN (metadataserver_script.hardware_type != %(hardware_type_cpu)s) THEN 0
              WHEN metadataserver_scriptresult.suppressed THEN 0
              WHEN (metadataserver_scriptresult.status = %(script_status_passed)s) THEN 1
              WHEN (metadataserver_scriptresult.status = %(script_status_skipped)s) THEN 1
              ELSE 0
            END
          ) AS cpu_test_status_combined_passed
        FROM maasserver_node
          JOIN metadataserver_scriptset ON metadataserver_scriptset.node_id = maasserver_node.id
          JOIN metadataserver_scriptresult ON metadataserver_scriptresult.script_set_id = metadataserver_scriptset.id
          JOIN metadataserver_script ON metadataserver_script.id = metadataserver_scriptresult.script_id
        WHERE metadataserver_scriptset.result_type = %(result_type_testing)s
        GROUP BY maasserver_node.id
      ),
      machine_tags AS (
        SELECT
          maasserver_node.id AS id,
          array_agg(maasserver_node_tags.tag_id) AS tag_ids
        FROM maasserver_node
          JOIN maasserver_node_tags ON maasserver_node_tags.node_id = maasserver_node.id
        GROUP BY maasserver_node.id
      )

    SELECT
      maasserver_node.architecture,
      maasserver_node.cpu_count,
      maasserver_node.description,
      maasserver_node.distro_series,
      maasserver_node.error_description,
      maasserver_node.hostname,
      maasserver_node.id,
      maasserver_node.locked,
      maasserver_node.osystem,
      maasserver_node.power_state,
      maasserver_node.system_id,
      maasserver_node.domain_id,
      maasserver_node.node_type,
      maasserver_node.pool_id,
      maasserver_node.status AS status_code,
      maasserver_node.zone_id,
      maasserver_domain.name AS domain_name,
      coalesce(auth_user.username, '') AS owner_name,
      parent.system_id AS parent,
      maasserver_resourcepool.name AS pool_name,
      maasserver_zone.name AS zone_name,
      storage.disk_count,
      round(storage.storage / CAST(1000000000 AS NUMERIC), 1) AS storage,
      round(maasserver_node.memory / CAST(1024 AS NUMERIC), 1) AS memory,
      fabrics.names AS fabrics,
      coalesce(spaces.names, %(empty_spaces)s) AS spaces,
      extra_macs.extra_macs,
      boot_interface.mac_address AS pxe_mac,
      maasserver_bmc.power_type,
      (
        SELECT concat(maasserver_eventtype.description, ' - ', maasserver_event.description) AS status_message
        FROM maasserver_event
          JOIN maasserver_eventtype ON maasserver_eventtype.id = maasserver_event.type_id
        WHERE maasserver_node.id = maasserver_event.node_id
          AND maasserver_eventtype.level >= %(eventtype_level_info)s
        ORDER BY maasserver_event.node_id, maasserver_event.created DESC, maasserver_event.id DESC
        LIMIT 1
      ) AS status_message,
      boot_vlan.id AS boot_vlan_id,
      boot_vlan.name AS boot_vlan_name,
      boot_vlan.fabric_id AS boot_fabric_id,
      boot_fabric.name AS boot_fabric_name,
      ip_addresses.ips,
      ip_addresses.is_boot_ips,
      ip_addresses.ips_configured,
      testing_status.testing_status_pending,
      testing_status.testing_status_running,
      testing_status.testing_status_passed,
      testing_status.testing_status_failed,
      CASE
        WHEN (testing_status.testing_status_combined_running > 0) THEN %(script_status_running)s
        WHEN (testing_status.testing_status_combined_failed > 0) THEN %(script_status_failed)s
        WHEN (testing_status.testing_status_combined_pending > 0) THEN %(script_status_pending)s
        WHEN (testing_status.testing_status_combined_degraded > 0) THEN %(script_status_degraded)s
        WHEN (testing_status.testing_status_combined_passed > 0) THEN %(script_status_passed)s
        ELSE -1
      END AS testing_status_combined,
      testing_status.storage_test_status_pending,
      testing_status.storage_test_status_running,
      testing_status.storage_test_status_passed,
      testing_status.storage_test_status_failed,
      CASE
        WHEN (testing_status.storage_test_status_combined_running > 0)
          THEN %(script_status_running)s
        WHEN (testing_status.storage_test_status_combined_failed > 0)
          THEN %(script_status_failed)s
        WHEN (testing_status.storage_test_status_combined_pending > 0)
          THEN %(script_status_pending)s
        WHEN (testing_status.storage_test_status_combined_degraded > 0)
          THEN %(script_status_degraded)s
        WHEN (testing_status.storage_test_status_combined_passed > 0)
          THEN %(script_status_passed)s
        ELSE -1
      END AS storage_test_status_combined,
      testing_status.network_test_status_pending,
      testing_status.network_test_status_running,
      testing_status.network_test_status_passed,
      testing_status.network_test_status_failed,
      CASE
        WHEN (testing_status.network_test_status_combined_running > 0) THEN %(script_status_running)s
        WHEN (testing_status.network_test_status_combined_failed > 0) THEN %(script_status_failed)s
        WHEN (testing_status.network_test_status_combined_pending > 0) THEN %(script_status_pending)s
        WHEN (testing_status.network_test_status_combined_degraded > 0) THEN %(script_status_degraded)s
        WHEN (testing_status.network_test_status_combined_passed > 0) THEN %(script_status_passed)s
        ELSE -1
      END AS network_test_status_combined,
      testing_status.cpu_test_status_pending,
      testing_status.cpu_test_status_running,
      testing_status.cpu_test_status_passed,
      testing_status.cpu_test_status_failed,
      CASE
        WHEN (testing_status.cpu_test_status_combined_running > 0) THEN %(script_status_running)s
        WHEN (testing_status.cpu_test_status_combined_failed > 0) THEN %(script_status_failed)s
        WHEN (testing_status.cpu_test_status_combined_pending > 0) THEN %(script_status_pending)s
        WHEN (testing_status.cpu_test_status_combined_degraded > 0) THEN %(script_status_degraded)s
        WHEN (testing_status.cpu_test_status_combined_passed > 0) THEN %(script_status_passed)s
        ELSE -1
      END AS cpu_test_status_combined,
      testing_status.memory_test_status_pending,
      testing_status.memory_test_status_running,
      testing_status.memory_test_status_passed,
      testing_status.memory_test_status_failed,
      CASE
        WHEN (testing_status.memory_test_status_combined_running > 0) THEN %(script_status_running)s
        WHEN (testing_status.memory_test_status_combined_failed > 0) THEN %(script_status_failed)s
        WHEN (testing_status.memory_test_status_combined_pending > 0) THEN %(script_status_pending)s
        WHEN (testing_status.memory_test_status_combined_degraded > 0) THEN %(script_status_degraded)s
        WHEN (testing_status.memory_test_status_combined_passed > 0) THEN %(script_status_passed)s
        ELSE -1
      END AS memory_test_status_combined,
      machine_tags.tag_ids
    FROM maasserver_node
      JOIN maasserver_domain ON maasserver_domain.id = maasserver_node.domain_id
      LEFT OUTER JOIN auth_user ON auth_user.id = maasserver_node.owner_id
      LEFT OUTER JOIN maasserver_resourcepool ON maasserver_resourcepool.id = maasserver_node.pool_id
      LEFT OUTER JOIN maasserver_zone ON maasserver_zone.id = maasserver_node.zone_id
      LEFT OUTER JOIN storage ON storage.id = maasserver_node.id
      LEFT OUTER JOIN fabrics ON fabrics.machine_id = maasserver_node.id
      LEFT OUTER JOIN spaces ON spaces.machine_id = maasserver_node.id
      LEFT OUTER JOIN maasserver_node AS parent ON parent.id = maasserver_node.parent_id
      JOIN extra_macs ON extra_macs.id = maasserver_node.id
      LEFT OUTER JOIN maasserver_interface AS boot_interface ON boot_interface.id = maasserver_node.boot_interface_id
      LEFT OUTER JOIN maasserver_bmc ON maasserver_bmc.id = maasserver_node.bmc_id
      JOIN maasserver_vlan AS boot_vlan ON boot_vlan.id = boot_interface.vlan_id
      JOIN maasserver_fabric AS boot_fabric ON boot_fabric.id = boot_vlan.fabric_id
      LEFT OUTER JOIN ip_addresses ON ip_addresses.id = maasserver_node.id
      LEFT OUTER JOIN testing_status ON testing_status.id = maasserver_node.id
      JOIN machine_tags ON machine_tags.id = maasserver_node.id
    WHERE maasserver_node.node_type = %(node_type_machine)s ORDER BY maasserver_node.id
    """
    if limit is not None:
        query = f"{query} LIMIT %(limit)s"

    params = {
        "alloc_type_dhcp": IPADDRESS_TYPE.DHCP,
        "alloc_type_discovered": IPADDRESS_TYPE.DISCOVERED,
        "empty_spaces": [],
        "eventtype_level_info": logging.INFO,
        "hardware_type_cpu": HARDWARE_TYPE.CPU,
        "hardware_type_memory": HARDWARE_TYPE.MEMORY,
        "hardware_type_network": HARDWARE_TYPE.NETWORK,
        "hardware_type_storage": HARDWARE_TYPE.STORAGE,
        "interface_physical": INTERFACE_TYPE.PHYSICAL,
        "limit": limit,
        "node_type_machine": NODE_TYPE.MACHINE,
        "result_type_testing": RESULT_TYPE.TESTING,
        "script_status_aborted": SCRIPT_STATUS.ABORTED,
        "script_status_applying_netconf": SCRIPT_STATUS.APPLYING_NETCONF,
        "script_status_degraded": SCRIPT_STATUS.DEGRADED,
        "script_status_failed": SCRIPT_STATUS.FAILED,
        "script_status_failed_applying_netconf": SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
        "script_status_failed_installing": SCRIPT_STATUS.FAILED_INSTALLING,
        "script_status_installing": SCRIPT_STATUS.INSTALLING,
        "script_status_passed": SCRIPT_STATUS.PASSED,
        "script_status_pending": SCRIPT_STATUS.PENDING,
        "script_status_running": SCRIPT_STATUS.RUNNING,
        "script_status_skipped": SCRIPT_STATUS.SKIPPED,
        "script_status_timedout": SCRIPT_STATUS.TIMEDOUT,
    }
    return query, params


def get_rows(conn, query, params):
    # use the underlying psycopg2 connection
    with conn.cursor(cursor_factory=NamedTupleCursor) as cur:
        cur.execute(query, params)
        return cur.fetchall()


def get_rows_from_view(conn, view_name, limit=None):
    query = f"SELECT * from {view_name} ORDER BY id"
    if limit is not None:
        query = f"{query} LIMIT {limit}"
    # use the underlying psycopg2 connection
    with conn.cursor(cursor_factory=NamedTupleCursor) as cur:
        cur.execute(query)
        return cur.fetchall()
