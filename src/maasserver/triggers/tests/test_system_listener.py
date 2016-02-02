# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Use the `PostgresListenerService` to test all of the triggers from for
`maasserver.triggers.system`"""

__all__ = []

from crochet import wait_for
from maasserver.triggers.system import register_system_triggers
from maasserver.triggers.tests.helper import TransactionalHelpersMixin
from maasserver.utils.threads import deferToDatabase
from maastesting.djangotestcase import DjangoTransactionTestCase
from provisioningserver.utils.twisted import DeferredValue
from twisted.internet.defer import inlineCallbacks


wait_for_reactor = wait_for(30)  # 30 seconds.


class TestDHCPListeners(DjangoTransactionTestCase, TransactionalHelpersMixin):
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
