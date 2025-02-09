# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for event-related helpers."""

from unittest.mock import MagicMock, sentinel

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.events import Event, EventGroup


class TestEvent(MAASTestCase):
    """Tests for `Event`."""

    def test_registerHandler(self):
        event = Event()
        event.registerHandler(sentinel.handler)
        self.assertEqual({sentinel.handler}, event.handlers)

    def test_registerHandler_during_fire(self):
        event = Event()
        event.registerHandler(event.registerHandler)
        event.fire(sentinel.otherHandler)
        self.assertEqual(
            {event.registerHandler, sentinel.otherHandler}, event.handlers
        )

    def test_unregisterHandler(self):
        event = Event()
        event.registerHandler(sentinel.handler)
        event.unregisterHandler(sentinel.handler)
        self.assertEqual(set(), event.handlers)

    def test_unregisterHandler_during_fire(self):
        event = Event()
        event.registerHandler(event.unregisterHandler)
        event.fire(event.unregisterHandler)
        self.assertEqual(set(), event.handlers)

    def test_fire_calls_all_handlers(self):
        event = Event()
        handler_one = MagicMock()
        handler_two = MagicMock()
        event.registerHandler(handler_one)
        event.registerHandler(handler_two)
        args = [factory.make_name("arg") for _ in range(3)]
        kwargs = {
            factory.make_name("key"): factory.make_name("value")
            for _ in range(3)
        }
        event.fire(*args, **kwargs)
        handler_one.mock_called_once_with(*args, **kwargs)
        handler_two.mock_called_once_with(*args, **kwargs)


class TestEventGroup(MAASTestCase):
    """Tests for `EventGroup`."""

    def test_makes_events_as_properties(self):
        events = [factory.make_name("event") for _ in range(3)]
        group = EventGroup(*events)
        for event in events:
            self.assertIsInstance(getattr(group, event), Event)
