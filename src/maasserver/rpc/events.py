# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to events."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "register_event_type",
    "send_event",
]


from maasserver.models import (
    Event,
    EventType,
    Node,
    )
from maasserver.utils.async import transactional
from provisioningserver.rpc.exceptions import (
    NoSuchEventType,
    NoSuchNode,
    )
from provisioningserver.utils.twisted import synchronous


@synchronous
@transactional
def register_event_type(name, description, level):
    """Register an event type.

    for :py:class:`~provisioningserver.rpc.region.RegisterEventType`.
    """
    EventType.objects.create(
        name=name, description=description, level=level)


@synchronous
@transactional
def send_event(system_id, type_name, description=''):
    """Send an event.

    for :py:class:`~provisioningserver.rpc.region.SendEvent`.
    """
    try:
        event_type = EventType.objects.get(name=type_name)
    except EventType.DoesNotExist:
        raise NoSuchEventType.from_name(type_name)

    try:
        node = Node.objects.get(system_id=system_id)
    except Node.DoesNotExist:
        raise NoSuchNode.from_system_id(system_id)

    Event.objects.create(
        node=node, type=event_type, description=description)
