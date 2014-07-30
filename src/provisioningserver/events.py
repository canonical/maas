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

from provisioningserver.logger.log import get_maas_logger
from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.exceptions import NoSuchEventType
from provisioningserver.rpc.region import (
    RegisterEventType,
    SendEvent,
    )
from twisted.internet.defer import inlineCallbacks


maaslog = get_maas_logger("events")


class EVENT_TYPES:
    # Power-related events.
    NODE_POWER_ON_STARTING = 'NODE_POWER_ON_STARTING'
    NODE_POWER_OFF_STARTING = 'NODE_POWER_OFF_STARTING'
    NODE_POWERED_ON = 'NODE_POWERED_ON'
    NODE_POWERED_OFF = 'NODE_POWERED_OFF'
    NODE_POWER_ON_FAILED = 'NODE_POWER_ON_FAILED'
    NODE_POWER_OFF_FAILED = 'NODE_POWER_OFF_FAILED'


EventDetail = namedtuple("EventDetail", ("description", "level"))


EVENT_DETAILS = {
    # Event type -> EventDetail mapping.
    EVENT_TYPES.NODE_POWER_ON_STARTING: EventDetail(
        description="Node power on starting",
        level=INFO,
    ),
    EVENT_TYPES.NODE_POWER_OFF_STARTING: EventDetail(
        description="Node power off starintg",
        level=INFO,
    ),
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


@inlineCallbacks
def send_event_node(event_type, system_id, hostname, description=''):
    """Send the given node event to the region.

    Also register the event type if it's not registered yet.

    :param event_type: The type of the event.
    :type event_type: unicode
    :param system_id: The system ID of the node of the event.
    :type system_id: unicode
    :param hostname: The hostname of the node of the event.
    :type hostname: unicode
    :param description: An optional description of the event.
    :type description: unicode
    """
    client = getRegionClient()
    try:
        yield client(
            SendEvent, system_id=system_id, type_name=event_type,
            description=description)
    except NoSuchEventType:
        # The event type doesn't exist, register it and re-send the event.
        event_detail = EVENT_DETAILS[event_type]
        yield client(
            RegisterEventType, name=event_type,
            description=event_detail.description, level=event_detail.level
        )
        yield client(
            SendEvent, system_id=system_id, type_name=event_type,
            description=description)
    maaslog.debug(
        "Node event %s sent for node: %s (%s)",
        event_type, hostname, system_id)
