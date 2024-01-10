# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.event`"""


import datetime
import random
from unittest.mock import sentinel

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerDoesNotExistError,
    HandlerPKError,
)
from maasserver.websockets.handlers.event import (
    dehydrate_event_type_level,
    EventHandler,
)


class TestEventHandler(MAASServerTestCase):
    def dehydrate_event(self, event):
        data = {
            "id": event.id,
            "node_id": event.node.id,
            "node_system_id": event.node_system_id,
            "node_hostname": event.node_hostname,
            "username": event.username,
            "ip_address": event.ip_address,
            "endpoint": event.endpoint,
            "user_agent": event.user_agent,
            "user_id": event.user_id,
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
        return [self.dehydrate_event(event) for event in events]

    def make_event_in_the_past(self, user, node, days_old):
        event = factory.make_Event(user=user, node=node)
        event.created -= datetime.timedelta(days_old)
        event.save()
        return event

    def test_list_raises_error_if_missing_node_id(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        self.assertRaises(HandlerPKError, handler.list, {})

    def test_list_raises_error_if_node_doesnt_exist(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        node = factory.make_Node()
        node.delete()
        self.assertRaises(
            HandlerDoesNotExistError, handler.list, {"node_id": node.id}
        )

    def test_list_places_node_id_in_cache(self):
        user = factory.make_User()
        cache = {}
        handler = EventHandler(user, cache, None)
        node = factory.make_Node()
        handler.list({"node_id": node.id})
        self.assertEqual([node.id], cache["node_ids"])

    def test_list_only_returns_events_for_node(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        node = factory.make_Node()
        events = [factory.make_Event(user=user, node=node) for _ in range(3)]
        # Other events.
        for _ in range(3):
            factory.make_Event()
        self.assertCountEqual(
            self.dehydrate_events(events),
            handler.list({"node_id": node.id, "user_id": user.id}),
        )

    def test_list_returns_newest_event_first(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        node = factory.make_Node()
        events = [factory.make_Event(user=user, node=node) for _ in range(3)]
        # Other events.
        for _ in range(3):
            factory.make_Event()
        self.assertEqual(
            self.dehydrate_events(reversed(events)),
            handler.list({"node_id": node.id}),
        )

    def test_list_default_max_days_of_30(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        node = factory.make_Node()
        events = [factory.make_Event(node=node) for _ in range(3)]
        # Event older than 30 days.
        self.make_event_in_the_past(user, node, 31)
        self.assertCountEqual(
            self.dehydrate_events(events), handler.list({"node_id": node.id})
        )

    def test_list_uses_max_days(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        node = factory.make_Node()
        maxdays = random.randint(3, 50)
        events = [
            self.make_event_in_the_past(user, node, maxdays - 1)
            for _ in range(3)
        ]
        for _ in range(3):
            self.make_event_in_the_past(user, node, maxdays + 1)
        self.assertCountEqual(
            self.dehydrate_events(events),
            handler.list({"node_id": node.id, "max_days": maxdays}),
        )

    def test_list_start(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        node = factory.make_Node()
        events = list(
            reversed(
                [factory.make_Event(user=user, node=node) for _ in range(6)]
            )
        )
        expected_output = self.dehydrate_events(events[3:])
        self.assertCountEqual(
            expected_output,
            handler.list({"node_id": node.id, "start": events[2].id}),
        )

    def test_list_limit(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        node = factory.make_Node()
        events = list(
            reversed(
                [factory.make_Event(user=user, node=node) for _ in range(6)]
            )
        )
        expected_output = self.dehydrate_events(events[:3])
        self.assertCountEqual(
            expected_output, handler.list({"node_id": node.id, "limit": 3})
        )

    def test_list_start_and_limit(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        node = factory.make_Node()
        events = list(
            reversed(
                [factory.make_Event(user=user, node=node) for _ in range(9)]
            )
        )
        expected_output = self.dehydrate_events(events[3:6])
        self.assertCountEqual(
            expected_output,
            handler.list(
                {"node_id": node.id, "start": events[2].id, "limit": 3}
            ),
        )

    def test_clear_raises_error_if_missing_node_id(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        self.assertRaises(HandlerPKError, handler.clear, {})

    def test_clear_raises_error_if_node_id_doesnt_exist(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        node = factory.make_Node()
        node.delete()
        self.assertRaises(
            HandlerDoesNotExistError, handler.clear, {"node_id": node.id}
        )

    def test_clear_removes_node_id_from_cache(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        node = factory.make_Node()
        handler.cache["node_ids"].append(node.id)
        self.assertIsNone(handler.clear({"node_id": node.id}))
        self.assertEqual(handler.cache["node_ids"], [])

    def test_on_listen_calls_listen_for_create(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        mock_listen = self.patch(handler, "listen")
        mock_listen.return_value = None
        pk = random.randint(1, 1000)
        handler.on_listen(sentinel.channel, "create", pk)
        mock_listen.assert_called_once_with(sentinel.channel, "create", pk)

    def test_on_listen_doesnt_call_listen_for_non_create(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        mock_listen = self.patch(handler, "listen")
        mock_listen.return_value = None
        pk = random.randint(1, 1000)
        action = factory.make_string()
        if action != "create":
            handler.on_listen(sentinel.channel, action, pk)
            mock_listen.assert_not_called()

    def test_on_listen_returns_None_if_obj_no_longer_exists(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        mock_listen = self.patch(handler, "listen")
        mock_listen.return_value = HandlerDoesNotExistError()
        self.assertIsNone(
            handler.on_listen(
                sentinel.channel, sentinel.action, random.randint(1, 1000)
            )
        )

    def test_on_listen_returns_None_if_listen_returns_None(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        mock_listen = self.patch(handler, "listen")
        mock_listen.return_value = None
        self.assertIsNone(
            handler.on_listen(
                sentinel.channel, sentinel.action, random.randint(1, 1000)
            )
        )

    def test_on_listen_returns_None_if_event_node_id_not_in_cache(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        node = factory.make_Node()
        event = factory.make_Event(node=node)
        self.assertIsNone(
            handler.on_listen(sentinel.channel, "create", event.id)
        )

    def test_on_listen_returns_handler_name_action_and_event(self):
        user = factory.make_User()
        handler = EventHandler(user, {}, None)
        node = factory.make_Node()
        event = factory.make_Event(user=user, node=node)
        handler.cache["node_ids"].append(node.id)
        self.assertEqual(
            (
                handler._meta.handler_name,
                "create",
                self.dehydrate_event(event),
            ),
            handler.on_listen(sentinel.channel, "create", event.id),
        )
