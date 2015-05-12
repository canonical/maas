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
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from mock import (
    ANY,
    call,
)
from provisioningserver.events import (
    EVENT_DETAILS,
    EVENT_TYPES,
    EventDetail,
    send_event_node,
    send_event_node_mac_address,
)
from provisioningserver.rpc import region
from provisioningserver.rpc.exceptions import NoSuchEventType
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from provisioningserver.utils.enum import map_enum
from testtools.matchers import (
    AllMatch,
    IsInstance,
)
from twisted.internet.defer import inlineCallbacks


class TestEvents(MAASTestCase):

    def test_every_event_has_details(self):
        all_events = map_enum(EVENT_TYPES)
        self.assertItemsEqual(all_events.values(), EVENT_DETAILS)
        self.assertThat(
            EVENT_DETAILS.values(), AllMatch(IsInstance(EventDetail)))


class TestSendEvent(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def patch_rpc_methods(self, side_effect=None):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.SendEvent, region.RegisterEventType)
        protocol.SendEvent.side_effect = side_effect
        return protocol, connecting

    @inlineCallbacks
    def test_send_event_node_stores_event(self):
        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        description = factory.make_name('description')
        event_name = random.choice(map_enum(EVENT_TYPES).keys())

        yield send_event_node(
            event_name, system_id, hostname, description)
        self.assertEquals(
            [call(
                ANY, type_name=event_name, system_id=system_id,
                description=description,
            )],
            protocol.SendEvent.call_args_list,
        )

    @inlineCallbacks
    def test_send_event_node_registers_event_type(self):
        protocol, connecting = self.patch_rpc_methods(
            side_effect=[NoSuchEventType, {}])
        self.addCleanup((yield connecting))

        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        description = factory.make_name('description')
        event_name = random.choice(map_enum(EVENT_TYPES).keys())

        yield send_event_node(event_name, system_id, hostname, description)
        event_detail = EVENT_DETAILS[event_name]
        self.assertEquals(
            [
                call(
                    ANY, type_name=event_name, system_id=system_id,
                    description=description),
                call(
                    ANY, type_name=event_name, system_id=system_id,
                    description=description),
            ],
            protocol.SendEvent.call_args_list,
        )
        self.assertEquals(
            [
                call(
                    ANY, name=event_name,
                    description=event_detail.description,
                    level=event_detail.level),
            ],
            protocol.RegisterEventType.call_args_list,
        )


class TestSendEventMACAddress(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def patch_rpc_methods(self, side_effect=None):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.SendEventMACAddress, region.RegisterEventType)
        protocol.SendEventMACAddress.side_effect = side_effect
        return protocol, connecting

    @inlineCallbacks
    def test_send_event_node_mac_address_stores_event(self):
        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        mac_address = factory.make_mac_address()
        description = factory.make_name('description')
        event_name = random.choice(map_enum(EVENT_TYPES).keys())

        yield send_event_node_mac_address(
            event_name, mac_address, description)
        self.assertEquals(
            [call(
                ANY, type_name=event_name, mac_address=mac_address,
                description=description,
            )],
            protocol.SendEventMACAddress.call_args_list,
        )

    @inlineCallbacks
    def test_send_event_node_mac_address_registers_event_type(self):
        protocol, connecting = self.patch_rpc_methods(
            side_effect=[NoSuchEventType, {}])
        self.addCleanup((yield connecting))

        mac_address = factory.make_mac_address()
        description = factory.make_name('description')
        event_name = random.choice(map_enum(EVENT_TYPES).keys())

        yield send_event_node_mac_address(
            event_name, mac_address, description)
        event_detail = EVENT_DETAILS[event_name]
        self.assertEquals(
            [
                call(
                    ANY, type_name=event_name, mac_address=mac_address,
                    description=description),
                call(
                    ANY, type_name=event_name, mac_address=mac_address,
                    description=description),
            ],
            protocol.SendEventMACAddress.call_args_list,
        )
        self.assertEquals(
            [
                call(
                    ANY, name=event_name,
                    description=event_detail.description,
                    level=event_detail.level),
            ],
            protocol.RegisterEventType.call_args_list,
        )
