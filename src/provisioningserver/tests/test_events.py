# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test event catalog."""


import random
from unittest.mock import sentinel

from twisted.internet.defer import fail, inlineCallbacks, succeed

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.events import (
    EVENT_DETAILS,
    EVENT_TYPES,
    EventDetail,
    nodeEventHub,
    NodeEventHub,
    send_node_event,
    send_node_event_ip_address,
    send_node_event_mac_address,
    send_rack_event,
)
from provisioningserver.rpc import clusterservice, region
from provisioningserver.rpc.exceptions import NoSuchEventType, NoSuchNode
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from provisioningserver.utils.enum import map_enum
from provisioningserver.utils.testing import MAASIDFixture

TIMEOUT = get_testing_timeout()


class TestEvents(MAASTestCase):
    def test_every_event_has_details(self):
        all_events = map_enum(EVENT_TYPES)
        self.assertEqual(set(all_events.values()), EVENT_DETAILS.keys())
        for detail in EVENT_DETAILS.values():
            self.assertIsInstance(detail, EventDetail)


class TestSendEventNode(MAASTestCase):
    """Tests for `send_node_event`."""

    def test_calls_singleton_hub_logByID_directly(self):
        self.patch(nodeEventHub, "logByID").return_value = sentinel.d
        result = send_node_event(
            sentinel.event_type,
            sentinel.system_id,
            sentinel.hostname,
            sentinel.description,
        )
        self.assertIs(result, sentinel.d)
        nodeEventHub.logByID.assert_called_once_with(
            sentinel.event_type, sentinel.system_id, sentinel.description
        )


class TestSendEventNodeMACAddress(MAASTestCase):
    """Tests for `send_node_event_mac_address`."""

    def test_calls_singleton_hub_logByMAC_directly(self):
        self.patch(nodeEventHub, "logByMAC").return_value = sentinel.d
        result = send_node_event_mac_address(
            sentinel.event_type, sentinel.mac_address, sentinel.description
        )
        self.assertIs(result, sentinel.d)
        nodeEventHub.logByMAC.assert_called_once_with(
            sentinel.event_type, sentinel.mac_address, sentinel.description
        )


class TestSendEventNodeIPAddress(MAASTestCase):
    """Tests for `send_node_event_mac_address`."""

    def test_calls_singleton_hub_logByIP_directly(self):
        self.patch(nodeEventHub, "logByIP").return_value = sentinel.d
        result = send_node_event_ip_address(
            sentinel.event_type, sentinel.ip_address, sentinel.description
        )
        self.assertIs(result, sentinel.d)
        nodeEventHub.logByIP.assert_called_once_with(
            sentinel.event_type, sentinel.ip_address, sentinel.description
        )


class TestSendRackEvent(MAASTestCase):
    """Tests for `send_rack_event`."""

    def test_calls_singleton_hub_logByID_directly(self):
        self.patch(nodeEventHub, "logByID").return_value = sentinel.d
        rack_system_id = factory.make_name("system_id")
        self.useFixture(MAASIDFixture(rack_system_id))
        result = send_rack_event(sentinel.event_type, sentinel.description)
        self.assertIs(result, sentinel.d)
        nodeEventHub.logByID.assert_called_once_with(
            sentinel.event_type, rack_system_id, sentinel.description
        )


