# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for event-related helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import (
    MagicMock,
    sentinel,
)
from provisioningserver.utils.events import (
    Event,
    EventGroup,
)
from testtools.matchers import IsInstance


class TestEvent(MAASTestCase):
    """Tests for `Event`."""

    def test_registerHandler(self):
        event = Event()
        event.registerHandler(sentinel.handler)
        self.assertItemsEqual([sentinel.handler], event.handlers)

    def test_unregisterHandler(self):
        event = Event()
        event.registerHandler(sentinel.handler)
        event.unregisterHandler(sentinel.handler)
        self.assertItemsEqual([], event.handlers)

    def test_fire_calls_all_handlers(self):
        event = Event()
        handler_one = MagicMock()
        handler_two = MagicMock()
        event.registerHandler(handler_one)
        event.registerHandler(handler_two)
        args = [
            factory.make_name("arg")
            for _ in range(3)
        ]
        kwargs = {
            factory.make_name("key"): factory.make_name("value")
            for _ in range(3)
        }
        event.fire(*args, **kwargs)
        self.assertThat(handler_one, MockCalledOnceWith(*args, **kwargs))
        self.assertThat(handler_two, MockCalledOnceWith(*args, **kwargs))


class TestEventGroup(MAASTestCase):
    """Tests for `EventGroup`."""

    def test_makes_events_as_properties(self):
        events = [
            factory.make_name("event")
            for _ in range(3)
        ]
        group = EventGroup(*events)
        for event in events:
            self.expectThat(getattr(group, event), IsInstance(Event))
