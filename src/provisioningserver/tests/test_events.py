# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test event catalog."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    ]

import random

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnce,
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from mock import (
    ANY,
    sentinel,
)
from provisioningserver.events import (
    EVENT_DETAILS,
    EVENT_TYPES,
    EventDetail,
    NodeEventHub,
    nodeEventHub,
    send_event_node,
    send_event_node_mac_address,
)
from provisioningserver.rpc import region
from provisioningserver.rpc.exceptions import (
    NoSuchEventType,
    NoSuchNode,
)
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from provisioningserver.utils.enum import map_enum
from testtools import ExpectedException
from testtools.matchers import (
    AllMatch,
    Equals,
    HasLength,
    Is,
    IsInstance,
)
from twisted.internet.defer import (
    fail,
    inlineCallbacks,
    succeed,
)


class TestEvents(MAASTestCase):

    def test_every_event_has_details(self):
        all_events = map_enum(EVENT_TYPES)
        self.assertItemsEqual(all_events.values(), EVENT_DETAILS)
        self.assertThat(
            EVENT_DETAILS.values(), AllMatch(IsInstance(EventDetail)))


class TestSendEventNode(MAASTestCase):
    """Tests for `send_event_node`."""

    def test__calls_singleton_hub_logByID_directly(self):
        self.patch_autospec(nodeEventHub, "logByID").return_value = sentinel.d
        result = send_event_node(
            sentinel.event_type, sentinel.system_id, sentinel.hostname,
            sentinel.description)
        self.assertThat(result, Is(sentinel.d))
        self.assertThat(nodeEventHub.logByID, MockCalledOnceWith(
            sentinel.event_type, sentinel.system_id, sentinel.description))


class TestSendEventNodeMACAddress(MAASTestCase):
    """Tests for `send_event_node_mac_address`."""

    def test__calls_singleton_hub_logByMAC_directly(self):
        self.patch_autospec(nodeEventHub, "logByMAC").return_value = sentinel.d
        result = send_event_node_mac_address(
            sentinel.event_type, sentinel.mac_address, sentinel.description)
        self.assertThat(result, Is(sentinel.d))
        self.assertThat(nodeEventHub.logByMAC, MockCalledOnceWith(
            sentinel.event_type, sentinel.mac_address, sentinel.description))