class TestNodeEventHubLogByID(MAASTestCase):
    """Tests for `NodeEventHub.logByID`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

    def patch_rpc_methods(self, side_effect=None):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.SendEvent, region.RegisterEventType
        )
        protocol.SendEvent.side_effect = side_effect
        return protocol, connecting

    @inlineCallbacks
    def test_event_is_sent_to_region(self):
        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        system_id = factory.make_name("system_id")
        description = factory.make_name("description")
        event_name = random.choice(list(map_enum(EVENT_TYPES)))

        yield NodeEventHub().logByID(event_name, system_id, description)

        protocol.SendEvent.assert_called_once_with(
            protocol,
            type_name=event_name,
            system_id=system_id,
            description=description,
        )

    @inlineCallbacks
    def test_event_type_is_registered_on_first_call_only(self):
        protocol, connecting = self.patch_rpc_methods(
            side_effect=[succeed({}), succeed({})]
        )
        self.addCleanup((yield connecting))

        system_id = factory.make_name("system_id")
        description = factory.make_name("description")
        event_name = random.choice(list(map_enum(EVENT_TYPES)))
        event_detail = EVENT_DETAILS[event_name]
        event_hub = NodeEventHub()

        # On the first call, the event type is registered before the log is
        # sent to the region.
        yield event_hub.logByID(event_name, system_id, description)
        protocol.RegisterEventType.assert_called_once_with(
            protocol,
            name=event_name,
            description=event_detail.description,
            level=event_detail.level,
        )
        protocol.SendEvent.assert_called_once()

        # Reset RPC call handlers.
        protocol.RegisterEventType.reset_mock()
        protocol.SendEvent.reset_mock()

        # On the second call, the event type is known to be registered, so the
        # log is sent to the region immediately.
        yield event_hub.logByID(event_name, system_id, description)
        protocol.RegisterEventType.assert_not_called()
        protocol.SendEvent.assert_called_once()

    @inlineCallbacks
    def test_updates_cache_if_event_type_not_found(self):
        protocol, connecting = self.patch_rpc_methods(
            side_effect=[succeed({}), fail(NoSuchEventType.from_name("foo"))]
        )
        self.addCleanup((yield connecting))

        system_id = factory.make_name("system_id")
        description = factory.make_name("description")
        event_name = random.choice(list(map_enum(EVENT_TYPES)))
        event_hub = NodeEventHub()

        # Fine the first time.
        yield event_hub.logByID(event_name, system_id, description)
        # The cache has been populated with the event name.
        self.assertEqual({event_name}, event_hub._types_registered)
        # Second time it crashes.
        with self.assertRaisesRegex(
            NoSuchEventType, r"Event type with name=foo could not be found\."
        ):
            yield event_hub.logByID(event_name, system_id, description)
        # The event has been removed from the cache.
        self.assertEqual(event_hub._types_registered, set())


class TestSendEventMACAddress(MAASTestCase):
    """Tests for `NodeEventHub.logByMAC`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

    def patch_rpc_methods(self, side_effect=None):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.SendEventMACAddress, region.RegisterEventType
        )
        protocol.SendEventMACAddress.side_effect = side_effect
        return protocol, connecting

    @inlineCallbacks
    def test_event_is_sent_to_region(self):
        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        mac_address = factory.make_mac_address()
        description = factory.make_name("description")
        event_name = random.choice(list(map_enum(EVENT_TYPES)))

        yield NodeEventHub().logByMAC(event_name, mac_address, description)

        protocol.SendEventMACAddress.assert_called_once_with(
            protocol,
            type_name=event_name,
            mac_address=mac_address,
            description=description,
        )

    @inlineCallbacks
    def test_failure_is_suppressed_if_node_not_found(self):
        protocol, connecting = self.patch_rpc_methods(
            side_effect=[fail(NoSuchNode())]
        )
        self.addCleanup((yield connecting))

        mac_address = factory.make_mac_address()
        description = factory.make_name("description")
        event_name = random.choice(list(map_enum(EVENT_TYPES)))

        yield NodeEventHub().logByMAC(event_name, mac_address, description)

        protocol.SendEventMACAddress.assert_called_once_with(
            protocol,
            type_name=event_name,
            mac_address=mac_address,
            description=description,
        )

    @inlineCallbacks
    def test_event_type_is_registered_on_first_call_only(self):
        protocol, connecting = self.patch_rpc_methods(side_effect=[{}, {}])
        self.addCleanup((yield connecting))

        mac_address = factory.make_mac_address()
        description = factory.make_name("description")
        event_name = random.choice(list(map_enum(EVENT_TYPES)))
        event_detail = EVENT_DETAILS[event_name]
        event_hub = NodeEventHub()

        # On the first call, the event type is registered before the log is
        # sent to the region.
        yield event_hub.logByMAC(event_name, mac_address, description)
        protocol.RegisterEventType.assert_called_once_with(
            protocol,
            name=event_name,
            description=event_detail.description,
            level=event_detail.level,
        )
        protocol.SendEventMACAddress.assert_called_once()

        # Reset RPC call handlers.
        protocol.RegisterEventType.reset_mock()
        protocol.SendEventMACAddress.reset_mock()

        # On the second call, the event type is known to be registered, so the
        # log is sent to the region immediately.
        yield event_hub.logByMAC(event_name, mac_address, description)
        protocol.RegisterEventType.assert_not_called()
        protocol.SendEventMACAddress.assert_called_once()

    @inlineCallbacks
    def test_updates_cache_if_event_type_not_found(self):
        protocol, connecting = self.patch_rpc_methods(
            side_effect=[succeed({}), fail(NoSuchEventType.from_name("foo"))]
        )
        self.addCleanup((yield connecting))

        mac_address = factory.make_mac_address()
        description = factory.make_name("description")
        event_name = random.choice(list(map_enum(EVENT_TYPES)))
        event_hub = NodeEventHub()

        # Fine the first time.
        yield event_hub.logByMAC(event_name, mac_address, description)
        # The cache has been populated with the event name.
        self.assertEqual({event_name}, event_hub._types_registered)
        # Second time it crashes.
        with self.assertRaisesRegex(
            NoSuchEventType, r"Event type with name=foo could not be found\."
        ):
            yield event_hub.logByMAC(event_name, mac_address, description)
        # The event has been removed from the cache.
        self.assertEqual(event_hub._types_registered, set())


