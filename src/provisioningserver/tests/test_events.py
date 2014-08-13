# Copyright 2014 Canonical Ltd.  This software is licensed under the
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
from maastesting.testcase import MAASTestCase
from mock import (
    ANY,
    call,
    )
from provisioningserver.events import (
    EVENT_DETAILS,
    EVENT_TYPES,
    EventDetail,
    send_event_node,
    )
from provisioningserver.rpc import region
from provisioningserver.rpc.exceptions import NoSuchEventType
from provisioningserver.rpc.testing import MockClusterToRegionRPCFixture
from provisioningserver.utils.enum import map_enum
from testtools.deferredruntest import AsynchronousDeferredRunTest
from testtools.matchers import (
    AllMatch,
    IsInstance,
    )


class TestEvents(MAASTestCase):

    def test_every_event_has_details(self):
        all_events = map_enum(EVENT_TYPES)
        self.assertItemsEqual(all_events.values(), EVENT_DETAILS)
        self.assertThat(
            EVENT_DETAILS.values(), AllMatch(IsInstance(EventDetail)))


class TestSendEvent(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def patch_rpc_methods(self, side_effect=None):
        fixture = self.useFixture(MockClusterToRegionRPCFixture())
        protocol, io = fixture.makeEventLoop(
            region.SendEvent, region.RegisterEventType)
        protocol.SendEvent.side_effect = side_effect
        return protocol, io

    def test_send_node_event_stores_event(self):
        protocol, io = self.patch_rpc_methods()
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        description = factory.make_name('description')
        event_name = random.choice(map_enum(EVENT_TYPES).keys())

        d = send_event_node(
            event_name, system_id, hostname, description)
        io.flush()
        self.assertEquals(
            [call(
                ANY, type_name=event_name, system_id=system_id,
                description=description,
            )],
            protocol.SendEvent.call_args_list,
        )
        return d

    def test_send_node_event_registers_event_type(self):
        protocol, io = self.patch_rpc_methods(
            side_effect=[NoSuchEventType, {}])

        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        description = factory.make_name('description')
        event_name = random.choice(map_enum(EVENT_TYPES).keys())

        d = send_event_node(event_name, system_id, hostname, description)
        io.flush()
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
        return d
