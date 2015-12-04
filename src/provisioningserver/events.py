# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Event catalog."""

__all__ = [
    'EVENT_DETAILS',
    'EVENT_TYPES',
    'send_event_node',
    'send_event_node_mac_address',
    ]

from collections import namedtuple
from logging import (
    DEBUG,
    ERROR,
    INFO,
    WARN,
)

from provisioningserver.logger.log import get_maas_logger
from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.exceptions import (
    NoSuchEventType,
    NoSuchNode,
)
from provisioningserver.rpc.region import (
    RegisterEventType,
    SendEvent,
    SendEventMACAddress,
)
from provisioningserver.utils.twisted import (
    asynchronous,
    callOut,
    DeferredValue,
)
from twisted.internet.defer import (
    maybeDeferred,
    succeed,
)
from twisted.python.failure import Failure


maaslog = get_maas_logger("events")


class EVENT_TYPES:
    # Power-related events.
    NODE_POWER_ON_STARTING = 'NODE_POWER_ON_STARTING'
    NODE_POWER_OFF_STARTING = 'NODE_POWER_OFF_STARTING'
    NODE_POWERED_ON = 'NODE_POWERED_ON'
    NODE_POWERED_OFF = 'NODE_POWERED_OFF'
    NODE_POWER_ON_FAILED = 'NODE_POWER_ON_FAILED'
    NODE_POWER_OFF_FAILED = 'NODE_POWER_OFF_FAILED'
    NODE_POWER_QUERY_FAILED = 'NODE_POWER_QUERY_FAILED'
    # PXE request event.
    NODE_PXE_REQUEST = 'NODE_PXE_REQUEST'
    # TFTP request event.
    NODE_TFTP_REQUEST = 'NODE_TFTP_REQUEST'
    # Other installation-related event types.
    NODE_INSTALLATION_FINISHED = "NODE_INSTALLATION_FINISHED"
    # Node status transition event.
    NODE_CHANGED_STATUS = "NODE_CHANGED_STATUS"
    # Node status events
    NODE_STATUS_EVENT = "NODE_STATUS_EVENT"
    NODE_COMMISSIONING_EVENT = "NODE_COMMISSIONING_EVENT"
    NODE_INSTALL_EVENT = "NODE_INSTALL_EVENT"
    # Node user request events
    REQUEST_NODE_START_COMMISSIONING = "REQUEST_NODE_START_COMMISSIONING"
    REQUEST_NODE_ABORT_COMMISSIONING = "REQUEST_NODE_ABORT_COMMISSIONING"
    REQUEST_NODE_ABORT_DEPLOYMENT = "REQUEST_NODE_ABORT_DEPLOYMENT"
    REQUEST_NODE_ACQUIRE = "REQUEST_NODE_ACQUIRE"
    REQUEST_NODE_ERASE_DISK = "REQUEST_NODE_ERASE_DISK"
    REQUEST_NODE_ABORT_ERASE_DISK = "REQUEST_NODE_ABORT_ERASE_DISK"
    REQUEST_NODE_RELEASE = "REQUEST_NODE_RELEASE"
    REQUEST_NODE_MARK_FAILED = "REQUEST_NODE_MARK_FAILED"
    REQUEST_NODE_MARK_BROKEN = "REQUEST_NODE_MARK_BROKEN"
    REQUEST_NODE_MARK_FIXED = "REQUEST_NODE_MARK_FIXED"
    REQUEST_NODE_START_DEPLOYMENT = "REQUEST_NODE_START_DEPLOYMENT"
    REQUEST_NODE_START = "REQUEST_NODE_START"
    REQUEST_NODE_STOP = "REQUEST_NODE_STOP"


EventDetail = namedtuple("EventDetail", ("description", "level"))