class TestSendEventIPAddress(MAASTestCase):
    """Tests for `NodeEventHub.logByIP`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

    def patch_rpc_methods(self, side_effect=None):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.SendEventIPAddress, region.RegisterEventType
        )
        protocol.SendEventIPAddress.side_effect = side_effect
        return protocol, connecting

    @inlineCallbacks
    def test_event_is_sent_to_region(self):
        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        ip_address = factory.make_ip_address()
        description = factory.make_name("description")
        event_name = random.choice(list(map_enum(EVENT_TYPES)))

        yield NodeEventHub().logByIP(event_name, ip_address, description)

        protocol.SendEventIPAddress.assert_called_once_with(
            protocol,
            type_name=event_name,
            ip_address=ip_address,
            description=description,
        )

    @inlineCallbacks
    def test_failure_is_suppressed_if_node_not_found(self):
        protocol, connecting = self.patch_rpc_methods(
            side_effect=[fail(NoSuchNode())]
        )
        self.addCleanup((yield connecting))

        ip_address = factory.make_ip_address()
        description = factory.make_name("description")
        event_name = random.choice(list(map_enum(EVENT_TYPES)))

        yield NodeEventHub().logByIP(event_name, ip_address, description)

        protocol.SendEventIPAddress.assert_called_once_with(
            protocol,
            type_name=event_name,
            ip_address=ip_address,
            description=description,
        )

    @inlineCallbacks
    def test_event_type_is_registered_on_first_call_only(self):
        protocol, connecting = self.patch_rpc_methods(side_effect=[{}, {}])
        self.addCleanup((yield connecting))

        ip_address = factory.make_ip_address()
        description = factory.make_name("description")
        event_name = random.choice(list(map_enum(EVENT_TYPES)))
        event_detail = EVENT_DETAILS[event_name]
        event_hub = NodeEventHub()

        # On the first call, the event type is registered before the log is
        # sent to the region.
        yield event_hub.logByIP(event_name, ip_address, description)
        protocol.RegisterEventType.assert_called_once_with(
            protocol,
            name=event_name,
            description=event_detail.description,
            level=event_detail.level,
        )
        protocol.SendEventIPAddress.assert_called_once_with(
            protocol,
            ip_address=ip_address,
            type_name=event_name,
            description=description,
        )

        # Reset RPC call handlers.
        protocol.RegisterEventType.reset_mock()
        protocol.SendEventIPAddress.reset_mock()

        # On the second call, the event type is known to be registered, so the
        # log is sent to the region immediately.
        yield event_hub.logByIP(event_name, ip_address, description)
        protocol.RegisterEventType.assert_not_called()
        protocol.SendEventIPAddress.assert_called_once()

    @inlineCallbacks
    def test_updates_cache_if_event_type_not_found(self):
        protocol, connecting = self.patch_rpc_methods(
            side_effect=[succeed({}), fail(NoSuchEventType.from_name("foo"))]
        )
        self.addCleanup((yield connecting))

        ip_address = factory.make_ip_address()
        description = factory.make_name("description")
        event_name = random.choice(list(map_enum(EVENT_TYPES)))
        event_hub = NodeEventHub()

        # Fine the first time.
        yield event_hub.logByIP(event_name, ip_address, description)
        # The cache has been populated with the event name.
        self.assertEqual({event_name}, event_hub._types_registered)
        # Second time it crashes.
        with self.assertRaisesRegex(
            NoSuchEventType, r"Event type with name=foo could not be found\."
        ):
            yield event_hub.logByIP(event_name, ip_address, description)
        # The event has been removed from the cache.
        self.assertEqual(event_hub._types_registered, set())
