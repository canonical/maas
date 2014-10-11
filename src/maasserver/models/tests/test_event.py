# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Event model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import logging
import random

from django.db import IntegrityError
from maasserver.models import (
    Event,
    event as event_module,
    EventType,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from provisioningserver.events import EVENT_TYPES


class EventTest(MAASServerTestCase):

    def test_displays_event_node(self):
        event = factory.make_Event()
        self.assertIn("%s" % event.node, "%s" % event)

    def test_register_event_and_event_type_registers_event(self):
        # EvenType exists
        node = factory.make_Node()
        event_type = factory.make_EventType()
        Event.objects.register_event_and_event_type(
            system_id=node.system_id, type_name=event_type.name)
        self.assertIsNotNone(Event.objects.get(node=node))

    def test_register_event_and_event_type_registers_event_type(self):
        # EventType does not exist
        node = factory.make_Node()
        type_name = factory.make_name('type_name')
        description = factory.make_name('description')
        Event.objects.register_event_and_event_type(
            system_id=node.system_id, type_name=type_name,
            type_description=description,
            type_level=random.choice(
                [logging.ERROR, logging.WARNING, logging.INFO]),
            event_description=description)
        self.assertIsNotNone(EventType.objects.get(name=type_name))
        self.assertIsNotNone(Event.objects.get(node=node))

    def test_create_node_event_creates_event(self):
        # EventTypes that are currently being used for
        # create_node_event
        node = factory.make_Node()
        event_type = random.choice([EVENT_TYPES.NODE_PXE_REQUEST])
        Event.objects.create_node_event(
            system_id=node.system_id, event_type=event_type)
        self.assertIsNotNone(EventType.objects.get(name=event_type))
        self.assertIsNotNone(Event.objects.get(node=node))

    def test_register_event_and_event_type_handles_integrity_errors(self):
        # It's possible that two calls to
        # register_event_and_event_type() could arrive at more-or-less
        # the same time. If that happens, we could end up with an
        # IntegrityError getting raised. register_event_and_event_type()
        # will handle that correctly rather than allowing it to blow up.
        node = factory.make_Node()
        type_name = factory.make_name('type_name')
        description = factory.make_name('description')
        maaslog = self.patch(event_module, 'maaslog')

        Event.objects.register_event_and_event_type(
            system_id=node.system_id, type_name=type_name,
            type_description=description,
            type_level=random.choice(
                [logging.ERROR, logging.WARNING, logging.INFO]),
            event_description=description)

        # Patch EventTypes.object.get() so that it raises DoesNotExist.
        # This will cause the creation code to be run, which is where
        # the IntegrityError occurs.
        event_type = EventType.objects.get(name=type_name)
        self.patch(EventType.objects, 'get').side_effect = [
            EventType.DoesNotExist(),
            event_type,
            ]
        self.patch(EventType.objects, 'create').side_effect = (
            IntegrityError)
        Event.objects.register_event_and_event_type(
            system_id=node.system_id, type_name=type_name,
            type_description=description,
            type_level=random.choice(
                [logging.ERROR, logging.WARNING, logging.INFO]),
            event_description=description)

        # If we get this far then we have the event type and the
        # events, and more importantly no errors got raised.
        self.assertIsNotNone(event_type)
        self.assertEqual(2, Event.objects.filter(node=node).count())

        # We log a debug message to say that we've hit the race.
        self.assertThat(
            maaslog.debug, MockCalledOnceWith(
                "IntegrityError caught in register_event_and_event_type; "
                "Trying to fetch event type '%s' again", type_name))
