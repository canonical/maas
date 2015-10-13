# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.event`"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import datetime
import random

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import (
    HandlerDoesNotExistError,
    HandlerPKError,
)
from maasserver.websockets.handlers.event import (
    dehydrate_event_type_level,
    EventHandler,
)
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime
from maastesting.matchers import MockCalledOnceWith
from mock import sentinel
from testtools.matchers import (
    Equals,
    Is,
)


class TestEventHandler(MAASServerTestCase):

    def dehydrate_event(self, event):
        data = {
            "id": event.id,
            "node_id": event.node.id,
            "action": event.action,
            "description": event.description,
            "type": {
                "level": dehydrate_event_type_level(event.type.level),
                "name": event.type.name,
                "description": event.type.description,
                },
            "updated": dehydrate_datetime(event.updated),
            "created": dehydrate_datetime(event.created),
            }
        return data

    def dehydrate_events(self, events):
        return [
            self.dehydrate_event(event)
            for event in events
            ]

    def make_event_in_the_past(self, node, days_old):
        event = factory.make_Event(node=node)
        event.created -= datetime.timedelta(days_old)
        event.save()
        return event

    def test_list_raises_error_if_missing_node_id(self):
        user = factory.make_User()
        handler = EventHandler(user, {})
        self.assertRaises(HandlerPKError, handler.list, {})

    def test_list_raises_error_if_node_doesnt_exist(self):
        user = factory.make_User()
        handler = EventHandler(user, {})
        node = factory.make_Node()
        node.delete()
        self.assertRaises(
            HandlerDoesNotExistError, handler.list, {"node_id": node.id})

    def test_list_places_node_id_in_cache(self):
        user = factory.make_User()
        cache = {}
        handler = EventHandler(user, cache)
        node = factory.make_Node()
        handler.list({"node_id": node.id})
        self.assertEquals([node.id], cache["node_ids"])

    def test_list_only_returns_events_for_node(self):
        user = factory.make_User()
        handler = EventHandler(user, {})
        node = factory.make_Node()
        events = [
            factory.make_Event(node=node)
            for _ in range(3)
            ]
        # Other events.
        for _ in range(3):
            factory.make_Event()
        self.assertItemsEqual(
            self.dehydrate_events(events),
            handler.list({"node_id": node.id}))

    def test_list_returns_newest_event_first(self):
        user = factory.make_User()
        handler = EventHandler(user, {})
        node = factory.make_Node()
        events = [
            factory.make_Event(node=node)
            for _ in range(3)
            ]
        # Other events.
        for _ in range(3):
            factory.make_Event()
        self.assertEquals(
            self.dehydrate_events(reversed(events)),
            handler.list({"node_id": node.id}))

    def test_list_default_max_days_of_30(self):
        user = factory.make_User()
        handler = EventHandler(user, {})
        node = factory.make_Node()
        events = [
            factory.make_Event(node=node)
            for _ in range(3)
            ]
        # Event older than 30 days.
        self.make_event_in_the_past(node, 31)
        self.assertItemsEqual(
            self.dehydrate_events(events),
            handler.list({"node_id": node.id}))

    def test_list_uses_max_days(self):
        user = factory.make_User()
        handler = EventHandler(user, {})
        node = factory.make_Node()
        maxdays = random.randint(3, 50)
        events = [
            self.make_event_in_the_past(node, maxdays - 1)
            for _ in range(3)
            ]
        for _ in range(3):
            self.make_event_in_the_past(node, maxdays + 1)
        self.assertItemsEqual(
            self.dehydrate_events(events),
            handler.list({"node_id": node.id, "max_days": maxdays}))

    def test_list_start(self):
        user = factory.make_User()
        handler = EventHandler(user, {})
        node = factory.make_Node()
        events = list(reversed([
            factory.make_Event(node=node)
            for _ in range(6)
            ]))
        expected_output = self.dehydrate_events(events[3:])
        self.assertItemsEqual(
            expected_output,
            handler.list({"node_id": node.id, "start": events[2].id}))

    def test_list_limit(self):
        user = factory.make_User()
        handler = EventHandler(user, {})
        node = factory.make_Node()
        events = list(reversed([
            factory.make_Event(node=node)
            for _ in range(6)
            ]))
        expected_output = self.dehydrate_events(events[:3])
        self.assertItemsEqual(
            expected_output,
            handler.list({"node_id": node.id, "limit": 3}))

    def test_list_start_and_limit(self):
        user = factory.make_User()
        handler = EventHandler(user, {})
        node = factory.make_Node()
        events = list(reversed([
            factory.make_Event(node=node)
            for _ in range(9)
            ]))
        expected_output = self.dehydrate_events(events[3:6])
        self.assertItemsEqual(
            expected_output,
            handler.list(
                {"node_id": node.id, "start": events[2].id, "limit": 3}))

    def test_clear_raises_error_if_missing_node_id(self):
        user = factory.make_User()
        handler = EventHandler(user, {})
        self.assertRaises(HandlerPKError, handler.clear, {})

    def test_clear_raises_error_if_node_id_doesnt_exist(self):
        user = factory.make_User()
        handler = EventHandler(user, {})
        node = factory.make_Node()
        node.delete()
        self.assertRaises(
            HandlerDoesNotExistError, handler.clear, {"node_id": node.id})

    def test_clear_removes_node_id_from_cache(self):
        user = factory.make_User()
        handler = EventHandler(user, {})
        node = factory.make_Node()
        handler.cache["node_ids"].append(node.id)
        self.expectThat(handler.clear({"node_id": node.id}), Is(None))
        self.expectThat(handler.cache["node_ids"], Equals([]))

    def test_on_listen_calls_listen(self):
        user = factory.make_User()
        handler = EventHandler(user, {})
        mock_listen = self.patch(handler, "listen")
        mock_listen.return_value = None
        pk = random.randint(1, 1000)
        handler.on_listen(sentinel.channel, sentinel.action, pk)
        self.assertThat(
            mock_listen,
            MockCalledOnceWith(
                sentinel.channel, sentinel.action, pk))

    def test_on_listen_returns_None_if_listen_returns_None(self):
        user = factory.make_User()
        handler = EventHandler(user, {})
        mock_listen = self.patch(handler, "listen")
        mock_listen.return_value = None
        self.assertIsNone(
            handler.on_listen(
                sentinel.channel, sentinel.action, random.randint(1, 1000)))

    def test_on_listen_delete_returns_handler_name_and_pk(self):
        user = factory.make_User()
        pk = random.randint(1, 1000)
        handler = EventHandler(user, {})
        self.assertEquals(
            (handler._meta.handler_name, "delete", pk),
            handler.on_listen(
                sentinel.channel, "delete", pk))

    def test_on_listen_returns_None_if_event_node_id_not_in_cache(self):
        user = factory.make_User()
        handler = EventHandler(user, {})
        node = factory.make_Node()
        event = factory.make_Event(node=node)
        self.assertIsNone(
            handler.on_listen(
                sentinel.channel, "create", event.id))

    def test_on_listen_returns_handler_name_action_and_event(self):
        user = factory.make_User()
        handler = EventHandler(user, {})
        node = factory.make_Node()
        event = factory.make_Event(node=node)
        handler.cache["node_ids"].append(node.id)
        self.assertEquals(
            (
                handler._meta.handler_name,
                "create",
                self.dehydrate_event(event)
            ),
            handler.on_listen(sentinel.channel, "create", event.id))
