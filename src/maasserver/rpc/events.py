# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to events."""

from maasserver.enum import INTERFACE_TYPE
from maasserver.models import Event, EventType, Interface, Node
from maasserver.utils.orm import transactional
from provisioningserver.logger import LegacyLogger
from provisioningserver.rpc.exceptions import NoSuchEventType
from provisioningserver.utils.twisted import synchronous

log = LegacyLogger()


@synchronous
@transactional
def register_event_type(name, description, level):
    """Register an event type.

    for :py:class:`~provisioningserver.rpc.region.RegisterEventType`.
    """
    EventType.objects.register(name, description, level)


@synchronous
@transactional
def send_event(system_id, type_name, description, timestamp):
    """Send an event.

    for :py:class:`~provisioningserver.rpc.region.SendEvent`.
    """
    try:
        event_type = EventType.objects.get(name=type_name)
    except EventType.DoesNotExist:
        raise NoSuchEventType.from_name(type_name)  # noqa: B904

    try:
        node = Node.objects.get(system_id=system_id)
    except Node.DoesNotExist:
        # The node doesn't exist, but we don't raise an exception - it's
        # entirely possible the cluster has started sending events for a node
        # that we don't know about yet. This is most likely to happen when a
        # new node is trying to enlist.
        log.debug(
            "Event '{type}: {description}' sent for non-existent "
            "node '{node_id}'.",
            type=type_name,
            description=description,
            node_id=system_id,
        )
    else:
        Event.objects.create(
            node=node,
            type=event_type,
            description=description,
            created=timestamp,
        )


@synchronous
@transactional
def send_event_mac_address(mac_address, type_name, description, timestamp):
    """Send an event.

    for :py:class:`~provisioningserver.rpc.region.SendEventMACAddress`.
    """
    try:
        event_type = EventType.objects.get(name=type_name)
    except EventType.DoesNotExist:
        raise NoSuchEventType.from_name(type_name)  # noqa: B904

    try:
        interface = Interface.objects.get(
            type=INTERFACE_TYPE.PHYSICAL, mac_address=mac_address
        )
    except Interface.DoesNotExist:
        # The node doesn't exist, but we don't raise an exception - it's
        # entirely possible the cluster has started sending events for a node
        # that we don't know about yet. This is most likely to happen when a
        # new node is trying to enlist.
        log.debug(
            "Event '{type}: {description}' sent for non-existent "
            "node with MAC address '{mac}'.",
            type=type_name,
            description=description,
            mac=mac_address,
        )
    else:
        Event.objects.create(
            node_id=interface.node_config.node_id,
            type=event_type,
            description=description,
            created=timestamp,
        )


@synchronous
@transactional
def send_event_ip_address(ip_address, type_name, description, timestamp):
    """Send an event using IP address.

    for :py:class:`~provisioningserver.rpc.region.SendEventIPAddress`.
    """
    try:
        event_type = EventType.objects.get(name=type_name)
    except EventType.DoesNotExist:
        raise NoSuchEventType.from_name(type_name)  # noqa: B904

    node = Node.objects.filter(
        current_config__interface__ip_addresses__ip=ip_address
    ).first()
    if node is None:
        # The node doesn't exist, but we don't raise an exception - it's
        # entirely possible the cluster has started sending events for a node
        # that we don't know about yet. This is most likely to happen when a
        # new node is trying to enlist.
        log.debug(
            "Event '{type}: {description}' sent for non-existent "
            "node with IP address '{ip_address}'.",
            type=type_name,
            description=description,
            ip_address=ip_address,
        )
    else:
        Event.objects.create(
            node=node,
            type=event_type,
            description=description,
            created=timestamp,
        )
