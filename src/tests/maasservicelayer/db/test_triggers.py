# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestTriggersUsed:
    """Tests relating to those triggers the MAAS application uses."""

    triggers_system = {
        "rbacsync_sys_rbac_sync",
        "regionrackrpcconnection_sys_core_rpc_delete",
        "regionrackrpcconnection_sys_core_rpc_insert",
        "resourcepool_sys_rbac_rpool_delete",
        "resourcepool_sys_rbac_rpool_insert",
        "resourcepool_sys_rbac_rpool_update",
        "subnet_sys_proxy_subnet_delete",
        "subnet_sys_proxy_subnet_insert",
        "subnet_sys_proxy_subnet_update",
    }

    triggers_websocket = {
        "blockdevice_nd_blockdevice_link_notify",
        "blockdevice_nd_blockdevice_unlink_notify",
        "blockdevice_nd_blockdevice_update_notify",
        "bmc_bmc_machine_update_notify",
        "bmc_pod_delete_notify",
        "bmc_pod_insert_notify",
        "bmc_pod_update_notify",
        "cacheset_nd_cacheset_link_notify",
        "cacheset_nd_cacheset_unlink_notify",
        "cacheset_nd_cacheset_update_notify",
        "config_sys_proxy_config_use_peer_proxy_insert",
        "config_sys_proxy_config_use_peer_proxy_update",
        "controllerinfo_controllerinfo_link_notify",
        "controllerinfo_controllerinfo_unlink_notify",
        "controllerinfo_controllerinfo_update_notify",
        "dhcpsnippet_dhcpsnippet_create_notify",
        "dhcpsnippet_dhcpsnippet_delete_notify",
        "dhcpsnippet_dhcpsnippet_update_notify",
        "dnsdata_dnsdata_domain_delete_notify",
        "dnsdata_dnsdata_domain_insert_notify",
        "dnsdata_dnsdata_domain_update_notify",
        "dnsresource_dnsresource_domain_delete_notify",
        "dnsresource_dnsresource_domain_insert_notify",
        "dnsresource_dnsresource_domain_update_notify",
        "dnsresource_ip_addresses_rrset_sipaddress_link_notify",
        "dnsresource_ip_addresses_rrset_sipaddress_unlink_notify",
        "domain_domain_create_notify",
        "domain_domain_delete_notify",
        "domain_domain_node_update_notify",
        "domain_domain_update_notify",
        "event_event_create_notify",
        "event_event_machine_update_notify",
        "fabric_fabric_create_notify",
        "fabric_fabric_delete_notify",
        "fabric_fabric_machine_update_notify",
        "fabric_fabric_update_notify",
        "filesystem_nd_filesystem_link_notify",
        "filesystem_nd_filesystem_unlink_notify",
        "filesystem_nd_filesystem_update_notify",
        "filesystemgroup_nd_filesystemgroup_link_notify",
        "filesystemgroup_nd_filesystemgroup_unlink_notify",
        "filesystemgroup_nd_filesystemgroup_update_notify",
        "interface_interface_pod_notify",
        "interface_ip_addresses_nd_sipaddress_dns_link_notify",
        "interface_ip_addresses_nd_sipaddress_dns_unlink_notify",
        "interface_ip_addresses_nd_sipaddress_link_notify",
        "interface_ip_addresses_nd_sipaddress_unlink_notify",
        "interface_nd_interface_link_notify",
        "interface_nd_interface_unlink_notify",
        "interface_nd_interface_update_notify",
        "iprange_iprange_create_notify",
        "iprange_iprange_delete_notify",
        "iprange_iprange_subnet_delete_notify",
        "iprange_iprange_subnet_insert_notify",
        "iprange_iprange_subnet_update_notify",
        "iprange_iprange_update_notify",
        "script_script_create_notify",
        "script_script_delete_notify",
        "script_script_update_notify",
        "scriptresult_nd_scriptresult_link_notify",
        "scriptresult_nd_scriptresult_unlink_notify",
        "scriptresult_nd_scriptresult_update_notify",
        "scriptresult_scriptresult_create_notify",
        "scriptresult_scriptresult_delete_notify",
        "scriptresult_scriptresult_update_notify",
        "scriptset_nd_scriptset_link_notify",
        "scriptset_nd_scriptset_unlink_notify",
        "neighbour_neighbour_create_notify",
        "neighbour_neighbour_delete_notify",
        "neighbour_neighbour_update_notify",
        "node_device_create_notify",
        "node_device_delete_notify",
        "node_device_update_notify",
        "node_machine_create_notify",
        "node_machine_delete_notify",
        "node_machine_update_notify",
        "node_node_pod_delete_notify",
        "node_node_pod_insert_notify",
        "node_node_pod_update_notify",
        "node_node_type_change_notify",
        "node_node_vmcluster_insert_notify",
        "node_node_vmcluster_update_notify",
        "node_node_vmcluster_delete_notify",
        "node_rack_controller_create_notify",
        "node_rack_controller_delete_notify",
        "node_rack_controller_update_notify",
        "node_region_and_rack_controller_create_notify",
        "node_region_and_rack_controller_delete_notify",
        "node_region_and_rack_controller_update_notify",
        "node_region_controller_create_notify",
        "node_region_controller_delete_notify",
        "node_region_controller_update_notify",
        "node_tags_machine_device_tag_link_notify",
        "node_tags_machine_device_tag_unlink_notify",
        "nodedevice_nodedevice_create_notify",
        "nodedevice_nodedevice_delete_notify",
        "nodedevice_nodedevice_update_notify",
        "nodemetadata_nodemetadata_link_notify",
        "nodemetadata_nodemetadata_unlink_notify",
        "nodemetadata_nodemetadata_update_notify",
        "notification_notification_create_notify",
        "notification_notification_delete_notify",
        "notification_notification_update_notify",
        "notificationdismissal_notificationdismissal_create_notify",
        "ownerdata_ownerdata_link_notify",
        "ownerdata_ownerdata_unlink_notify",
        "ownerdata_ownerdata_update_notify",
        "packagerepository_packagerepository_create_notify",
        "packagerepository_packagerepository_delete_notify",
        "packagerepository_packagerepository_update_notify",
        "partition_nd_partition_link_notify",
        "partition_nd_partition_unlink_notify",
        "partition_nd_partition_update_notify",
        "partitiontable_nd_partitiontable_link_notify",
        "partitiontable_nd_partitiontable_unlink_notify",
        "partitiontable_nd_partitiontable_update_notify",
        "physicalblockdevice_nd_physblockdevice_update_notify",
        "piston3_consumer_consumer_token_update_notify",
        "piston3_token_token_create_notify",
        "piston3_token_token_delete_notify",
        "service_service_create_notify",
        "service_service_delete_notify",
        "service_service_update_notify",
        "space_space_create_notify",
        "space_space_delete_notify",
        "space_space_machine_update_notify",
        "space_space_update_notify",
        "staticipaddress_ipaddress_domain_delete_notify",
        "staticipaddress_ipaddress_domain_insert_notify",
        "staticipaddress_ipaddress_domain_update_notify",
        "staticipaddress_ipaddress_machine_update_notify",
        "staticipaddress_ipaddress_subnet_delete_notify",
        "staticipaddress_ipaddress_subnet_insert_notify",
        "staticipaddress_ipaddress_subnet_update_notify",
        "staticroute_staticroute_create_notify",
        "staticroute_staticroute_delete_notify",
        "staticroute_staticroute_update_notify",
        "subnet_subnet_create_notify",
        "subnet_subnet_delete_notify",
        "subnet_subnet_machine_update_notify",
        "subnet_subnet_update_notify",
        "tag_tag_create_notify",
        "tag_tag_delete_notify",
        "tag_tag_update_machine_device_notify",
        "tag_tag_update_notify",
        "virtualblockdevice_nd_virtblockdevice_update_notify",
        "vlan_vlan_create_notify",
        "vlan_vlan_delete_notify",
        "vlan_vlan_machine_update_notify",
        "vlan_vlan_subnet_update_notify",
        "vlan_vlan_update_notify",
        "vmcluster_vmcluster_insert_notify",
        "vmcluster_vmcluster_update_notify",
        "vmcluster_vmcluster_delete_notify",
    }

    triggers_all = triggers_system | triggers_websocket

    async def find_triggers_in_database(self, db_connection: AsyncConnection):
        stmt = text(
            "SELECT tgname::text FROM pg_trigger WHERE NOT tgisinternal"
        )
        result = await db_connection.execute(stmt)
        return {tgname for (tgname,) in result.fetchall()}

    async def check_triggers_in_database(self, db_connection: AsyncConnection):
        # Note: if this test fails, a trigger may have been added, but not
        # added to the list of expected triggers.
        triggers_found = await self.find_triggers_in_database(db_connection)
        assert self.triggers_all - triggers_found == frozenset(), (
            "Some triggers were expected but not found."
        )
        assert triggers_found - self.triggers_all == frozenset(), (
            "Some triggers were unexpected."
        )

    async def test_all_triggers_present_and_correct(
        self, db_connection: AsyncConnection
    ):
        # Running in a fully migrated database means all triggers should be
        # present from the get go.
        await self.check_triggers_in_database(db_connection)


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestTriggers:
    async def test_register_system_triggers(
        self, db_connection: AsyncConnection
    ):
        triggers = [
            "regionrackrpcconnection_sys_core_rpc_insert",
            "regionrackrpcconnection_sys_core_rpc_delete",
            "subnet_sys_proxy_subnet_insert",
            "subnet_sys_proxy_subnet_update",
            "subnet_sys_proxy_subnet_delete",
            "resourcepool_sys_rbac_rpool_insert",
            "resourcepool_sys_rbac_rpool_update",
            "resourcepool_sys_rbac_rpool_delete",
        ]

        stmt = text("""
            SELECT tgname::text
            FROM pg_trigger
            WHERE tgname::text = ANY(:triggers)
        """).bindparams(triggers=triggers)

        result = await db_connection.execute(stmt)
        db_triggers = [row[0] for row in result.fetchall()]

        # Note: if this test fails, a trigger may have been added, but not
        # added to the list of expected triggers.
        triggers_found = [trigger[0] for trigger in db_triggers]
        missing_triggers = [
            trigger for trigger in triggers if trigger not in triggers_found
        ]
        assert len(triggers) == len(db_triggers), (
            f"Missing {len(triggers) - len(db_triggers)} triggers in the database. Triggers missing: {missing_triggers}"
        )
