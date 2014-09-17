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

from maasserver.models import (
    Event,
    EventType,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


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
