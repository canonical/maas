# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Event catalog."""

__all__ = [
    'EVENT_DETAILS',
    'EVENT_TYPES',
    'send_node_event',
    'send_node_event_mac_address',
    'send_rack_event',
    ]

from collections import namedtuple
from logging import (
    DEBUG,
    ERROR,
    INFO,
    WARN,
)

from provisioningserver.logger import (
    get_maas_logger,
    LegacyLogger,
)
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
from provisioningserver.utils.env import get_maas_id
from provisioningserver.utils.twisted import (
    asynchronous,
    callOut,
    DeferredValue,
    FOREVER,
    suppress,
)
from twisted.internet.defer import (
    maybeDeferred,
    succeed,
)


maaslog = get_maas_logger("events")
log = LegacyLogger()

# AUDIT event logging level
AUDIT = 0


class EVENT_TYPES:
    # Power-related events.
    NODE_POWER_ON_STARTING = 'NODE_POWER_ON_STARTING'
    NODE_POWER_OFF_STARTING = 'NODE_POWER_OFF_STARTING'
    NODE_POWER_CYCLE_STARTING = 'NODE_POWER_CYCLE_STARTING'
    NODE_POWERED_ON = 'NODE_POWERED_ON'
    NODE_POWERED_OFF = 'NODE_POWERED_OFF'
    NODE_POWER_ON_FAILED = 'NODE_POWER_ON_FAILED'
    NODE_POWER_OFF_FAILED = 'NODE_POWER_OFF_FAILED'
    NODE_POWER_CYCLE_FAILED = 'NODE_POWER_CYCLE_FAILED'
    NODE_POWER_QUERIED = 'NODE_POWER_QUERIED'
    NODE_POWER_QUERIED_DEBUG = 'NODE_POWER_QUERIED_DEBUG'
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
    NODE_COMMISSIONING_EVENT_FAILED = "NODE_COMMISSIONING_EVENT_FAILED"
    NODE_INSTALL_EVENT = "NODE_INSTALL_EVENT"
    NODE_INSTALL_EVENT_FAILED = "NODE_INSTALL_EVENT_FAILED"
    NODE_POST_INSTALL_EVENT_FAILED = "NODE_POST_INSTALL_EVENT_FAILED"
    NODE_ENTERING_RESCUE_MODE_EVENT = "NODE_ENTERING_RESCUE_MODE_EVENT"
    NODE_ENTERING_RESCUE_MODE_EVENT_FAILED = (
        "NODE_ENTERING_RESCUE_MODE_EVENT_FAILED")
    NODE_EXITING_RESCUE_MODE_EVENT = "NODE_EXITING_RESCUE_MODE_EVENT"
    NODE_EXITING_RESCUE_MODE_EVENT_FAILED = (
        "NODE_EXITING_RESCUE_MODE_EVENT_FAILED")
    # Node user request events
    REQUEST_NODE_START_COMMISSIONING = "REQUEST_NODE_START_COMMISSIONING"
    REQUEST_NODE_ABORT_COMMISSIONING = "REQUEST_NODE_ABORT_COMMISSIONING"
    REQUEST_NODE_START_TESTING = "REQUEST_NODE_START_TESTING"
    REQUEST_NODE_ABORT_TESTING = "REQUEST_NODE_ABORT_TESTING"
    REQUEST_NODE_OVERRIDE_FAILED_TESTING = (
        "REQUEST_NODE_OVERRIDE_FAILED_TESTING")
    REQUEST_NODE_ABORT_DEPLOYMENT = "REQUEST_NODE_ABORT_DEPLOYMENT"
    REQUEST_NODE_ACQUIRE = "REQUEST_NODE_ACQUIRE"
    REQUEST_NODE_ERASE_DISK = "REQUEST_NODE_ERASE_DISK"
    REQUEST_NODE_ABORT_ERASE_DISK = "REQUEST_NODE_ABORT_ERASE_DISK"
    REQUEST_NODE_RELEASE = "REQUEST_NODE_RELEASE"
    REQUEST_NODE_MARK_FAILED = "REQUEST_NODE_MARK_FAILED"
    REQUEST_NODE_MARK_FAILED_SYSTEM = "REQUEST_NODE_MARK_FAILED_SYSTEM"
    REQUEST_NODE_MARK_BROKEN = "REQUEST_NODE_MARK_BROKEN"
    REQUEST_NODE_MARK_FIXED = "REQUEST_NODE_MARK_FIXED"
    REQUEST_NODE_LOCK = "REQUEST_NODE_LOCK"
    REQUEST_NODE_UNLOCK = "REQUEST_NODE_UNLOCK"
    REQUEST_NODE_START_DEPLOYMENT = "REQUEST_NODE_START_DEPLOYMENT"
    REQUEST_NODE_START = "REQUEST_NODE_START"
    REQUEST_NODE_STOP = "REQUEST_NODE_STOP"
    REQUEST_NODE_START_RESCUE_MODE = "REQUEST_NODE_START_RESCUE_MODE"
    REQUEST_NODE_STOP_RESCUE_MODE = "REQUEST_NODE_STOP_RESCUE_MODE"
    # Rack controller request events
    REQUEST_CONTROLLER_REFRESH = "REQUEST_CONTROLLER_REFRESH"
    REQUEST_RACK_CONTROLLER_ADD_CHASSIS = "REQUEST_RACK_CONTROLLER_ADD_CHASSIS"
    # Rack import events
    RACK_IMPORT_WARNING = "RACK_IMPORT_WARNING"
    RACK_IMPORT_ERROR = "RACK_IMPORT_ERROR"
    RACK_IMPORT_INFO = "RACK_IMPORT_INFO"
    # Region import events
    REGION_IMPORT_WARNING = "REGION_IMPORT_WARNING"
    REGION_IMPORT_ERROR = "REGION_IMPORT_ERROR"
    REGION_IMPORT_INFO = "REGION_IMPORT_INFO"
    # Script result storage and lookup events
    SCRIPT_RESULT_ERROR = "SCRIPT_RESULT_ERROR"
    # Authorisation events
    AUTHORISATION = "AUTHORISATION"
    # Settings events
    SETTINGS = "SETTINGS"
    # Node events
    NODE = "NODE"
    # Images events
    IMAGES = "IMAGES"
    # Pod events
    POD = "POD"
    # Networking events
    NETWORKING = "NETWORKING"
    # Zones events
    ZONES = "ZONES"


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
    EVENT_TYPES.NODE_POWER_CYCLE_STARTING: EventDetail(
        description="Power cycling node",
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
    EVENT_TYPES.NODE_POWER_CYCLE_FAILED: EventDetail(
        description="Failed to power cycle node",
        level=ERROR,
    ),
    EVENT_TYPES.NODE_POWER_QUERIED: EventDetail(
        description="Queried node's BMC",
        level=INFO,
    ),
    EVENT_TYPES.NODE_POWER_QUERIED_DEBUG: EventDetail(
        description="Queried node's BMC",
        level=DEBUG,
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
    EVENT_TYPES.NODE_COMMISSIONING_EVENT_FAILED: EventDetail(
        description="Node commissioning failure",
        level=ERROR,
    ),
    EVENT_TYPES.NODE_INSTALL_EVENT: EventDetail(
        description="Node installation",
        level=DEBUG,
    ),
    EVENT_TYPES.NODE_INSTALL_EVENT_FAILED: EventDetail(
        description="Node installation failure",
        level=ERROR,
    ),
    EVENT_TYPES.NODE_POST_INSTALL_EVENT_FAILED: EventDetail(
        description="Node post-installation failure",
        level=ERROR,
    ),
    EVENT_TYPES.NODE_ENTERING_RESCUE_MODE_EVENT: EventDetail(
        description="Node entering rescue mode",
        level=DEBUG,
    ),
    EVENT_TYPES.NODE_ENTERING_RESCUE_MODE_EVENT_FAILED: EventDetail(
        description="Node entering rescue mode failure",
        level=ERROR,
    ),
    EVENT_TYPES.NODE_EXITING_RESCUE_MODE_EVENT: EventDetail(
        description="Node exiting rescue mode",
        level=DEBUG,
    ),
    EVENT_TYPES.NODE_EXITING_RESCUE_MODE_EVENT_FAILED: EventDetail(
        description="Node exiting rescue mode failure",
        level=ERROR,
    ),
    EVENT_TYPES.REQUEST_NODE_START_COMMISSIONING: EventDetail(
        description="User starting node commissioning",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_ABORT_COMMISSIONING: EventDetail(
        description="User aborting node commissioning",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_START_TESTING: EventDetail(
        description="User starting node testing",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_ABORT_TESTING: EventDetail(
        description="User aborting node testing",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_OVERRIDE_FAILED_TESTING: EventDetail(
        description="User overrode 'Failed testing' status",
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
    EVENT_TYPES.REQUEST_NODE_MARK_FAILED_SYSTEM: EventDetail(
        description="Marking node failed",
        level=ERROR,
    ),
    EVENT_TYPES.REQUEST_NODE_MARK_BROKEN: EventDetail(
        description="User marking node broken",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_MARK_FIXED: EventDetail(
        description="User marking node fixed",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_LOCK: EventDetail(
        description="User locking node",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_UNLOCK: EventDetail(
        description="User unlocking node",
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
    EVENT_TYPES.REQUEST_NODE_START_RESCUE_MODE: EventDetail(
        description="User starting rescue mode",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_NODE_STOP_RESCUE_MODE: EventDetail(
        description="User stopping rescue mode",
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_CONTROLLER_REFRESH: EventDetail(
        description=("Starting refresh of controller hardware and networking "
                     "information"),
        level=INFO,
    ),
    EVENT_TYPES.REQUEST_RACK_CONTROLLER_ADD_CHASSIS: EventDetail(
        description=("Querying chassis and enlisting all machines"),
        level=INFO,
    ),
    EVENT_TYPES.RACK_IMPORT_WARNING: EventDetail(
        description=("Rack import warning"),
        level=WARN,
    ),
    EVENT_TYPES.RACK_IMPORT_ERROR: EventDetail(
        description=("Rack import error"),
        level=ERROR,
    ),
    EVENT_TYPES.RACK_IMPORT_INFO: EventDetail(
        description=("Rack import info"),
        level=INFO,
    ),
    EVENT_TYPES.REGION_IMPORT_WARNING: EventDetail(
        description=("Region import warning"),
        level=WARN,
    ),
    EVENT_TYPES.REGION_IMPORT_ERROR: EventDetail(
        description=("Region import error"),
        level=ERROR,
    ),
    EVENT_TYPES.REGION_IMPORT_INFO: EventDetail(
        description=("Region import info"),
        level=INFO,
    ),
    EVENT_TYPES.SCRIPT_RESULT_ERROR: EventDetail(
        description=("Script result lookup or storage error"),
        level=ERROR,
    ),
    EVENT_TYPES.AUTHORISATION: EventDetail(
        description=("Authorisation"),
        level=AUDIT,
    ),
    EVENT_TYPES.SETTINGS: EventDetail(
        description=("Settings"),
        level=AUDIT,
    ),
    EVENT_TYPES.NODE: EventDetail(
        description=("Node"),
        level=AUDIT,
    ),
    EVENT_TYPES.IMAGES: EventDetail(
        description=("Images"),
        level=AUDIT,
    ),
    EVENT_TYPES.POD: EventDetail(
        description=("Pod"),
        level=AUDIT,
    ),
    EVENT_TYPES.NETWORKING: EventDetail(
        description=("Networking"),
        level=AUDIT,
    ),
    EVENT_TYPES.ZONES: EventDetail(
        description=("Zones"),
        level=AUDIT,
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
        d.addErrback(suppress, NoSuchNode)

        return d


# Singleton.
nodeEventHub = NodeEventHub()


@asynchronous
def send_node_event(event_type, system_id, hostname, description=''):
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
def send_node_event_mac_address(event_type, mac_address, description=''):
    """Send the given node event to the region for the given mac address.

    :param event_type: The type of the event.
    :type event_type: unicode
    :param mac_address: The MAC Address of the node of the event.
    :type mac_address: unicode
    :param description: An optional description of the event.
    :type description: unicode
    """
    return nodeEventHub.logByMAC(event_type, mac_address, description)


@asynchronous
def send_rack_event(event_type, description=''):
    """Send an event about the running rack to the region.

    :param event_type: The type of the event.
    :type event_type: unicode
    :param description: An optional description of the event.
    :type description: unicode
    """
    return nodeEventHub.logByID(event_type, get_maas_id(), description)


@asynchronous(timeout=FOREVER)
def try_send_rack_event(event_type, description=''):
    """Try to send a rack event to the region.

    Log something locally if this fails but otherwise supress all
    failures.
    """
    d = send_rack_event(event_type, description)
    d.addErrback(
        log.err, "Failure sending rack event to region: %s - %s" %
        (event_type, description))
    return d
