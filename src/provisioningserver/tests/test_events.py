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
    call,
    Mock,
    )
from provisioningserver.events import (
    EVENT_DETAILS,
    EVENT_TYPES,
    EventDetail,
    send_event_node,
    )
from provisioningserver.rpc.exceptions import NoSuchEventType
from provisioningserver.rpc.region import (
    RegisterEventType,
    SendEvent,
    )
from provisioningserver.utils import map_enum
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

    def test_send_node_event_stores_event(self):
        client = Mock()
        system_id = factory.make_name('system_id')
        description = factory.make_name('description')
        event_name = random.choice(map_enum(EVENT_TYPES).keys())

        send_event_node(client, event_name, system_id, description)
        self.assertEquals(
            [call(
                SendEvent, type_name=event_name, system_id=system_id,
                description=description,
            )],
            client.call_args_list,
        )

    def test_send_node_event_registers_event_type(self):
        client = Mock(side_effect=[NoSuchEventType, None, None])
        system_id = factory.make_name('system_id')
        description = factory.make_name('description')
        event_name = random.choice(map_enum(EVENT_TYPES).keys())

        send_event_node(client, event_name, system_id, description)
        event_detail = EVENT_DETAILS[event_name]
        self.assertEquals(
            [
                call(
                    SendEvent, type_name=event_name, system_id=system_id,
                    description=description),
                call(
                    RegisterEventType, name=event_name,
                    description=event_detail.description,
                    level=event_detail.level),
                call(
                    SendEvent, type_name=event_name, system_id=system_id,
                    description=description),
            ],
            client.call_args_list,
        )
