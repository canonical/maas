# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.triggers`."""

from contextlib import closing

from django.db import connection

from maasserver.testing.testcase import MAASServerTestCase
from maasserver.triggers import register_procedure, register_trigger
from maasserver.triggers.system import register_system_triggers
from maasserver.triggers.websocket import (
    register_websocket_triggers,
    render_notification_procedure,
)

EMPTY_SET = frozenset()


class TestTriggers(MAASServerTestCase):
    def test_register_trigger_doesnt_create_trigger_if_already_exists(self):
        NODE_CREATE_PROCEDURE = render_notification_procedure(
            "node_create_notify", "node_create", "NEW.system_id"
        )
        register_procedure(NODE_CREATE_PROCEDURE)
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                "DROP TRIGGER IF EXISTS node_node_create_notify ON "
                "maasserver_node;"
                "CREATE TRIGGER node_node_create_notify "
                "AFTER INSERT ON maasserver_node "
                "FOR EACH ROW EXECUTE PROCEDURE node_create_notify();"
            )

        # Will raise an OperationError if trigger already exists.
        register_trigger("maasserver_node", "node_create_notify", "insert")

    def test_register_trigger_creates_missing_trigger(self):
        NODE_CREATE_PROCEDURE = render_notification_procedure(
            "node_create_notify", "node_create", "NEW.system_id"
        )
        register_procedure(NODE_CREATE_PROCEDURE)
        register_trigger("maasserver_node", "node_create_notify", "insert")

        with closing(connection.cursor()) as cursor:
            cursor.execute(
                "SELECT * FROM pg_trigger WHERE "
                "tgname = 'node_node_create_notify'"
            )
            triggers = cursor.fetchall()

        self.assertEqual(1, len(triggers), "Trigger was not created.")


class TestTriggersUsed(MAASServerTestCase):
    """Tests relating to those triggers the MAAS application uses."""

    triggers_system = {
        "config_sys_dns_config_insert",
        "config_sys_dns_config_update",
        "dnspublication_sys_dns_publish",
        "interface_ip_addresses_sys_dns_nic_ip_link",
        "interface_ip_addresses_sys_dns_nic_ip_unlink",
        "interface_ip_addresses_sys_dns_updates_interface_ip_insert",
        "interface_ip_addresses_sys_dns_updates_interface_ip_delete",
        "interface_sys_dns_interface_update",
        "interface_sys_dns_updates_maasserver_interface_delete",
        "node_sys_dns_node_delete",
        "node_sys_dns_node_update",
        "node_sys_dns_updates_maasserver_node_insert",
        "node_sys_dns_updates_maasserver_node_update",
        "node_sys_dns_updates_maasserver_node_delete",
        "rbacsync_sys_rbac_sync",
        "regionrackrpcconnection_sys_core_rpc_delete",
        "regionrackrpcconnection_sys_core_rpc_insert",
        "resourcepool_sys_rbac_rpool_delete",
        "resourcepool_sys_rbac_rpool_insert",
        "resourcepool_sys_rbac_rpool_update",
        "staticipaddress_sys_dns_staticipaddress_update",
        "staticipaddress_sys_dns_updates_ip_update",
        "subnet_sys_dns_updates_maasserver_subnet_delete",
        "subnet_sys_dns_updates_maasserver_subnet_insert",
        "subnet_sys_dns_updates_maasserver_subnet_update",
        "subnet_sys_dns_subnet_delete",
        "subnet_sys_dns_subnet_insert",
        "subnet_sys_dns_subnet_update",
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
        "piston3_token_user_token_link_notify",
        "piston3_token_user_token_unlink_notify",
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

    def find_triggers_in_database(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tgname::text FROM pg_trigger WHERE NOT tgisinternal"
            )
            return {tgname for (tgname,) in cursor.fetchall()}

    def check_triggers_in_database(self):
        # Note: if this test fails, a trigger may have been added, but not
        # added to the list of expected triggers.
        triggers_found = self.find_triggers_in_database()
        self.assertEqual(
            (self.triggers_all - triggers_found),
            EMPTY_SET,
            "Some triggers were expected but not found.",
        )
        self.assertEqual(
            (triggers_found - self.triggers_all),
            EMPTY_SET,
            "Some triggers were unexpected.",
        )

    def test_all_triggers_present_and_correct(self):
        # Running in a fully migrated database means all triggers should be
        # present from the get go.
        self.check_triggers_in_database()

    def test_register_system_triggers_does_not_introduce_more(self):
        register_system_triggers()
        self.check_triggers_in_database()

    def test_register_websocket_triggers_does_not_introduce_more(self):
        register_websocket_triggers()
        self.check_triggers_in_database()