EVENT_DETAILS = {
    # Event type -> EventDetail mapping.
    EVENT_TYPES.NODE_POWER_ON_STARTING: EventDetail(
        description="Powering node on",
        level=INFO,
    ),
    EVENT_TYPES.NODE_POWER_OFF_STARTING: EventDetail(
        description="Powering node off",
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
    EVENT_TYPES.NODE_POWER_QUERY_FAILED: EventDetail(
        description="Failed to query node's BMC",
        level=WARN,
    ),
    EVENT_TYPES.NODE_TFTP_REQUEST: EventDetail(
        description="TFTP Request",
        level=DEBUG,
    ),
    EVENT_TYPES.NODE_PXE_REQUEST: EventDetail(
        description="PXE Request",
        level=INFO,
    ),
    EVENT_TYPES.NODE_INSTALLATION_FINISHED: EventDetail(
        description="Installation complete",
        level=INFO,
    ),
    EVENT_TYPES.NODE_CHANGED_STATUS: EventDetail(
        description="Node changed status",
        level=INFO,
    ),
    EVENT_TYPES.NODE_STATUS_EVENT: EventDetail(
        description="Node status event",
        level=DEBUG,
    ),
    EVENT_TYPES.NODE_COMMISSIONING_EVENT: EventDetail(
        description="Node commissioning",
        level=DEBUG,
    ),
    EVENT_TYPES.NODE_INSTALL_EVENT: EventDetail(
        description="Node installation",
        level=DEBUG,
    ),
    EVENT_TYPES.REQUEST_NODE_START_COMMISSIONING: EventDetail(
        description="User starting node commissioning",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_ABORT_COMMISSIONING: EventDetail(
        description="User aborting node commissioning",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_ABORT_DEPLOYMENT: EventDetail(
        description="User aborting deployment",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_ACQUIRE: EventDetail(
        description="User acquiring node",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_ERASE_DISK: EventDetail(
        description="User erasing disk",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_ABORT_ERASE_DISK: EventDetail(
        description="User aborting disk erase",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_RELEASE: EventDetail(
        description="User releasing node",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_MARK_FAILED: EventDetail(
        description="User marking node failed",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_MARK_BROKEN: EventDetail(
        description="User marking node broken",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_MARK_FIXED: EventDetail(
        description="User marking node fixed",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_START_DEPLOYMENT: EventDetail(
        description="User starting deployment",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_START: EventDetail(
        description="User powering up node",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_STOP: EventDetail(
        description="User powering down node",
        level=INFO,
    ),
}


class NodeEventHub:
    """Singleton for sending node events to the region.

    This automatically ensures that the event type is registered before
    sending logs to the region.
    """

    def __init__(self):
        super(NodeEventHub, self).__init__()
        self._types_registering = dict()
        self._types_registered = set()

    @asynchronous
    def registerEventType(self, event_type):
        """Ensure that `event_type` is known to the region.

        This populates the cache used by `ensureEventTypeRegistered` but does
        not consult it; it always attempts to contact the region.

        :return: :class:`Deferred`
        """
        details = EVENT_DETAILS[event_type]

        def register(client):
            return client(
                RegisterEventType, name=event_type, level=details.level,
                description=details.description)

        d = maybeDeferred(getRegionClient).addCallback(register)
        # Whatever happens, we are now done registering.
        d.addBoth(callOut, self._types_registering.pop, event_type)
        # On success, record that the event type has been registered. On
        # failure, ensure that the set of registered event types does NOT
        # contain the event type.
        d.addCallbacks(
            callback=callOut, callbackArgs=(
                self._types_registered.add, event_type),
            errback=callOut, errbackArgs=(
                self._types_registered.discard, event_type))
        # Capture the result into a DeferredValue.
        result = DeferredValue()
        result.capture(d)
        # Keep track of it so that concurrent requests don't duplicate work.
        self._types_registering[event_type] = result
        return result.get()

    @asynchronous
    def ensureEventTypeRegistered(self, event_type):
        """Ensure that `event_type` is known to the region.

        This method keeps track of event types that it has already registered,
        and so can return in the affirmative without needing to contact the
        region.

        :return: :class:`Deferred`
        """
        if event_type in self._types_registered:
            return succeed(None)
        elif event_type in self._types_registering:
            return self._types_registering[event_type].get()
        else:
            return self.registerEventType(event_type)

    def _checkEventTypeRegistered(self, failure, event_type):
        """Check if the event type is NOT registered after all.

        Maybe someone has monkeyed about with the region database and removed
        the event type? In any case, if we see `NoSuchEventType` coming back
        from a `SendEvent` or `SendEventMACAddress` call we discard the event
        type from the set of registered types. Subsequent logging calls will
        cause this class to attempt to register the event type again.

        As of MAAS 1.9 the region will no longer signal `NoSuchEventType` or
        `NoSuchNode` errors because database activity is not performed before
        returning. This method thus exists for compatibility with pre-1.9
        region controllers only.

        All failures, including `NoSuchEventType`, are passed through.
        """
        if failure.check(NoSuchEventType):
            self._types_registered.discard(event_type)
        return failure

    @asynchronous
    def logByID(self, event_type, system_id, description=""):
        """Send the given node event to the region.

        The node is specified by its ID.

        :param event_type: The type of the event.
        :type event_type: unicode
        :param system_id: The system ID of the node.
        :type system_id: unicode
        :param description: An optional description of the event.
        :type description: unicode
        """
        def send(_):
            client = getRegionClient()
            return client(
                SendEvent, system_id=system_id, type_name=event_type,
                description=description)

        d = self.ensureEventTypeRegistered(event_type).addCallback(send)
        d.addErrback(self._checkEventTypeRegistered, event_type)
        return d

    @asynchronous
    def logByMAC(self, event_type, mac_address, description=""):
        """Send the given node event to the region.

        The node is specified by its MAC address.

        :param event_type: The type of the event.
        :type event_type: unicode
        :param mac_address: The MAC address of the node.
        :type mac_address: unicode
        :param description: An optional description of the event.
        :type description: unicode
        """
        def send(_):
            client = getRegionClient()
            return client(
                SendEventMACAddress, mac_address=mac_address,
                type_name=event_type, description=description)

        d = self.ensureEventTypeRegistered(event_type).addCallback(send)
        d.addErrback(self._checkEventTypeRegistered, event_type)

        # Suppress NoSuchNode. This happens during enlistment because the
        # region does not yet know of the node; it's quite normal. Logging
        # tracebacks telling us about it is not useful. Perhaps the region
        # should store these logs anyway. Then, if and when the node is
        # enlisted, logs prior to enlistment can be seen.
        d.addErrback(Failure.trap, NoSuchNode)

        return d


# Singleton.
nodeEventHub = NodeEventHub()


@asynchronous
def send_event_node(event_type, system_id, hostname, description=''):
    """Send the given node event to the region.

    :param event_type: The type of the event.
    :type event_type: unicode
    :param system_id: The system ID of the node of the event.
    :type system_id: unicode
    :param hostname: Ignored!
    :param description: An optional description of the event.
    :type description: unicode
    """
    return nodeEventHub.logByID(event_type, system_id, description)


@asynchronous
def send_event_node_mac_address(event_type, mac_address, description=''):
    """Send the given node event to the region for the given mac address.

    :param event_type: The type of the event.
    :type event_type: unicode
    :param mac_address: The MAC Address of the node of the event.
    :type mac_address: unicode
    :param description: An optional description of the event.
    :type description: unicode
    """
    return nodeEventHub.logByMAC(event_type, mac_address, description)
