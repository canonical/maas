# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`Event` and friends."""

__all__ = [
    'Event',
    ]

import logging

from django.contrib.auth.models import User
from django.db.models import (
    CharField,
    ForeignKey,
    IntegerField,
    Manager,
    PROTECT,
    SET_NULL,
    TextField,
)
from maasserver import DefaultMeta
from maasserver.enum import (
    ENDPOINT,
    ENDPOINT_CHOICES,
)
from maasserver.fields import MAASIPAddressField
from maasserver.models.cleansave import CleanSave
from maasserver.models.eventtype import EventType
from maasserver.models.node import Node
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.dns import validate_hostname
from provisioningserver.events import EVENT_DETAILS
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.env import get_maas_id


maaslog = get_maas_logger('models.event')


class EventManager(Manager):
    """A utility to manage the collection of Events."""

    def register_event_and_event_type(
            self, type_name, type_description='',
            type_level=logging.INFO, event_action='',
            event_description='', system_id=None, user=None,
            ip_address=None, endpoint=ENDPOINT.API,
            user_agent='', created=None):
        """Register EventType if it does not exist, then register the Event."""
        node = (Node.objects.get(system_id=system_id)
                if system_id is not None else None)
        try:
            # Be optimistic; try to retrieve the event type first.
            event_type = EventType.objects.get(name=type_name)
        except EventType.DoesNotExist:
            # We didn't find it so register it.
            event_type = EventType.objects.register(
                type_name, type_description, type_level)
        return Event.objects.create(
            type=event_type, node=node, user=user, ip_address=ip_address,
            endpoint=endpoint, user_agent=user_agent, action=event_action,
            description=event_description, created=created)

    def create_node_event(
            self, system_id, event_type, event_action='',
            event_description='', user=None):
        """Helper to register event and event type for the given node."""
        self.register_event_and_event_type(
            system_id=system_id, type_name=event_type,
            type_description=EVENT_DETAILS[event_type].description,
            type_level=EVENT_DETAILS[event_type].level,
            event_action=event_action,
            event_description=event_description, user=user)

    def create_region_event(self, event_type, event_description='', user=None):
        """Helper to register event and event type for the running region."""
        self.create_node_event(
            system_id=get_maas_id(), event_type=event_type,
            event_description=event_description, user=user)


class Event(CleanSave, TimestampedModel):
    """An `Event` represents a MAAS event.

    :ivar type: The event's type.
    :ivar node: The node of the event.
    :ivar node_hostname: The hostname of the node of the event.
    :ivar user: The user responsible for this event.
    :ivar username: The username of the user responsible for this event.
    :ivar ip_address: IP address used in the request for this event.
    :ivar endpoint: Endpoint used in the request for this event.
    :ivar user_agent: User agent used in the request for this event.
    :ivar action: The action of the event.
    :ivar description: A free-form description of the event.
    """

    type = ForeignKey(
        'EventType', null=False, editable=False, on_delete=PROTECT)

    node = ForeignKey('Node', null=True, editable=False, on_delete=SET_NULL)

    # Set on node deletion.
    node_hostname = CharField(
        max_length=255, default='', blank=True, validators=[validate_hostname])

    user = ForeignKey(
        User, default=None, blank=True, null=True, editable=False,
        on_delete=SET_NULL)

    # Set on user deletion.
    username = CharField(max_length=32, blank=True, default='')

    # IP address of the request that caused this event.
    ip_address = MAASIPAddressField(
        unique=False, null=True, editable=False, blank=True, default=None)

    # Endpoint of request used to register the event.
    endpoint = IntegerField(
        choices=ENDPOINT_CHOICES, editable=False, default=ENDPOINT.API)

    # User agent of request used to register the event.
    user_agent = TextField(default='', blank=True, editable=False)

    action = TextField(default='', blank=True, editable=False)

    description = TextField(default='', blank=True, editable=False)

    objects = EventManager()

    class Meta(DefaultMeta):
        verbose_name = "Event record"
        index_together = (
            ("node", "id"),
        )

    @property
    def endpoint_name(self):
        return ENDPOINT_CHOICES[self.endpoint][1]

    @property
    def render_audit_description(self):
        if self.username:
            return self.description % {'username': self.username}
        else:
            return self.description % {'username': self.user.username}

    def __str__(self):
        return "%s (node=%s, type=%s, created=%s)" % (
            self.id, self.node, self.type.name, self.created)
