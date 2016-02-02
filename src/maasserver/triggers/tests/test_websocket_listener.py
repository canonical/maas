# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Use the `PostgresListenerService` to test all of the triggers from for
`maasserver.triggers.websocket`"""

__all__ = []

import random

from crochet import wait_for
from maasserver.enum import (
    IPADDRESS_TYPE,
    NODE_TYPE,
)
from maasserver.listener import PostgresListenerService
from maasserver.testing.factory import factory
from maasserver.triggers.tests.helper import TransactionalHelpersMixin
from maasserver.triggers.websocket import register_websocket_triggers
from maasserver.utils.threads import deferToDatabase
from maastesting.djangotestcase import DjangoTransactionTestCase
from provisioningserver.utils.twisted import DeferredValue
from twisted.internet.defer import inlineCallbacks


wait_for_reactor = wait_for(30)  # 30 seconds.


class TestNodeListener(DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers code."""

    scenarios = (
        ('machine', {
            'params': {'node_type': NODE_TYPE.MACHINE},
            'listener': 'machine',
            }),
        ('device', {
            'params': {'node_type': NODE_TYPE.DEVICE},
            'listener': 'device',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            node = yield deferToDatabase(self.create_node, self.params)
            yield dv.get(timeout=2)
            self.assertEqual(('create', node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        node = yield deferToDatabase(self.create_node, self.params)
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_node,
                node.system_id,
                {'hostname': factory.make_name('hostname')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        node = yield deferToDatabase(self.create_node, self.params)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_node, node.system_id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestDeviceWithParentListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        parent = yield deferToDatabase(self.create_node)
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_node, {
                    "node_type": NODE_TYPE.DEVICE,
                    "parent": parent,
                    })
            yield dv.get(timeout=2)
            self.assertEqual(('update', parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_node,
                device.system_id,
                {'hostname': factory.make_name('hostname')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_node, device.system_id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', parent.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestZoneListener(DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the zone
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("zone", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            zone = yield deferToDatabase(self.create_zone)
            yield dv.get(timeout=2)
            self.assertEqual(('create', '%s' % zone.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("zone", lambda *args: dv.set(args))
        zone = yield deferToDatabase(self.create_zone)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_zone,
                zone.id,
                {'cluster_name': factory.make_name('cluster_name')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % zone.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("zone", lambda *args: dv.set(args))
        zone = yield deferToDatabase(self.create_zone)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_zone, zone.id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', '%s' % zone.id), dv.value)
        finally:
            yield listener.stopService()


class TestTagListener(DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the tag
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("tag", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            tag = yield deferToDatabase(self.create_tag)
            yield dv.get(timeout=2)
            self.assertEqual(('create', '%s' % tag.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("tag", lambda *args: dv.set(args))
        tag = yield deferToDatabase(self.create_tag)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_tag,
                tag.id,
                {'name': factory.make_name('tag')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % tag.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("tag", lambda *args: dv.set(args))
        tag = yield deferToDatabase(self.create_tag)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_tag, tag.id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', '%s' % tag.id), dv.value)
        finally:
            yield listener.stopService()


class TestNodeTagListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_node_tags table."""

    scenarios = (
        ('machine', {
            'params': {'node_type': NODE_TYPE.MACHINE},
            'listener': 'machine',
            }),
        ('device', {
            'params': {'node_type': NODE_TYPE.DEVICE},
            'listener': 'device',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        tag = yield deferToDatabase(self.create_tag)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.add_node_to_tag, node, tag)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        tag = yield deferToDatabase(self.create_tag)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.remove_node_from_tag, node, tag)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_node_handler_with_update_on_tag_rename(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        tag = yield deferToDatabase(self.create_tag)
        yield deferToDatabase(self.add_node_to_tag, node, tag)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            tag = yield deferToDatabase(
                self.update_tag, tag.id, {'name': factory.make_name("tag")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestDeviceWithParentTagListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_node_tags table."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        tag = yield deferToDatabase(self.create_tag)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.add_node_to_tag, device, tag)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_websocket_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        tag = yield deferToDatabase(self.create_tag)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.remove_node_from_tag, device, tag)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_node_handler_with_update_on_tag_rename(self):
        yield deferToDatabase(register_websocket_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        tag = yield deferToDatabase(self.create_tag)
        yield deferToDatabase(self.add_node_to_tag, device, tag)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            tag = yield deferToDatabase(
                self.update_tag, tag.id, {'name': factory.make_name("tag")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestUserListener(DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the user
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            user = yield deferToDatabase(self.create_user)
            yield dv.get(timeout=2)
            self.assertEqual(('create', '%s' % user.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        user = yield deferToDatabase(self.create_user)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_user,
                user.id,
                {'username': factory.make_name('username')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % user.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        user = yield deferToDatabase(self.create_user)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_user, user.id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', '%s' % user.id), dv.value)
        finally:
            yield listener.stopService()


class TestEventListener(DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the event
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("event", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            event = yield deferToDatabase(self.create_event)
            yield dv.get(timeout=2)
            self.assertEqual(('create', '%s' % event.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("event", lambda *args: dv.set(args))
        event = yield deferToDatabase(self.create_event)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_event,
                event.id,
                {'description': factory.make_name('description')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % event.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("event", lambda *args: dv.set(args))
        event = yield deferToDatabase(self.create_event)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_event, event.id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', '%s' % event.id), dv.value)
        finally:
            yield listener.stopService()


class TestNodeEventListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_event table that notifies its node."""

    scenarios = (
        ('machine', {
            'params': {'node_type': NODE_TYPE.MACHINE},
            'listener': 'machine',
            }),
        ('device', {
            'params': {'node_type': NODE_TYPE.DEVICE},
            'listener': 'device',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_event, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestDeviceWithParentEventListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_event table that notifies its node."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_event, {"node": device})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestNodeStaticIPAddressListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_interfacestaticipaddresslink table that notifies its node."""

    scenarios = (
        ('machine', {
            'params': {'node_type': NODE_TYPE.MACHINE, 'interface': True},
            'listener': 'machine',
            }),
        ('device', {
            'params': {'node_type': NODE_TYPE.DEVICE, 'interface': True},
            'listener': 'device',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id)

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_staticipaddress, {"interface": interface})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id)
        sip = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_staticipaddress, sip.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestDeviceWithParentStaticIPAddressListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_interfacestaticipaddresslink table that notifies its node."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True})
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id)

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_staticipaddress, {"interface": interface})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_websocket_triggers)
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True})
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id)
        sip = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_staticipaddress, sip.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestNodeNodeResultListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    metadataserver_noderesult table that notifies its node."""

    scenarios = (
        ('machine', {
            'params': {'node_type': NODE_TYPE.MACHINE},
            'listener': 'machine',
            }),
        ('device', {
            'params': {'node_type': NODE_TYPE.DEVICE},
            'listener': 'device',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_noderesult, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        result = yield deferToDatabase(self.create_noderesult, {"node": node})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_noderesult, result.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestDeviceWithParentNodeResultListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    metadataserver_noderesult table that notifies its node."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_noderesult, {"node": device})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_websocket_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        result = yield deferToDatabase(
            self.create_noderesult, {"node": device})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_noderesult, result.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestNodeInterfaceListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_interface table that notifies its node."""

    scenarios = (
        ('machine', {
            'params': {'node_type': NODE_TYPE.MACHINE},
            'listener': 'machine',
            }),
        ('device', {
            'params': {'node_type': NODE_TYPE.DEVICE},
            'listener': 'device',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_interface, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_interface, interface.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_update(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_interface, interface.id, {
                "mac_address": factory.make_MAC()
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_old_node_on_update(self):
        yield deferToDatabase(register_websocket_triggers)
        node1 = yield deferToDatabase(self.create_node, self.params)
        node2 = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node1})
        dvs = [DeferredValue(), DeferredValue()]

        def set_defer_value(*args):
            for dv in dvs:
                if not dv.isSet:
                    dv.set(args)
                    break

        listener = PostgresListenerService()
        listener.register(self.listener, set_defer_value)
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_interface, interface.id, {
                "node": node2
                })
            yield dvs[0].get(timeout=2)
            yield dvs[1].get(timeout=2)
            self.assertItemsEqual([
                ('update', '%s' % node1.system_id),
                ('update', '%s' % node2.system_id),
                ], [dvs[0].value, dvs[1].value])
        finally:
            yield listener.stopService()


class TestDeviceWithParentInterfaceListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_interface table that notifies its node."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_interface, {"node": device})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_websocket_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        interface = yield deferToDatabase(
            self.create_interface, {"node": device})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_interface, interface.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_update(self):
        yield deferToDatabase(register_websocket_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        interface = yield deferToDatabase(
            self.create_interface, {"node": device})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_interface, interface.id, {
                "mac_address": factory.make_MAC()
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_old_node_on_update(self):
        yield deferToDatabase(register_websocket_triggers)
        device1, parent1 = yield deferToDatabase(
            self.create_device_with_parent)
        device2, parent2 = yield deferToDatabase(
            self.create_device_with_parent)
        interface = yield deferToDatabase(
            self.create_interface, {"node": device1})
        dvs = [DeferredValue(), DeferredValue()]

        def set_defer_value(*args):
            for dv in dvs:
                if not dv.isSet:
                    dv.set(args)
                    break

        listener = PostgresListenerService()
        listener.register("machine", set_defer_value)
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_interface, interface.id, {
                "node": device2
                })
            yield dvs[0].get(timeout=2)
            yield dvs[1].get(timeout=2)
            self.assertItemsEqual([
                ('update', '%s' % parent1.system_id),
                ('update', '%s' % parent2.system_id),
                ], [dvs[0].value, dvs[1].value])
        finally:
            yield listener.stopService()


class TestFabricListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("fabric", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            fabric = yield deferToDatabase(self.create_fabric)
            yield dv.get(timeout=2)
            self.assertEqual(('create', '%s' % fabric.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("fabric", lambda *args: dv.set(args))
        fabric = yield deferToDatabase(self.create_fabric)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_fabric,
                fabric.id,
                {'name': factory.make_name('name')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % fabric.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("fabric", lambda *args: dv.set(args))
        fabric = yield deferToDatabase(self.create_fabric)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_fabric, fabric.id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', '%s' % fabric.id), dv.value)
        finally:
            yield listener.stopService()


class TestVLANListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        fabric = yield deferToDatabase(self.create_fabric)
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("vlan", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            vlan = yield deferToDatabase(self.create_vlan, {'fabric': fabric})
            yield dv.get(timeout=2)
            self.assertEqual(('create', '%s' % vlan.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        fabric = yield deferToDatabase(self.create_fabric)
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("vlan", lambda *args: dv.set(args))
        vlan = yield deferToDatabase(self.create_vlan, {'fabric': fabric})

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_vlan,
                vlan.id,
                {'name': factory.make_name('name')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % vlan.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        fabric = yield deferToDatabase(self.create_fabric)
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("vlan", lambda *args: dv.set(args))
        vlan = yield deferToDatabase(self.create_vlan, {'fabric': fabric})
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_vlan, vlan.id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', '%s' % vlan.id), dv.value)
        finally:
            yield listener.stopService()


class TestSubnetListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            subnet = yield deferToDatabase(self.create_subnet)
            yield dv.get(timeout=2)
            self.assertEqual(('create', '%s' % subnet.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        subnet = yield deferToDatabase(self.create_subnet)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_subnet,
                subnet.id,
                {'name': factory.make_name('name')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % subnet.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        subnet = yield deferToDatabase(self.create_subnet)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_subnet, subnet.id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', '%s' % subnet.id), dv.value)
        finally:
            yield listener.stopService()


class TestSpaceListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("space", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            space = yield deferToDatabase(self.create_space)
            yield dv.get(timeout=2)
            self.assertEqual(('create', '%s' % space.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("space", lambda *args: dv.set(args))
        space = yield deferToDatabase(self.create_space)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_space,
                space.id,
                {'name': factory.make_name('name')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % space.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_websocket_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("space", lambda *args: dv.set(args))
        space = yield deferToDatabase(self.create_space)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_space, space.id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', '%s' % space.id), dv.value)
        finally:
            yield listener.stopService()


class TestNodeNetworkListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_fabric, maasserver_space, maasserver_subnet, and
    maasserver_vlan tables that notifies affected nodes."""

    scenarios = (
        ('machine', {
            'params': {'node_type': NODE_TYPE.MACHINE, 'interface': True},
            'listener': 'machine',
            }),
        ('device', {
            'params': {'node_type': NODE_TYPE.DEVICE, 'interface': True},
            'listener': 'device',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_iface_with_update_on_fabric_update(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id)
        yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})
        fabric = yield deferToDatabase(self.get_interface_fabric, interface.id)

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_fabric,
                fabric.id, {"name": factory.make_name("name")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_iface_with_update_on_vlan_update(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id)
        yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})
        vlan = yield deferToDatabase(self.get_interface_vlan, interface.id)

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_vlan,
                vlan.id, {"name": factory.make_name("name")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_subnet_update(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id)
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})
        subnet = yield deferToDatabase(self.get_ipaddress_subnet, ipaddress.id)

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_subnet,
                subnet.id, {"name": factory.make_name("name")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_space_update(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id)
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})
        space = yield deferToDatabase(self.get_ipaddress_space, ipaddress.id)

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_space, space.id,
                {"name": factory.make_name("name")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_ip_address_update(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id)
        subnet = yield deferToDatabase(self.create_subnet)
        selected_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "interface": interface,
                "subnet": subnet,
                "ip": "",
                })

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress, ipaddress.id,
                {"ip": selected_ip})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestDeviceWithParentNetworkListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_fabric, maasserver_space, maasserver_subnet, and
    maasserver_vlan tables that notifies affected nodes."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_iface_with_update_on_fabric_update(self):
        yield deferToDatabase(register_websocket_triggers)
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True})
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id)
        yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})
        fabric = yield deferToDatabase(self.get_interface_fabric, interface.id)

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_fabric,
                fabric.id, {"name": factory.make_name("name")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_iface_with_update_on_vlan_update(self):
        yield deferToDatabase(register_websocket_triggers)
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True})
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id)
        yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})
        vlan = yield deferToDatabase(self.get_interface_vlan, interface.id)

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_vlan,
                vlan.id, {"name": factory.make_name("name")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_subnet_update(self):
        yield deferToDatabase(register_websocket_triggers)
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True})
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id)
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})
        subnet = yield deferToDatabase(self.get_ipaddress_subnet, ipaddress.id)

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_subnet,
                subnet.id, {"name": factory.make_name("name")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_space_update(self):
        yield deferToDatabase(register_websocket_triggers)
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True})
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id)
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})
        space = yield deferToDatabase(self.get_ipaddress_space, ipaddress.id)

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_space, space.id,
                {"name": factory.make_name("name")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_ip_address_update(self):
        yield deferToDatabase(register_websocket_triggers)
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True})
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id)
        subnet = yield deferToDatabase(self.create_subnet)
        selected_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "interface": interface,
                "subnet": subnet,
                "ip": "",
                })

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress, ipaddress.id,
                {"ip": selected_ip})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestStaticIPAddressSubnetListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_staticipaddress tables that notifies affected subnets."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_update_on_subnet(self):
        yield deferToDatabase(register_websocket_triggers)
        subnet = yield deferToDatabase(self.create_subnet)
        selected_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "subnet": subnet,
                "ip": "",
                })

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress,
                ipaddress.id, {"ip": selected_ip})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % subnet.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_update_on_old_and_new_subnet(self):
        yield deferToDatabase(register_websocket_triggers)
        old_subnet = yield deferToDatabase(self.create_subnet)
        new_subnet = yield deferToDatabase(self.create_subnet)
        selected_ip = factory.pick_ip_in_network(new_subnet.get_ipnetwork())
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "subnet": old_subnet,
                "ip": "",
                })
        dvs = [DeferredValue(), DeferredValue()]

        def set_defer_value(*args):
            for dv in dvs:
                if not dv.isSet:
                    dv.set(args)
                    break

        listener = PostgresListenerService()
        listener.register("subnet", set_defer_value)
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_staticipaddress, ipaddress.id, {
                "ip": selected_ip,
                "subnet": new_subnet,
                })
            yield dvs[0].get(timeout=2)
            yield dvs[1].get(timeout=2)
            self.assertItemsEqual([
                ('update', '%s' % old_subnet.id),
                ('update', '%s' % new_subnet.id),
                ], [dvs[0].value, dvs[1].value])
        finally:
            yield listener.stopService()


class TestMachineBlockDeviceListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_blockdevice, maasserver_physicalblockdevice, and
    maasserver_virtualblockdevice tables that notifies its machine."""

    scenarios = (
        ('machine', {
            'params': {'node_type': NODE_TYPE.MACHINE},
            'listener': 'machine',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_blockdevice, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        blockdevice = yield deferToDatabase(
            self.create_blockdevice, {"node": node})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_blockdevice, blockdevice.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_update(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        blockdevice = yield deferToDatabase(
            self.create_blockdevice, {"node": node})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_blockdevice, blockdevice.id, {
                "size": random.randint(3000 * 1000, 1000 * 1000 * 1000)
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_physicalblockdevice_update(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        blockdevice = yield deferToDatabase(
            self.create_physicalblockdevice, {"node": node})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_physicalblockdevice, blockdevice.id, {
                    "model": factory.make_name("model")
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_virtualblockdevice_update(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        blockdevice = yield deferToDatabase(
            self.create_virtualblockdevice, {"node": node})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_virtualblockdevice, blockdevice.id, {
                    "uuid": factory.make_UUID()
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestMachinePartitionTableListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_partitiontable tables that notifies its machine."""

    scenarios = (
        ('machine', {
            'params': {'node_type': NODE_TYPE.MACHINE},
            'listener': 'machine',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_partitiontable, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partitiontable = yield deferToDatabase(
            self.create_partitiontable, {"node": node})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.delete_partitiontable, partitiontable.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_update(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partitiontable = yield deferToDatabase(
            self.create_partitiontable, {"node": node})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_partitiontable, partitiontable.id, {
                    "size": random.randint(3000 * 1000, 1000 * 1000 * 1000)
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestMachinePartitionListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_partition tables that notifies its machine."""

    scenarios = (
        ('machine', {
            'params': {'node_type': NODE_TYPE.MACHINE},
            'listener': 'machine',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_partition, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_partition, partition.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_update(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            # Only downsize the partition otherwise the test may fail due
            # to the random number being generated is greater than the mock
            # available disk space
            yield deferToDatabase(self.update_partition, partition.id, {
                "size": partition.size - 1,
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestMachineFilesystemListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_filesystem tables that notifies its machine."""

    scenarios = (
        ('machine', {
            'params': {'node_type': NODE_TYPE.MACHINE},
            'listener': 'machine',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_filesystem, {"partition": partition})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node})
        filesystem = yield deferToDatabase(
            self.create_filesystem, {"partition": partition})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_filesystem, filesystem.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_update(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node})
        filesystem = yield deferToDatabase(
            self.create_filesystem, {"partition": partition})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_filesystem, filesystem.id, {
                "size": random.randint(3000 * 1000, 1000 * 1000 * 1000)
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestMachineFilesystemgroupListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_filesystemgroup tables that notifies its machine."""

    scenarios = (
        ('machine', {
            'params': {'node_type': NODE_TYPE.MACHINE, 'with_boot_disk': True},
            'listener': 'machine',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        yield deferToDatabase(self.create_partitiontable, {'node': node})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_filesystemgroup, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        yield deferToDatabase(self.create_partitiontable, {'node': node})
        filesystemgroup = yield deferToDatabase(
            self.create_filesystemgroup, {
                "node": node, "group_type": "raid-5"})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.delete_filesystemgroup, filesystemgroup.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_update(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        yield deferToDatabase(self.create_partitiontable, {'node': node})
        filesystemgroup = yield deferToDatabase(
            self.create_filesystemgroup, {
                "node": node, "group_type": "raid-5"})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_filesystemgroup, filesystemgroup.id, {
                    "size": random.randint(3000 * 1000, 1000 * 1000 * 1000)
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestMachineCachesetListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_cacheset tables that notifies its machine."""

    scenarios = (
        ('machine', {
            'params': {'node_type': NODE_TYPE.MACHINE},
            'listener': 'machine',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_cacheset, {"node": node, "partition": partition})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node})
        cacheset = yield deferToDatabase(
            self.create_cacheset, {"node": node, "partition": partition})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_cacheset, cacheset.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_update(self):
        yield deferToDatabase(register_websocket_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node})
        cacheset = yield deferToDatabase(
            self.create_cacheset, {"node": node, "partition": partition})

        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_cacheset, cacheset.id, {
                "size": random.randint(3000 * 1000, 1000 * 1000 * 1000)
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestUserSSHKeyListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the maasserver_sshkey
    table that notifies its user."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        user = yield deferToDatabase(self.create_user)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_sshkey, {"user": user})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % user.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_websocket_triggers)
        user = yield deferToDatabase(self.create_user)
        sshkey = yield deferToDatabase(self.create_sshkey, {"user": user})

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_sshkey, sshkey.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % user.id), dv.value)
        finally:
            yield listener.stopService()


class TestUserSSLKeyListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the maasserver_sslkey
    table that notifies its user."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_websocket_triggers)
        user = yield deferToDatabase(self.create_user)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_sslkey, {"user": user})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % user.id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_websocket_triggers)
        user = yield deferToDatabase(self.create_user)
        sslkey = yield deferToDatabase(self.create_sslkey, {"user": user})

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_sslkey, sslkey.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % user.id), dv.value)
        finally:
            yield listener.stopService()
