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
    "send_event_mac_address",
]

from maasserver.models import (
    Event,
    EventType,
    MACAddress,
    Node,
    )
from maasserver.utils.async import transactional
from provisioningserver.logger.log import get_maas_logger
from provisioningserver.rpc.exceptions import NoSuchEventType
from provisioningserver.utils.twisted import synchronous


maaslog = get_maas_logger("region.events")


@synchronous
@transactional
def register_event_type(name, description, level):
    """Register an event type.

    for :py:class:`~provisioningserver.rpc.region.RegisterEventType`.
    """
    EventType.objects.register(name, description, level)


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
        # The node doesn't exist, but we don't raise an exception - it's
        # entirely possible the cluster has started sending events for a
        # node that we don't know about yet.
        # This is most likely to happen when a new node is trying to
        # enlist.
        maaslog.debug(
            "Event '%s: %s' sent for non-existent node '%s'.",
            type_name, description, system_id)
        return

    Event.objects.create(
        node=node, type=event_type, description=description)


@synchronous
@transactional
def send_event_mac_address(mac_address, type_name, description=''):
    """Send an event.

    for :py:class:`~provisioningserver.rpc.region.SendEventMACAddress`.
    """
    try:
        event_type = EventType.objects.get(name=type_name)
    except EventType.DoesNotExist:
        raise NoSuchEventType.from_name(type_name)

    try:
        node = MACAddress.objects.get(mac_address=mac_address).node
    except MACAddress.DoesNotExist:
        # The node doesn't exist, but we don't raise an exception - it's
        # entirely possible the cluster has started sending events for a
        # node that we don't know about yet.
        # This is most likely to happen when a new node is trying to
        # enlist.
        maaslog.debug(
            "Event '%s: %s' sent for non-existent node with MAC "
            "address '%s'.",
            type_name, description, mac_address)
        return

    Event.objects.create(
        node=node, type=event_type, description=description)
