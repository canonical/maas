# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Event catalog."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'EVENT_DETAILS',
    'EVENT_TYPES',
    ]

from collections import namedtuple
from logging import (
    ERROR,
    INFO,
    )

from provisioningserver.rpc.exceptions import NoSuchEventType
from provisioningserver.rpc.region import (
    RegisterEventType,
    SendEvent,
    )


class EVENT_TYPES:
    # Power-related events.
    NODE_POWERED_ON = 'NODE_POWERED_ON'
    NODE_POWERED_OFF = 'NODE_POWERED_OFF'
    NODE_POWER_ON_FAILED = 'NODE_POWER_ON_FAILED'
    NODE_POWER_OFF_FAILED = 'NODE_POWER_OFF_FAILED'


EventDetail = namedtuple("EventDetail", ("description", "level"))


EVENT_DETAILS = {
    # Event type -> EventDetail mapping.
    EVENT_TYPES.NODE_POWERED_ON: EventDetail(
        description="Node powered on",
        level=INFO,
    ),
    EVENT_TYPES.NODE_POWERED_OFF: EventDetail(
        description="Node powered off",
        level=INFO,
    ),
    EVENT_TYPES.NODE_POWER_ON_FAILED: EventDetail(
        description="Failed to power on node",
        level=ERROR,
    ),
    EVENT_TYPES.NODE_POWER_OFF_FAILED: EventDetail(
        description="Failed to power off node",
        level=ERROR,
    ),
}


def send_event_node(client, event_type, system_id, description=''):
    """Send the given node event to the region.

    Also register the event type if it's not registered yet.

    :param client: A region RPC client.
    :type rpc_service: :class:`common.Client`
    :param event_type: The type of the event.
    :type event_type: unicode
    :param system_id: The system ID of the node of the event.
    :type system_id: unicode
    :param description: An optional description for of the event.
    :type description: unicode
    """
    try:
        client(
            SendEvent, system_id=system_id, type_name=event_type,
            description=description)
    except NoSuchEventType:
        # The event type doesn't exist, register it and re-send the event.
        event_detail = EVENT_DETAILS[event_type]
        client(
            RegisterEventType, name=event_type,
            description=event_detail.description, level=event_detail.level
        )
        client(
            SendEvent, system_id=system_id, type_name=event_type,
            description=description)