class TestNodeEventHubLogByID(MAASTestCase):
    """Tests for `NodeEventHub.logByID`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def patch_rpc_methods(self, side_effect=None):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.SendEvent, region.RegisterEventType)
        protocol.SendEvent.side_effect = side_effect
        return protocol, connecting

    @inlineCallbacks
    def test__event_is_sent_to_region(self):
        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        system_id = factory.make_name('system_id')
        description = factory.make_name('description')
        event_name = random.choice(map_enum(EVENT_TYPES).keys())

        yield NodeEventHub().logByID(event_name, system_id, description)

        self.assertThat(
            protocol.SendEvent, MockCalledOnceWith(
                ANY, type_name=event_name, system_id=system_id,
                description=description))

    @inlineCallbacks
    def test__event_type_is_registered_on_first_call_only(self):
        protocol, connecting = self.patch_rpc_methods(
            side_effect=[succeed({}), succeed({})])
        self.addCleanup((yield connecting))

        system_id = factory.make_name('system_id')
        description = factory.make_name('description')
        event_name = random.choice(map_enum(EVENT_TYPES).keys())
        event_detail = EVENT_DETAILS[event_name]
        event_hub = NodeEventHub()

        # On the first call, the event type is registered before the log is
        # sent to the region.
        yield event_hub.logByID(event_name, system_id, description)
        self.assertThat(
            protocol.RegisterEventType, MockCalledOnceWith(
                ANY, name=event_name, description=event_detail.description,
                level=event_detail.level))
        self.assertThat(protocol.SendEvent, MockCalledOnce())

        # Reset RPC call handlers.
        protocol.RegisterEventType.reset_mock()
        protocol.SendEvent.reset_mock()

        # On the second call, the event type is known to be registered, so the
        # log is sent to the region immediately.
        yield event_hub.logByID(event_name, system_id, description)
        self.assertThat(protocol.RegisterEventType, MockNotCalled())
        self.assertThat(protocol.SendEvent, MockCalledOnce())

    @inlineCallbacks
    def test__updates_cache_if_event_type_not_found(self):
        protocol, connecting = self.patch_rpc_methods(
            side_effect=[succeed({}), fail(NoSuchEventType())])
        self.addCleanup((yield connecting))

        system_id = factory.make_name('system_id')
        description = factory.make_name('description')
        event_name = random.choice(map_enum(EVENT_TYPES).keys())
        event_hub = NodeEventHub()

        # Fine the first time.
        yield event_hub.logByID(event_name, system_id, description)
        # The cache has been populated with the event name.
        self.assertThat(event_hub._types_registered, Equals({event_name}))
        # Second time it crashes.
        with ExpectedException(NoSuchEventType):
            yield event_hub.logByID(event_name, system_id, description)
        # The event has been removed from the cache.
        self.assertThat(event_hub._types_registered, HasLength(0))


class TestSendEventMACAddress(MAASTestCase):
    """Tests for `NodeEventHub.logByMAC`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def patch_rpc_methods(self, side_effect=None):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.SendEventMACAddress, region.RegisterEventType)
        protocol.SendEventMACAddress.side_effect = side_effect
        return protocol, connecting

    @inlineCallbacks
    def test__event_is_sent_to_region(self):
        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        mac_address = factory.make_mac_address()
        description = factory.make_name('description')
        event_name = random.choice(map_enum(EVENT_TYPES).keys())

        yield NodeEventHub().logByMAC(event_name, mac_address, description)

        self.assertThat(
            protocol.SendEventMACAddress, MockCalledOnceWith(
                ANY, type_name=event_name, mac_address=mac_address,
                description=description))

    @inlineCallbacks
    def test__failure_is_suppressed_if_node_not_found(self):
        protocol, connecting = self.patch_rpc_methods(
            side_effect=[fail(NoSuchNode())])
        self.addCleanup((yield connecting))

        mac_address = factory.make_mac_address()
        description = factory.make_name('description')
        event_name = random.choice(map_enum(EVENT_TYPES).keys())

        yield NodeEventHub().logByMAC(event_name, mac_address, description)

        self.assertThat(
            protocol.SendEventMACAddress, MockCalledOnceWith(
                ANY, type_name=event_name, mac_address=mac_address,
                description=description))

    @inlineCallbacks
    def test__event_type_is_registered_on_first_call_only(self):
        protocol, connecting = self.patch_rpc_methods(side_effect=[{}, {}])
        self.addCleanup((yield connecting))

        mac_address = factory.make_mac_address()
        description = factory.make_name('description')
        event_name = random.choice(map_enum(EVENT_TYPES).keys())
        event_detail = EVENT_DETAILS[event_name]
        event_hub = NodeEventHub()

        # On the first call, the event type is registered before the log is
        # sent to the region.
        yield event_hub.logByMAC(event_name, mac_address, description)
        self.assertThat(
            protocol.RegisterEventType, MockCalledOnceWith(
                ANY, name=event_name, description=event_detail.description,
                level=event_detail.level))
        self.assertThat(protocol.SendEventMACAddress, MockCalledOnce())

        # Reset RPC call handlers.
        protocol.RegisterEventType.reset_mock()
        protocol.SendEventMACAddress.reset_mock()

        # On the second call, the event type is known to be registered, so the
        # log is sent to the region immediately.
        yield event_hub.logByMAC(event_name, mac_address, description)
        self.assertThat(protocol.RegisterEventType, MockNotCalled())
        self.assertThat(protocol.SendEventMACAddress, MockCalledOnce())

    @inlineCallbacks
    def test__updates_cache_if_event_type_not_found(self):
        protocol, connecting = self.patch_rpc_methods(
            side_effect=[succeed({}), fail(NoSuchEventType())])
        self.addCleanup((yield connecting))

        mac_address = factory.make_mac_address()
        description = factory.make_name('description')
        event_name = random.choice(map_enum(EVENT_TYPES).keys())
        event_hub = NodeEventHub()

        # Fine the first time.
        yield event_hub.logByMAC(event_name, mac_address, description)
        # The cache has been populated with the event name.
        self.assertThat(event_hub._types_registered, Equals({event_name}))
        # Second time it crashes.
        with ExpectedException(NoSuchEventType):
            yield event_hub.logByMAC(event_name, mac_address, description)
        # The event has been removed from the cache.
        self.assertThat(event_hub._types_registered, HasLength(0))
