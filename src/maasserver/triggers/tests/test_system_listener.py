# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Use the `PostgresListenerService` to test all of the triggers from for
`maasserver.triggers.system`"""

__all__ = []

from crochet import wait_for
from maasserver.enum import (
    IPADDRESS_TYPE,
    IPRANGE_TYPE,
)
from maasserver.testing.factory import factory
from maasserver.triggers.system import register_system_triggers
from maasserver.triggers.tests.helper import TransactionalHelpersMixin
from maasserver.utils.threads import deferToDatabase
from maastesting.djangotestcase import DjangoTransactionTestCase
from netaddr import IPAddress
from provisioningserver.utils.twisted import DeferredValue
from twisted.internet.defer import inlineCallbacks


wait_for_reactor = wait_for(30)  # 30 seconds.


class TestDHCPVLANListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test for the DHCP triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_primary_when_turned_on(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan)

        primary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_vlan, vlan.id, {
                "dhcp_on": True,
                "primary_rack": primary_rack,
            })
            yield primary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_primary_and_secondary_when_turned_on(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan)

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_vlan, vlan.id, {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_old_primary_when_turned_off(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
        })

        primary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_vlan, vlan.id, {
                "dhcp_on": False,
                "primary_rack": None,
            })
            yield primary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_primary_and_secondary_when_turned_off(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_vlan, vlan.id, {
                "dhcp_on": False,
                "primary_rack": None,
                "secondary_rack": None,
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_old_and_new_primary_when_changed(self):
        yield deferToDatabase(register_system_triggers)
        old_primary_rack = yield deferToDatabase(self.create_rack_controller)
        new_primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": old_primary_rack,
        })

        old_primary_dv = DeferredValue()
        new_primary_rack_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % old_primary_rack.id,
            lambda *args: old_primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % new_primary_rack.id,
            lambda *args: new_primary_rack_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_vlan, vlan.id, {
                "primary_rack": new_primary_rack,
            })
            yield old_primary_dv.get(timeout=2)
            yield new_primary_rack_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_old_and_new_secondary_when_changed(self):
        yield deferToDatabase(register_system_triggers)
        old_secondary_rack = yield deferToDatabase(self.create_rack_controller)
        new_secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "secondary_rack": old_secondary_rack,
        })

        old_secondary_dv = DeferredValue()
        new_secondary_rack_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % old_secondary_rack.id,
            lambda *args: old_secondary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % new_secondary_rack.id,
            lambda *args: new_secondary_rack_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_vlan, vlan.id, {
                "secondary_rack": new_secondary_rack,
            })
            yield old_secondary_dv.get(timeout=2)
            yield new_secondary_rack_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_old_and_new_pimary_and_secondary(self):
        yield deferToDatabase(register_system_triggers)
        old_primary_rack = yield deferToDatabase(self.create_rack_controller)
        new_primary_rack = yield deferToDatabase(self.create_rack_controller)
        old_secondary_rack = yield deferToDatabase(self.create_rack_controller)
        new_secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": old_primary_rack,
            "secondary_rack": old_secondary_rack,
        })

        old_primary_dv = DeferredValue()
        new_primary_rack_dv = DeferredValue()
        old_secondary_dv = DeferredValue()
        new_secondary_rack_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % old_primary_rack.id,
            lambda *args: old_primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % new_primary_rack.id,
            lambda *args: new_primary_rack_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % old_secondary_rack.id,
            lambda *args: old_secondary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % new_secondary_rack.id,
            lambda *args: new_secondary_rack_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_vlan, vlan.id, {
                "primary_rack": new_primary_rack,
                "secondary_rack": new_secondary_rack,
            })
            yield old_primary_dv.get(timeout=2)
            yield new_primary_rack_dv.get(timeout=2)
            yield old_secondary_dv.get(timeout=2)
            yield new_secondary_rack_dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDHCPSubnetListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test for the DHCP triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_old_vlan_and_new_vlan(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack_1 = yield deferToDatabase(self.create_rack_controller)
        secondary_rack_1 = yield deferToDatabase(self.create_rack_controller)
        vlan_1 = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack_1,
            "secondary_rack": secondary_rack_1,
        })
        primary_rack_2 = yield deferToDatabase(self.create_rack_controller)
        secondary_rack_2 = yield deferToDatabase(self.create_rack_controller)
        vlan_2 = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack_2,
            "secondary_rack": secondary_rack_2,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan_1,
        })

        listener = self.make_listener_without_delay()
        primary_dv_1 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack_1.id,
            lambda *args: primary_dv_1.set(args))
        secondary_dv_1 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack_1.id,
            lambda *args: secondary_dv_1.set(args))
        primary_dv_2 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack_2.id,
            lambda *args: primary_dv_2.set(args))
        secondary_dv_2 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack_2.id,
            lambda *args: secondary_dv_2.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_subnet, subnet.id, {
                "vlan": vlan_2,
            })
            yield primary_dv_1.get(timeout=2)
            yield secondary_dv_1.get(timeout=2)
            yield primary_dv_1.get(timeout=2)
            yield secondary_dv_2.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_vlan_when_cidr_changes(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            network = factory.make_ip4_or_6_network()
            yield deferToDatabase(self.update_subnet, subnet.id, {
                "cidr": str(network.cidr),
                "gateway_ip": factory.pick_ip_in_network(network),
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_vlan_when_gateway_ip_changes(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_subnet, subnet.id, {
                "gateway_ip": factory.pick_ip_in_network(
                    subnet.get_ipnetwork(), but_not=[subnet.gateway_ip]),
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_vlan_when_dns_servers_changes(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_subnet, subnet.id, {
                "dns_servers": [factory.pick_ip_in_network(
                    subnet.get_ipnetwork(), but_not=subnet.dns_servers)],
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_vlan_when_subnet_deleted(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_subnet, subnet.id)
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDHCPIPRangeListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test for the DHCP triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_new_managed_dhcp_range(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        network = factory.make_ipv4_network()
        subnet = yield deferToDatabase(self.create_subnet, {
            "cidr": str(network.cidr),
            "vlan": vlan,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            network = subnet.get_ipnetwork()
            start_ip = str(IPAddress(network.first + 2))
            end_ip = str(IPAddress(network.first + 3))
            yield deferToDatabase(self.create_iprange, {
                "subnet": subnet,
                "type": IPRANGE_TYPE.MANAGED_DHCP,
                "start_ip": start_ip,
                "end_ip": end_ip,
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_updated_managed_dhcp_range(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        network = factory.make_ipv4_network()
        subnet = yield deferToDatabase(self.create_subnet, {
            "cidr": str(network.cidr),
            "vlan": vlan,
        })
        network = subnet.get_ipnetwork()
        start_ip = str(IPAddress(network.first + 2))
        end_ip = str(IPAddress(network.first + 3))
        ip_range = yield deferToDatabase(self.create_iprange, {
            "subnet": subnet,
            "type": IPRANGE_TYPE.MANAGED_DHCP,
            "start_ip": start_ip,
            "end_ip": end_ip,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            end_ip = str(IPAddress(network.first + 4))
            yield deferToDatabase(self.update_iprange, ip_range.id, {
                "end_ip": end_ip,
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_updated_from_managed_to_other(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        network = factory.make_ipv4_network()
        subnet = yield deferToDatabase(self.create_subnet, {
            "cidr": str(network.cidr),
            "vlan": vlan,
        })
        network = subnet.get_ipnetwork()
        start_ip = str(IPAddress(network.first + 2))
        end_ip = str(IPAddress(network.first + 3))
        ip_range = yield deferToDatabase(self.create_iprange, {
            "subnet": subnet,
            "type": IPRANGE_TYPE.MANAGED_DHCP,
            "start_ip": start_ip,
            "end_ip": end_ip,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_iprange, ip_range.id, {
                "type": IPRANGE_TYPE.ADMIN_RESERVED,
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_updated_from_other_to_managed(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        network = factory.make_ipv4_network()
        subnet = yield deferToDatabase(self.create_subnet, {
            "cidr": str(network.cidr),
            "vlan": vlan,
        })
        network = subnet.get_ipnetwork()
        start_ip = str(IPAddress(network.first + 2))
        end_ip = str(IPAddress(network.first + 3))
        ip_range = yield deferToDatabase(self.create_iprange, {
            "subnet": subnet,
            "type": IPRANGE_TYPE.ADMIN_RESERVED,
            "start_ip": start_ip,
            "end_ip": end_ip,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_iprange, ip_range.id, {
                "type": IPRANGE_TYPE.MANAGED_DHCP,
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_deleting_range(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        network = factory.make_ipv4_network()
        subnet = yield deferToDatabase(self.create_subnet, {
            "cidr": str(network.cidr),
            "vlan": vlan,
        })
        network = subnet.get_ipnetwork()
        start_ip = str(IPAddress(network.first + 2))
        end_ip = str(IPAddress(network.first + 3))
        ip_range = yield deferToDatabase(self.create_iprange, {
            "subnet": subnet,
            "type": IPRANGE_TYPE.MANAGED_DHCP,
            "start_ip": start_ip,
            "end_ip": end_ip,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_iprange, ip_range.id)
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDHCPStaticIPAddressListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test for the DHCP triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_new_staticipaddress(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        user = yield deferToDatabase(self.create_user)

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_staticipaddress, {
                "subnet": subnet,
                "alloc_type": IPADDRESS_TYPE.USER_RESERVED,
                "user": user,
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_both_vlans_on_subnet_switch(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack_1 = yield deferToDatabase(self.create_rack_controller)
        secondary_rack_1 = yield deferToDatabase(self.create_rack_controller)
        vlan_1 = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack_1,
            "secondary_rack": secondary_rack_1,
        })
        subnet_1 = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan_1,
        })
        primary_rack_2 = yield deferToDatabase(self.create_rack_controller)
        secondary_rack_2 = yield deferToDatabase(self.create_rack_controller)
        vlan_2 = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack_2,
            "secondary_rack": secondary_rack_2,
        })
        subnet_2 = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan_2,
        })
        user = yield deferToDatabase(self.create_user)
        staticip = yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet_1,
            "alloc_type": IPADDRESS_TYPE.USER_RESERVED,
            "user": user,
        })

        listener = self.make_listener_without_delay()
        primary_dv_1 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack_1.id,
            lambda *args: primary_dv_1.set(args))
        secondary_dv_1 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack_1.id,
            lambda *args: secondary_dv_1.set(args))
        primary_dv_2 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack_2.id,
            lambda *args: primary_dv_2.set(args))
        secondary_dv_2 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack_2.id,
            lambda *args: secondary_dv_2.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_staticipaddress, staticip.id, {
                "subnet": subnet_2,
                "ip": factory.pick_ip_in_Subnet(subnet_2),
            })
            yield primary_dv_1.get(timeout=2)
            yield secondary_dv_1.get(timeout=2)
            yield primary_dv_2.get(timeout=2)
            yield secondary_dv_2.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_one_vlan_on_switch_subnet_on_same_vlan(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet_1 = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        subnet_2 = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        user = yield deferToDatabase(self.create_user)
        staticip = yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet_1,
            "alloc_type": IPADDRESS_TYPE.USER_RESERVED,
            "user": user,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_staticipaddress, staticip.id, {
                "subnet": subnet_2,
                "ip": factory.pick_ip_in_Subnet(subnet_2),
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_assigning_an_ip(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(self.create_interface, {
            "node": node,
            "vlan": vlan,
        })
        staticip = yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet,
            "alloc_type": IPADDRESS_TYPE.AUTO,
            "interface": interface,
            "ip": "",
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_staticipaddress, staticip.id, {
                "ip": factory.pick_ip_in_Subnet(subnet),
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_releasing_an_ip(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(self.create_interface, {
            "node": node,
            "vlan": vlan,
        })
        staticip = yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet,
            "alloc_type": IPADDRESS_TYPE.AUTO,
            "interface": interface,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_staticipaddress, staticip.id, {
                "ip": "",
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_changing_an_ip(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(self.create_interface, {
            "node": node,
            "vlan": vlan,
        })
        staticip = yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet,
            "alloc_type": IPADDRESS_TYPE.AUTO,
            "interface": interface,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_staticipaddress, staticip.id, {
                "ip": factory.pick_ip_in_Subnet(subnet, but_not=[staticip.ip]),
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_delet_an_ip(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(self.create_interface, {
            "node": node,
            "vlan": vlan,
        })
        staticip = yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet,
            "alloc_type": IPADDRESS_TYPE.AUTO,
            "interface": interface,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_staticipaddress, staticip.id, {
                "ip": factory.pick_ip_in_Subnet(subnet, but_not=[staticip.ip]),
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDHCPInterfaceListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test for the DHCP triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_interface_name_change(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(self.create_interface, {
            "node": node,
            "vlan": vlan,
        })
        yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet,
            "alloc_type": IPADDRESS_TYPE.AUTO,
            "interface": interface,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_interface, interface.id, {
                "name": factory.make_name("eth"),
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_mac_address_change(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(self.create_interface, {
            "node": node,
            "vlan": vlan,
        })
        yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet,
            "alloc_type": IPADDRESS_TYPE.AUTO,
            "interface": interface,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_interface, interface.id, {
                "mac_address": factory.make_mac_address(),
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDHCPNodeListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test for the DHCP triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_hostname_change(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(self.create_interface, {
            "node": node,
            "vlan": vlan,
        })
        yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet,
            "alloc_type": IPADDRESS_TYPE.AUTO,
            "interface": interface,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_node, node.system_id, {
                "hostname": factory.make_name("host"),
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()
