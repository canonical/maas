# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.triggers.system`."""


from contextlib import closing

from django.db import connection

from maasserver.models.dnspublication import zone_serial
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.triggers.system import register_system_triggers
from maasserver.utils.orm import psql_array
from maastesting.matchers import MockCalledOnceWith


class TestTriggers(MAASServerTestCase):
    def test_register_system_triggers(self):
        register_system_triggers()
        triggers = [
            "regionrackrpcconnection_sys_core_rpc_insert",
            "regionrackrpcconnection_sys_core_rpc_delete",
            "vlan_sys_dhcp_vlan_update",
            "subnet_sys_dhcp_subnet_update",
            "subnet_sys_dhcp_subnet_delete",
            "iprange_sys_dhcp_iprange_insert",
            "iprange_sys_dhcp_iprange_update",
            "iprange_sys_dhcp_iprange_delete",
            "staticipaddress_sys_dhcp_staticipaddress_insert",
            "staticipaddress_sys_dhcp_staticipaddress_update",
            "staticipaddress_sys_dhcp_staticipaddress_delete",
            "interface_sys_dhcp_interface_update",
            "node_sys_dhcp_node_update",
            "dhcpsnippet_sys_dhcp_snippet_insert",
            "dhcpsnippet_sys_dhcp_snippet_update",
            "dhcpsnippet_sys_dhcp_snippet_delete",
            "domain_sys_dns_domain_insert",
            "domain_sys_dns_domain_update",
            "domain_sys_dns_domain_delete",
            "staticipaddress_sys_dns_staticipaddress_update",
            "interface_ip_addresses_sys_dns_nic_ip_link",
            "interface_ip_addresses_sys_dns_nic_ip_unlink",
            "dnsresource_sys_dns_dnsresource_insert",
            "dnsresource_sys_dns_dnsresource_update",
            "dnsresource_sys_dns_dnsresource_delete",
            "dnsresource_ip_addresses_sys_dns_dnsresource_ip_link",
            "dnsresource_ip_addresses_sys_dns_dnsresource_ip_unlink",
            "dnsdata_sys_dns_dnsdata_insert",
            "dnsdata_sys_dns_dnsdata_update",
            "dnsdata_sys_dns_dnsdata_delete",
            "subnet_sys_dns_subnet_insert",
            "subnet_sys_dns_subnet_update",
            "subnet_sys_dns_subnet_delete",
            "node_sys_dns_node_update",
            "node_sys_dns_node_delete",
            "interface_sys_dns_interface_update",
            "config_sys_dns_config_insert",
            "config_sys_dns_config_update",
            "subnet_sys_proxy_subnet_insert",
            "subnet_sys_proxy_subnet_update",
            "subnet_sys_proxy_subnet_delete",
            "resourcepool_sys_rbac_rpool_insert",
            "resourcepool_sys_rbac_rpool_update",
            "resourcepool_sys_rbac_rpool_delete",
            "config_sys_rbac_config_insert",
            "config_sys_rbac_config_update",
        ]
        sql, args = psql_array(triggers, sql_type="text")
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                "SELECT tgname::text FROM pg_trigger WHERE "
                "tgname::text = ANY(%s)" % sql,
                args,
            )
            db_triggers = cursor.fetchall()

        # Note: if this test fails, a trigger may have been added, but not
        # added to the list of expected triggers.
        triggers_found = [trigger[0] for trigger in db_triggers]
        missing_triggers = [
            trigger for trigger in triggers if trigger not in triggers_found
        ]
        self.assertEqual(
            len(triggers),
            len(db_triggers),
            "Missing %s triggers in the database. Triggers missing: %s"
            % (len(triggers) - len(db_triggers), missing_triggers),
        )

    def test_register_system_triggers_ensures_zone_serial(self):
        mock_create = self.patch(zone_serial, "create_if_not_exists")
        register_system_triggers()
        self.assertThat(mock_create, MockCalledOnceWith())
