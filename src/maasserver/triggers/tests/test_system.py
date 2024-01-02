# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from contextlib import closing

from django.db import connection
from twisted.internet.defer import inlineCallbacks

from maasserver.enum import NODE_STATUS, NODE_TYPE
from maasserver.models import Domain
from maasserver.models.dnspublication import zone_serial
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.triggers.models.dns_notifications import (
    DynamicDNSUpdateNotification,
)
from maasserver.triggers.system import register_system_triggers
from maasserver.triggers.testing import (
    NotifyHelperMixin,
    TransactionalHelpersMixin,
)
from maasserver.utils.orm import psql_array
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from maastesting.matchers import MockCalledOnceWith

wait_for_reactor = wait_for()


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


class TestSysDNSUpdates(
    MAASTransactionServerTestCase, TransactionalHelpersMixin, NotifyHelperMixin
):
    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_dnsresource_ip_addresses_insert(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        domain = yield deferToDatabase(self.create_domain)
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_dnsresource_ip_addresses",
            "sys_dns_updates",
            ops=("insert",),
            trigger="sys_dns_updates_dns_ip_insert",
        )
        self.start_reading()
        try:
            static_ip = yield deferToDatabase(self.create_staticipaddress)
            rec = yield deferToDatabase(
                self.create_dnsresource,
                params={"domain": domain, "ip_addresses": [static_ip]},
            )
            yield self.get_notify(
                "sys_dns_updates"
            )  # ignore RELOAD from domain creation
            msg = yield self.get_notify("sys_dns_updates")
            decoded_msg = DynamicDNSUpdateNotification(
                msg
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg,
                f"INSERT {domain.name} {rec.name} A {domain.ttl if domain.ttl else 0} {static_ip.ip}",
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_dnsresource_ip_addresses_delete(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        domain = yield deferToDatabase(self.create_domain)
        static_ip = yield deferToDatabase(self.create_staticipaddress)
        rec = yield deferToDatabase(
            self.create_dnsresource,
            params={"domain": domain, "ip_addresses": [static_ip]},
        )
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_dnsresource_ip_addresses",
            "sys_dns_updates",
            ops=("delete",),
            trigger="sys_dns_updates_dns_ip_delete",
        )
        self.start_reading()
        try:
            yield deferToDatabase(rec.delete)
            msg = yield self.get_notify("sys_dns_updates")
            decoded_msg = DynamicDNSUpdateNotification(
                msg
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg,
                f"DELETE {domain.name} {rec.name} A {static_ip.ip}",
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_dnsresource_update(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        domain = yield deferToDatabase(self.create_domain)
        static_ip = yield deferToDatabase(self.create_staticipaddress)
        rec = yield deferToDatabase(
            self.create_dnsresource,
            params={"domain": domain, "ip_addresses": [static_ip]},
        )
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_dnsresource",
            "sys_dns_updates",
            ops=("update",),
        )
        self.start_reading()
        try:
            rec.address_ttl = 30
            yield deferToDatabase(rec.save)
            msg = yield self.get_notify("sys_dns_updates")
            decoded_msg = DynamicDNSUpdateNotification(
                msg
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg,
                f"UPDATE {domain.name} {rec.name} A 30 {static_ip.ip}",
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_dnsresource_delete(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        domain = yield deferToDatabase(self.create_domain)
        static_ip = yield deferToDatabase(self.create_staticipaddress)
        rec = yield deferToDatabase(
            self.create_dnsresource,
            params={"domain": domain, "ip_addresses": [static_ip]},
        )
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_dnsresource",
            "sys_dns_updates",
            ops=("delete",),
        )
        self.start_reading()
        try:
            yield deferToDatabase(rec.delete)
            msg = yield self.get_notify("sys_dns_updates")
            decoded_msg = DynamicDNSUpdateNotification(
                msg
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg,
                f"DELETE {domain.name} {rec.name} A {static_ip.ip}",
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_dnsdata_update(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        domain = yield deferToDatabase(self.create_domain)
        rec = yield deferToDatabase(
            self.create_dnsresource, params={"domain": domain}
        )
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_dnsdata",
            "sys_dns_updates",
            ops=("update",),
        )
        self.start_reading()
        try:
            dnsdata = yield deferToDatabase(
                self.create_dnsdata,
                params={
                    "dnsresource": rec,
                    "rrtype": "TXT",
                    "rrdata": factory.make_name(),
                },
            )
            dnsdata.rrdata = factory.make_name()
            yield deferToDatabase(dnsdata.save)
            msg = yield self.get_notify("sys_dns_updates")
            decoded_msg = DynamicDNSUpdateNotification(
                msg
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg,
                f"UPDATE-DATA {dnsdata.id}",
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_dnsdata_insert(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        domain = yield deferToDatabase(self.create_domain)
        rec = yield deferToDatabase(
            self.create_dnsresource, {"domain": domain}
        )
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_dnsdata",
            "sys_dns_updates",
            ops=("insert",),
        )
        self.start_reading()
        try:
            dnsdata = yield deferToDatabase(
                self.create_dnsdata,
                params={
                    "dnsresource": rec,
                    "rrtype": "TXT",
                    "rrdata": factory.make_name(),
                },
            )
            msg = yield self.get_notify("sys_dns_updates")
            decoded_msg = DynamicDNSUpdateNotification(
                msg
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg,
                f"INSERT-DATA {dnsdata.id}",
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_dnsdata_delete(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        domain = yield deferToDatabase(self.create_domain)
        rec = yield deferToDatabase(
            self.create_dnsresource, params={"domain": domain}
        )
        dnsdata = yield deferToDatabase(
            self.create_dnsdata,
            params={
                "dnsresource": rec,
                "rrtype": "TXT",
                "rrdata": factory.make_name(),
            },
        )
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_dnsdata",
            "sys_dns_updates",
            ops=("delete",),
        )
        self.start_reading()
        try:
            yield deferToDatabase(dnsdata.delete)
            msg = yield self.get_notify("sys_dns_updates")
            decoded_msg = DynamicDNSUpdateNotification(
                msg
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg,
                f"DELETE {domain.name} {rec.name} {dnsdata.rrtype}",
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_domain_reload(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_domain",
            "sys_dns_updates",
            ops=("insert",),
        )
        self.start_reading()
        try:
            yield deferToDatabase(self.create_domain)
            msg = yield self.get_notify("sys_dns_updates")
            decoded_msg = DynamicDNSUpdateNotification(
                msg
            ).get_decoded_message()
            self.assertEqual(decoded_msg, "RELOAD")
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_subnet_reload(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_subnet",
            "sys_dns_updates",
            ops=("insert",),
        )
        self.start_reading()
        try:
            yield deferToDatabase(self.create_subnet)
            msg = yield self.get_notify("sys_dns_updates")
            decoded_msg = DynamicDNSUpdateNotification(
                msg
            ).get_decoded_message()
            self.assertEqual(decoded_msg, "RELOAD")
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_interface_static_ip_address_insert(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_interface_ip_addresses",
            "sys_dns_updates",
            ops=("insert",),
            trigger="sys_dns_updates_interface_ip_insert",
        )
        vlan = yield deferToDatabase(self.create_vlan)
        subnet = yield deferToDatabase(
            self.create_subnet, params={"vlan": vlan}
        )
        rack_controller = yield deferToDatabase(
            self.create_rack_controller,
            params={"vlan": vlan, "subnet": subnet},
        )
        self.start_reading()
        try:
            node = yield deferToDatabase(
                self.create_node_with_interface,
                params={
                    "subnet": subnet,
                    "status": NODE_STATUS.DEPLOYED,
                    "node_type": NODE_TYPE.MACHINE,
                    "primary_rack": rack_controller,
                },
            )
            domain = yield deferToDatabase(Domain.objects.get_default_domain)
            expected_iface = yield deferToDatabase(
                lambda: node.current_config.interface_set.first()
            )
            expected_ip = yield deferToDatabase(
                lambda: self.create_staticipaddress(
                    params={
                        "ip": subnet.get_next_ip_for_allocation()[0],
                        "interface": expected_iface,
                        "subnet": subnet,
                    }
                )
            )
            msg1 = yield self.get_notify("sys_dns_updates")
            decoded_msg1 = DynamicDNSUpdateNotification(
                msg1
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg1,
                f"INSERT {domain.name} {node.hostname} A 0 {expected_ip.ip}",
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_interface_static_ip_address_insert_with_non_default_domain(
        self,
    ):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_interface_ip_addresses",
            "sys_dns_updates",
            ops=("insert",),
            trigger="sys_dns_updates_interface_ip_insert",
        )
        vlan = yield deferToDatabase(self.create_vlan)
        subnet = yield deferToDatabase(
            self.create_subnet, params={"vlan": vlan}
        )
        domain = yield deferToDatabase(self.create_domain)
        rack_controller = yield deferToDatabase(
            self.create_rack_controller,
            params={"vlan": vlan, "subnet": subnet},
        )
        self.start_reading()
        try:
            node = yield deferToDatabase(
                self.create_node_with_interface,
                params={
                    "subnet": subnet,
                    "status": NODE_STATUS.DEPLOYED,
                    "domain": domain,
                    "node_type": NODE_TYPE.MACHINE,
                    "primary_rack": rack_controller,
                },
            )
            expected_iface = yield deferToDatabase(
                lambda: node.current_config.interface_set.first()
            )
            expected_ip = yield deferToDatabase(
                lambda: self.create_staticipaddress(
                    params={
                        "ip": subnet.get_next_ip_for_allocation()[0],
                        "interface": expected_iface,
                        "subnet": subnet,
                    }
                )
            )
            msg1 = yield self.get_notify("sys_dns_updates")
            decoded_msg1 = DynamicDNSUpdateNotification(
                msg1
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg1,
                f"INSERT {domain.name} {node.hostname} A 0 {expected_ip.ip}",
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_interface_static_ip_address_delete(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_interface_ip_addresses",
            "sys_dns_updates",
            ops=("delete",),
            trigger="sys_dns_updates_interface_ip_delete",
        )
        vlan = yield deferToDatabase(self.create_vlan)
        subnet = yield deferToDatabase(
            self.create_subnet, params={"vlan": vlan}
        )
        node = yield deferToDatabase(
            self.create_node_with_interface,
            params={"subnet": subnet, "status": NODE_STATUS.DEPLOYED},
        )
        domain = yield deferToDatabase(Domain.objects.get_default_domain)
        iface = yield deferToDatabase(
            lambda: node.current_config.interface_set.first()
        )
        ip1 = yield deferToDatabase(
            lambda: self.create_staticipaddress(
                params={
                    "ip": subnet.get_next_ip_for_allocation()[0],
                    "interface": iface,
                    "subnet": subnet,
                }
            )
        )
        self.start_reading()
        try:
            yield deferToDatabase(iface.unlink_ip_address, ip1)
            msg1 = yield self.get_notify("sys_dns_updates")
            decoded_msg1 = DynamicDNSUpdateNotification(
                msg1
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg1,
                f"DELETE {domain.name} {node.hostname} A {ip1.ip}",
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_interface_static_ip_address_ignores_controllers(
        self,
    ):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_interface_ip_addresses",
            "sys_dns_updates",
            ops=("delete",),
            trigger="sys_dns_updates_interface_ip_delete",
        )
        vlan = yield deferToDatabase(self.create_vlan)
        subnet1 = yield deferToDatabase(
            self.create_subnet, params={"vlan": vlan}
        )
        subnet2 = yield deferToDatabase(
            self.create_subnet, params={"vlan": vlan}
        )
        node1 = yield deferToDatabase(
            self.create_node_with_interface,
            params={
                "node_type": NODE_TYPE.RACK_CONTROLLER,
                "subnet": subnet1,
                "status": NODE_STATUS.DEPLOYED,
            },
        )
        node2 = yield deferToDatabase(
            self.create_node_with_interface,
            params={"subnet": subnet2, "status": NODE_STATUS.DEPLOYED},
        )
        domain = yield deferToDatabase(Domain.objects.get_default_domain)
        iface1 = yield deferToDatabase(
            lambda: node1.current_config.interface_set.first()
        )
        iface2 = yield deferToDatabase(
            lambda: node2.current_config.interface_set.first()
        )
        ip1 = yield deferToDatabase(
            lambda: self.create_staticipaddress(
                params={
                    "ip": subnet1.get_next_ip_for_allocation()[0],
                    "interface": iface1,
                    "subnet": subnet1,
                }
            )
        )
        ip2 = yield deferToDatabase(
            lambda: self.create_staticipaddress(
                params={
                    "ip": subnet2.get_next_ip_for_allocation()[0],
                    "interface": iface2,
                    "subnet": subnet2,
                }
            )
        )
        self.start_reading()
        try:
            yield deferToDatabase(iface1.unlink_ip_address, ip1)
            yield deferToDatabase(iface2.unlink_ip_address, ip2)
            expected_msgs = (
                f"DELETE {domain.name} {node2.hostname} A {ip2.ip}",
            )
            for exp in expected_msgs:
                msg = yield self.get_notify("sys_dns_updates")
                decoded_msg = DynamicDNSUpdateNotification(
                    msg
                ).get_decoded_message()
                self.assertEqual(decoded_msg, exp)
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamc_update_ip_boot_interface_update(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_staticipaddress",
            "sys_dns_updates",
            ops=("update",),
            trigger="sys_dns_updates_ip_update",
        )
        vlan = yield deferToDatabase(self.create_vlan)
        subnet = yield deferToDatabase(
            self.create_subnet, params={"vlan": vlan}
        )
        node = yield deferToDatabase(
            self.create_node_with_interface,
            params={"subnet": subnet, "status": NODE_STATUS.DEPLOYED},
        )
        domain = yield deferToDatabase(Domain.objects.get_default_domain)
        iface = yield deferToDatabase(
            lambda: node.current_config.interface_set.first()
        )
        ip = yield deferToDatabase(
            lambda: self.create_staticipaddress(
                params={
                    "ip": subnet.get_next_ip_for_allocation()[0],
                    "interface": iface,
                    "subnet": subnet,
                }
            )
        )
        old_ip = ip.ip

        def _set_new_ip():
            ip.ip = subnet.get_next_ip_for_allocation()[0]
            ip.save()

        self.start_reading()
        try:
            yield deferToDatabase(_set_new_ip)
            msg1 = yield self.get_notify("sys_dns_updates")
            decoded_msg1 = DynamicDNSUpdateNotification(
                msg1
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg1,
                f"DELETE {domain.name} {node.hostname} A {old_ip}",
            )
            msg2 = yield self.get_notify("sys_dns_updates")
            decoded_msg2 = DynamicDNSUpdateNotification(
                msg2
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg2,
                f"INSERT {domain.name} {node.hostname} A 0 {ip.ip}",
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamc_update_ip_non_boot_interface_update(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_staticipaddress",
            "sys_dns_updates",
            ops=("update",),
            trigger="sys_dns_updates_ip_update",
        )
        vlan = yield deferToDatabase(self.create_vlan)
        subnet = yield deferToDatabase(
            self.create_subnet, params={"vlan": vlan}
        )
        node = yield deferToDatabase(
            self.create_node_with_interface,
            params={"subnet": subnet, "status": NODE_STATUS.DEPLOYED},
        )
        domain = yield deferToDatabase(Domain.objects.get_default_domain)
        # set boot interface
        yield deferToDatabase(
            lambda: node.current_config.interface_set.first()
        )
        iface2 = yield deferToDatabase(
            self.create_interface, params={"node": node}
        )
        # Change ip of the non-boot interface
        ip = yield deferToDatabase(
            lambda: self.create_staticipaddress(
                params={
                    "ip": subnet.get_next_ip_for_allocation()[0],
                    "interface": iface2,
                    "subnet": subnet,
                }
            )
        )
        old_ip = ip.ip

        def _set_new_ip():
            ip.ip = subnet.get_next_ip_for_allocation()[0]
            ip.save()

        self.start_reading()
        try:
            yield deferToDatabase(_set_new_ip)
            msg1 = yield self.get_notify("sys_dns_updates")
            decoded_msg1 = DynamicDNSUpdateNotification(
                msg1
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg1,
                f"DELETE {domain.name} {iface2.name}.{node.hostname} A {old_ip}",
            )
            msg2 = yield self.get_notify("sys_dns_updates")
            decoded_msg2 = DynamicDNSUpdateNotification(
                msg2
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg2,
                f"INSERT {domain.name} {iface2.name}.{node.hostname} A 0 {ip.ip}",
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_controller_insert(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_node",
            "sys_dns_updates",
            ops=("insert",),
        )
        self.start_reading()
        try:
            yield deferToDatabase(self.create_rack_controller)
            msg = yield self.get_notify("sys_dns_updates")
            decoded_msg = DynamicDNSUpdateNotification(
                msg
            ).get_decoded_message()
            self.assertEqual(decoded_msg, "RELOAD")
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_controller_update(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_node",
            "sys_dns_updates",
            ops=("update",),
        )
        self.start_reading()
        controller = yield deferToDatabase(self.create_rack_controller)
        try:
            controller.cpu_speed = 10
            yield deferToDatabase(controller.save)
            msg = yield self.get_notify("sys_dns_updates")
            decoded_msg = DynamicDNSUpdateNotification(
                msg
            ).get_decoded_message()
            self.assertEqual(decoded_msg, "RELOAD")
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_node_delete(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_node",
            "sys_dns_updates",
            ops=("delete",),
        )
        node = yield deferToDatabase(self.create_node)
        domain = yield deferToDatabase(Domain.objects.get_default_domain)
        self.start_reading()
        try:
            yield deferToDatabase(node.delete)
            msg = yield self.get_notify("sys_dns_updates")
            decoded_msg = DynamicDNSUpdateNotification(
                msg
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg, f"DELETE {domain.name} {node.hostname} A"
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_boot_interface_delete(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_node",
            "sys_dns_updates",
            ops=("delete",),
        )
        subnet = yield deferToDatabase(self.create_subnet)
        node = yield deferToDatabase(
            self.create_node_with_interface, params={"subnet": subnet}
        )
        domain = yield deferToDatabase(Domain.objects.get_default_domain)
        iface = yield deferToDatabase(
            lambda: node.current_config.interface_set.first()
        )
        self.start_reading()
        try:
            yield deferToDatabase(iface.delete)
            msg1 = yield self.get_notify("sys_dns_updates")
            decoded_msg = DynamicDNSUpdateNotification(
                msg1
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg, f"DELETE {domain.name} {node.hostname} A"
            )
            msg2 = yield self.get_notify("sys_dns_updates")
            decoded_msg2 = DynamicDNSUpdateNotification(
                msg2
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg2,
                f"DELETE {domain.name} {iface.name}.{node.hostname} A",
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_non_boot_interface_delete(self):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_node",
            "sys_dns_updates",
            ops=("delete",),
        )
        subnet = yield deferToDatabase(self.create_subnet)
        node = yield deferToDatabase(
            self.create_node_with_interface, params={"subnet": subnet}
        )
        domain = yield deferToDatabase(Domain.objects.get_default_domain)
        yield deferToDatabase(
            lambda: node.current_config.interface_set.first()
        )
        iface2 = yield deferToDatabase(
            self.create_interface, params={"node": node}
        )
        self.start_reading()
        try:
            yield deferToDatabase(iface2.delete)
            msg1 = yield self.get_notify("sys_dns_updates")
            decoded_msg = DynamicDNSUpdateNotification(
                msg1
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg,
                f"DELETE {domain.name} {iface2.name}.{node.hostname} A",
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_creates_iface_record_only_for_non_boot_iface(
        self,
    ):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_interface_ip_addresses",
            "sys_dns_updates",
            ops=("insert",),
            trigger="sys_dns_updates_interface_ip_insert",
        )
        vlan = yield deferToDatabase(self.create_vlan)
        subnet = yield deferToDatabase(
            self.create_subnet, params={"vlan": vlan}
        )
        rack_controller = yield deferToDatabase(
            self.create_rack_controller,
            params={"vlan": vlan, "subnet": subnet},
        )
        self.start_reading()
        try:
            node = yield deferToDatabase(
                self.create_node_with_interface,
                params={
                    "subnet": subnet,
                    "status": NODE_STATUS.DEPLOYED,
                    "node_type": NODE_TYPE.MACHINE,
                    "primary_rack": rack_controller,
                },
            )
            domain = yield deferToDatabase(Domain.objects.get_default_domain)
            iface1 = yield deferToDatabase(
                lambda: node.current_config.interface_set.first()
            )
            iface2 = yield deferToDatabase(
                self.create_interface, params={"node": node}
            )
            ip1 = yield deferToDatabase(
                lambda: self.create_staticipaddress(
                    params={
                        "ip": subnet.get_next_ip_for_allocation()[0],
                        "interface": iface1,
                        "subnet": subnet,
                    }
                )
            )
            ip2 = yield deferToDatabase(
                lambda: self.create_staticipaddress(
                    params={
                        "ip": subnet.get_next_ip_for_allocation()[0],
                        "interface": iface2,
                        "subnet": subnet,
                    }
                )
            )
            msg1 = yield self.get_notify("sys_dns_updates")
            decoded_msg1 = DynamicDNSUpdateNotification(
                msg1
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg1,
                f"INSERT {domain.name} {node.hostname} A 0 {ip1.ip}",
            )
            msg2 = yield self.get_notify("sys_dns_updates")
            decoded_msg2 = DynamicDNSUpdateNotification(
                msg2
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg2,
                f"INSERT {domain.name} {iface2.name}.{node.hostname} A 0 {ip2.ip}",
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_interface_ip_address_handles_no_boot_interface(
        self,
    ):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_interface_ip_addresses",
            "sys_dns_updates",
            ops=("insert",),
            trigger="sys_dns_updates_interface_ip_insert",
        )
        vlan = yield deferToDatabase(self.create_vlan)
        subnet = yield deferToDatabase(
            self.create_subnet, params={"vlan": vlan}
        )
        rack_controller = yield deferToDatabase(
            self.create_rack_controller,
            params={"vlan": vlan, "subnet": subnet},
        )
        node = yield deferToDatabase(
            self.create_node_with_interface,
            params={
                "subnet": subnet,
                "status": NODE_STATUS.DEPLOYED,
                "node_type": NODE_TYPE.MACHINE,
                "primary_rack": rack_controller,
            },
        )
        domain = yield deferToDatabase(Domain.objects.get_default_domain)
        iface1 = yield deferToDatabase(
            lambda: node.current_config.interface_set.first()
        )
        self.start_reading()
        try:
            node.boot_interface = None
            yield deferToDatabase(node.save)
            ip1 = yield deferToDatabase(
                lambda: self.create_staticipaddress(
                    params={
                        "ip": subnet.get_next_ip_for_allocation()[0],
                        "interface": iface1,
                        "subnet": subnet,
                    }
                )
            )
            msg1 = yield self.get_notify("sys_dns_updates")
            decoded_msg1 = DynamicDNSUpdateNotification(
                msg1
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg1,
                f"INSERT {domain.name} {node.hostname} A 0 {ip1.ip}",
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_dynamic_update_node_update_handles_different_boot_interface(
        self,
    ):
        listener = self.make_listener_without_delay()
        yield self.set_service(listener)
        yield deferToDatabase(
            self.register_trigger,
            "maasserver_node",
            "sys_dns_updates",
            ops=("update",),
            trigger="sys_dns_updates_maasserver_node_update",
        )
        vlan = yield deferToDatabase(self.create_vlan)
        subnet = yield deferToDatabase(
            self.create_subnet, params={"vlan": vlan}
        )
        rack_controller = yield deferToDatabase(
            self.create_rack_controller,
            params={"vlan": vlan, "subnet": subnet},
        )
        node = yield deferToDatabase(
            self.create_node_with_interface,
            params={
                "subnet": subnet,
                "status": NODE_STATUS.DEPLOYED,
                "node_type": NODE_TYPE.MACHINE,
                "primary_rack": rack_controller,
            },
        )
        domain = yield deferToDatabase(Domain.objects.get_default_domain)
        iface1 = yield deferToDatabase(
            lambda: node.current_config.interface_set.first()
        )
        iface2 = yield deferToDatabase(
            self.create_interface, params={"node": node}
        )
        ip1 = yield deferToDatabase(
            lambda: self.create_staticipaddress(
                params={
                    "ip": subnet.get_next_ip_for_allocation()[0],
                    "interface": iface1,
                    "subnet": subnet,
                }
            )
        )
        ip2 = yield deferToDatabase(
            lambda: self.create_staticipaddress(
                params={
                    "ip": subnet.get_next_ip_for_allocation()[0],
                    "interface": iface2,
                    "subnet": subnet,
                }
            )
        )
        node.boot_interface = iface1
        yield deferToDatabase(node.save)
        self.start_reading()
        try:
            node.boot_interface = iface2
            yield deferToDatabase(node.save)
            msg1 = yield self.get_notify("sys_dns_updates")
            decoded_msg1 = DynamicDNSUpdateNotification(
                msg1
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg1,
                f"DELETE {domain.name} {node.hostname} A {ip1.ip}",
            )
            msg2 = yield self.get_notify("sys_dns_updates")
            decoded_msg2 = DynamicDNSUpdateNotification(
                msg2
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg2,
                f"INSERT {domain.name} {iface1.name}.{node.hostname} A 0 {ip1.ip}",
            )
            msg3 = yield self.get_notify("sys_dns_updates")
            decoded_msg3 = DynamicDNSUpdateNotification(
                msg3
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg3,
                f"DELETE {domain.name} {iface2.name}.{node.hostname} A {ip2.ip}",
            )
            msg4 = yield self.get_notify("sys_dns_updates")
            decoded_msg4 = DynamicDNSUpdateNotification(
                msg4
            ).get_decoded_message()
            self.assertEqual(
                decoded_msg4,
                f"INSERT {domain.name} {node.hostname} A 0 {ip2.ip}",
            )
        finally:
            self.stop_reading()
            yield self.postgres_listener_service.stopService()
