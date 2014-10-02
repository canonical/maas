# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`Event` and friends."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'Event',
    ]

import logging

from django.db.models import (
    ForeignKey,
    Manager,
    TextField,
    )
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.eventtype import EventType
from maasserver.models.node import Node
from maasserver.models.timestampedmodel import TimestampedModel
from provisioningserver.events import EVENT_DETAILS


class EventManager(Manager):
    """A utility to manage the collection of Events."""

    def register_event_and_event_type(self, system_id, type_name,
                                      type_description='',
                                      type_level=logging.INFO,
                                      event_description=''):
        """Register EventType if it does not exist, then register the Event."""
        # Check if event type is registered.
        try:
            event_type = EventType.objects.get(name=type_name)
        except EventType.DoesNotExist:
            # Create the event type.
            event_type = EventType.objects.create(
                name=type_name, description=type_description,
                level=type_level)

        node = Node.objects.get(system_id=system_id)

        Event.objects.create(
            node=node, type=event_type, description=event_description)

    def create_node_event(self, system_id, event_type, event_description=''):
        """Helper to register event and event type for the given node."""
        self.register_event_and_event_type(
            system_id=system_id, type_name=event_type,
            type_description=EVENT_DETAILS[event_type].description,
            type_level=EVENT_DETAILS[event_type].level,
            event_description=event_description)


class Event(CleanSave, TimestampedModel):
    """An `Event` represents a MAAS event.

    :ivar type: The event's type.
    :ivar node: The node of the event.
    :ivar description: A free-form description of the event.
    """

    type = ForeignKey('EventType', null=False, editable=False)

    node = ForeignKey('Node', null=False, editable=False)

    description = TextField(default='', blank=True, editable=False)

    objects = EventManager()

    class Meta(DefaultMeta):
        verbose_name = "Event record"

    def __unicode__(self):
        return "%s (node=%s, type=%s, created=%s)" % (
            self.id, self.node, self.type.name, self.created)
