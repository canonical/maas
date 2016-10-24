# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.triggers.websocket`."""

__all__ = []

from contextlib import closing

from django.db import connection
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.triggers.websocket import register_websocket_triggers
from maasserver.utils.orm import psql_array


class TestTriggers(MAASServerTestCase):

    def test_register_websocket_triggers(self):
        register_websocket_triggers()
        triggers = [
            "node_machine_create_notify",
            "node_machine_update_notify",
            "node_machine_delete_notify",
            "node_device_create_notify",
            "node_device_update_notify",
            "node_device_delete_notify",
            "config_config_create_notify",
            "config_config_update_notify",
            "config_config_delete_notify",
            "node_rack_controller_create_notify",
            "node_rack_controller_update_notify",
            "node_rack_controller_delete_notify",
            "node_region_controller_create_notify",
            "node_region_controller_update_notify",
            "node_region_controller_delete_notify",
            "node_region_and_rack_controller_create_notify",
            "node_region_and_rack_controller_update_notify",
            "node_region_and_rack_controller_delete_notify",
            "zone_zone_create_notify",
            "zone_zone_update_notify",
            "zone_zone_delete_notify",
            "tag_tag_create_notify",
            "tag_tag_update_notify",
            "tag_tag_delete_notify",
            "node_tags_machine_device_tag_link_notify",
            "node_tags_machine_device_tag_unlink_notify",
            "tag_tag_update_machine_device_notify",
            "auth_user_user_create_notify",
            "auth_user_user_update_notify",
            "auth_user_user_delete_notify",
            "event_event_create_notify",
            "event_event_create_machine_device_notify",
            "interface_ip_addresses_nd_sipaddress_link_notify",
            "interface_ip_addresses_nd_sipaddress_unlink_notify",
            "interface_ip_addresses_nd_sipaddress_dns_link_notify",
            "interface_ip_addresses_nd_sipaddress_dns_unlink_notify",
            "dnsresource_ip_addresses_rrset_sipaddress_link_notify",
            "dnsresource_ip_addresses_rrset_sipaddress_unlink_notify",
            "metadataserver_noderesult_nd_noderesult_link_notify",
            "metadataserver_noderesult_nd_noderesult_unlink_notify",
            "interface_nd_interface_link_notify",
            "interface_nd_interface_unlink_notify",
            "interface_nd_interface_update_notify",
            "blockdevice_nd_blockdevice_link_notify",
            "blockdevice_nd_blockdevice_unlink_notify",
            "physicalblockdevice_nd_physblockdevice_update_notify",
            "virtualblockdevice_nd_virtblockdevice_update_notify",
            "sshkey_user_sshkey_link_notify",
            "sshkey_user_sshkey_unlink_notify",
            "sshkey_sshkey_create_notify",
            "sshkey_sshkey_update_notify",
            "sshkey_sshkey_delete_notify",
            "sslkey_user_sslkey_link_notify",
            "sslkey_user_sslkey_unlink_notify",
            "fabric_fabric_create_notify",
            "fabric_fabric_update_notify",
            "fabric_fabric_delete_notify",
            "vlan_vlan_create_notify",
            "vlan_vlan_update_notify",
            "vlan_vlan_delete_notify",
            "neighbour_neighbour_create_notify",
            "neighbour_neighbour_update_notify",
            "neighbour_neighbour_delete_notify",
            "iprange_iprange_create_notify",
            "iprange_iprange_update_notify",
            "iprange_iprange_delete_notify",
            "staticroute_staticroute_create_notify",
            "staticroute_staticroute_update_notify",
            "staticroute_staticroute_delete_notify",
            "subnet_subnet_create_notify",
            "subnet_subnet_update_notify",
            "subnet_subnet_delete_notify",
            "space_space_create_notify",
            "space_space_update_notify",
            "space_space_delete_notify",
            "subnet_subnet_machine_update_notify",
            "fabric_fabric_machine_update_notify",
            "space_space_machine_update_notify",
            "vlan_vlan_machine_update_notify",
            "staticipaddress_ipaddress_machine_update_notify",
            "staticipaddress_ipaddress_subnet_update_notify",
            "dhcpsnippet_dhcpsnippet_create_notify",
            "dhcpsnippet_dhcpsnippet_update_notify",
            "dhcpsnippet_dhcpsnippet_delete_notify",
            "iprange_iprange_subnet_insert_notify",
            "iprange_iprange_subnet_update_notify",
            "iprange_iprange_subnet_delete_notify",
            ]
        sql, args = psql_array(triggers, sql_type="text")
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                "SELECT tgname::text FROM pg_trigger WHERE "
                "tgname::text = ANY(%s) " % sql, args)
            db_triggers = cursor.fetchall()

        # Note: if this test fails, a trigger may have been added, but not
        # added to the list of expected triggers.
        triggers_found = [trigger[0] for trigger in db_triggers]
        self.assertEqual(
            len(triggers), len(db_triggers),
            "Missing %s triggers in the database. Triggers found: %s" % (
                len(triggers) - len(db_triggers), triggers_found))

        self.assertItemsEqual(
            triggers, triggers_found,
            "Missing triggers in the database. Triggers found: %s" % (
                triggers_found))
