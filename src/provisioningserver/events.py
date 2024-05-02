# Copyright 2014-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Event catalog."""

from collections import namedtuple
from logging import DEBUG, ERROR, INFO, WARN

from twisted.internet.defer import maybeDeferred, succeed

from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.exceptions import NoSuchEventType, NoSuchNode
from provisioningserver.rpc.region import (
    RegisterEventType,
    SendEvent,
    SendEventIPAddress,
    SendEventMACAddress,
)
from provisioningserver.utils.env import MAAS_ID
from provisioningserver.utils.twisted import (
    asynchronous,
    callOut,
    DeferredValue,
    FOREVER,
    suppress,
)

maaslog = get_maas_logger("events")
log = LegacyLogger()

# AUDIT event logging level
AUDIT = 0


class EVENT_TYPES:
    # Power-related events.
    NODE_POWER_ON_STARTING = "NODE_POWER_ON_STARTING"
    NODE_POWER_OFF_STARTING = "NODE_POWER_OFF_STARTING"
    NODE_POWER_CYCLE_STARTING = "NODE_POWER_CYCLE_STARTING"
    NODE_POWERED_ON = "NODE_POWERED_ON"
    NODE_POWERED_OFF = "NODE_POWERED_OFF"
    NODE_POWER_ON_FAILED = "NODE_POWER_ON_FAILED"
    NODE_POWER_OFF_FAILED = "NODE_POWER_OFF_FAILED"
    NODE_POWER_CYCLE_FAILED = "NODE_POWER_CYCLE_FAILED"
    NODE_POWER_QUERY_FAILED = "NODE_POWER_QUERY_FAILED"
    # PXE request event.
    NODE_PXE_REQUEST = "NODE_PXE_REQUEST"
    # TFTP request event.
    NODE_TFTP_REQUEST = "NODE_TFTP_REQUEST"
    # HTTP request event.
    NODE_HTTP_REQUEST = "NODE_HTTP_REQUEST"
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
        "NODE_ENTERING_RESCUE_MODE_EVENT_FAILED"
    )
    NODE_EXITING_RESCUE_MODE_EVENT = "NODE_EXITING_RESCUE_MODE_EVENT"
    NODE_EXITING_RESCUE_MODE_EVENT_FAILED = (
        "NODE_EXITING_RESCUE_MODE_EVENT_FAILED"
    )
    # Node hardware sync events
    NODE_HARDWARE_SYNC_BMC = "NODE_HARDWARE_SYNC_BMC"
    NODE_HARDWARE_SYNC_BLOCK_DEVICE = "NODE_HARDWARE_SYNC_BLOCK_DEVICE"
    NODE_HARDWARE_SYNC_CPU = "NODE_HARDWARE_SYNC_CPU"
    NODE_HARDWARE_SYNC_INTERFACE = "NODE_HARDWARE_SYNC_INTERFACE"
    NODE_HARDWARE_SYNC_MEMORY = "NODE_HARDWARE_SYNC_MEMORY"
    NODE_HARDWARE_SYNC_PCI_DEVICE = "NODE_HARDWARE_SYNC_PCI_DEVICE"
    NODE_HARDWARE_SYNC_USB_DEVICE = "NODE_HARDWARE_SYNC_USB_DEVICE"
    # Node user request events
    REQUEST_NODE_START_COMMISSIONING = "REQUEST_NODE_START_COMMISSIONING"
    REQUEST_NODE_ABORT_COMMISSIONING = "REQUEST_NODE_ABORT_COMMISSIONING"
    REQUEST_NODE_START_TESTING = "REQUEST_NODE_START_TESTING"
    REQUEST_NODE_ABORT_TESTING = "REQUEST_NODE_ABORT_TESTING"
    REQUEST_NODE_OVERRIDE_FAILED_TESTING = (
        "REQUEST_NODE_OVERRIDE_FAILED_TESTING"
    )
    REQUEST_NODE_ABORT_DEPLOYMENT = "REQUEST_NODE_ABORT_DEPLOYMENT"
    REQUEST_NODE_ACQUIRE = "REQUEST_NODE_ACQUIRE"
    REQUEST_NODE_ERASE_DISK = "REQUEST_NODE_ERASE_DISK"
    REQUEST_NODE_ABORT_ERASE_DISK = "REQUEST_NODE_ABORT_ERASE_DISK"
    REQUEST_NODE_RELEASE = "REQUEST_NODE_RELEASE"
    REQUEST_NODE_MARK_FAILED = "REQUEST_NODE_MARK_FAILED"
    REQUEST_NODE_MARK_FAILED_SYSTEM = "REQUEST_NODE_MARK_FAILED_SYSTEM"
    REQUEST_NODE_MARK_BROKEN = "REQUEST_NODE_MARK_BROKEN"
    REQUEST_NODE_MARK_BROKEN_SYSTEM = "REQUEST_NODE_MARK_BROKEN_SYSTEM"
    REQUEST_NODE_MARK_FIXED = "REQUEST_NODE_MARK_FIXED"
    REQUEST_NODE_MARK_FIXED_SYSTEM = "REQUEST_NODE_MARK_FIXED_SYSTEM"
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
    # Tag events
    TAG = "TAG"
    # Status message events
    CONFIGURING_STORAGE = "CONFIGURING_STORAGE"
    INSTALLING_OS = "INSTALLING_OS"
    CONFIGURING_OS = "CONFIGURING_OS"
    REBOOTING = "REBOOTING"
    PERFORMING_PXE_BOOT = "PERFORMING_PXE_BOOT"
    LOADING_EPHEMERAL = "LOADING_EPHEMERAL"
    NEW = "NEW"
    COMMISSIONING = "COMMISSIONING"
    FAILED_COMMISSIONING = "FAILED_COMMISSIONING"
    TESTING = "TESTING"
    FAILED_TESTING = "FAILED_TESTING"
    READY = "READY"
    DEPLOYING = "DEPLOYING"
    DEPLOYED = "DEPLOYED"
    IMAGE_DEPLOYED = "IMAGE_DEPLOYED"
    RELEASING = "RELEASING"
    RELEASED = "RELEASED"
    ENTERING_RESCUE_MODE = "ENTERING_RESCUE_MODE"
    RESCUE_MODE = "RESCUE_MODE"
    FAILED_EXITING_RESCUE_MODE = "FAILED_EXITING_RESCUE_MODE"
    EXITED_RESCUE_MODE = "EXITED_RESCUE_MODE"
    GATHERING_INFO = "GATHERING_INFO"
    RUNNING_TEST = "RUNNING_TEST"
    SCRIPT_DID_NOT_COMPLETE = "SCRIPT_DID_NOT_COMPLETE"
    SCRIPT_RESULT_CHANGED_STATUS = "SCRIPT_RESULT_CHANGED_STATUS"
    ABORTED_DISK_ERASING = "ABORTED_DISK_ERASING"
    ABORTED_COMMISSIONING = "ABORTED_COMMISSIONING"
    ABORTED_DEPLOYMENT = "ABORTED_DEPLOYMENT"
    ABORTED_TESTING = "ABORTED_TESTING"


# Used to create new events used for the machine's status.
# The keys are the messages sent from cloud-init and curtin
# to the metadataserver.
EVENT_STATUS_MESSAGES = {
    "cmd-install/stage-partitioning": EVENT_TYPES.CONFIGURING_STORAGE,
    "cmd-install/stage-extract": EVENT_TYPES.INSTALLING_OS,
    "cmd-install/stage-curthooks": EVENT_TYPES.CONFIGURING_OS,
}


EventDetail = namedtuple("EventDetail", ("description", "level"))


EVENT_DETAILS = {
    # Event type -> EventDetail mapping.
    EVENT_TYPES.NODE_POWER_ON_STARTING: EventDetail(
        description="Powering on", level=INFO
    ),
    EVENT_TYPES.NODE_POWER_OFF_STARTING: EventDetail(
        description="Powering off", level=INFO
    ),
    EVENT_TYPES.NODE_POWER_CYCLE_STARTING: EventDetail(
        description="Power cycling", level=INFO
    ),
    EVENT_TYPES.NODE_POWERED_ON: EventDetail(
        description="Node powered on", level=DEBUG
    ),
    EVENT_TYPES.NODE_POWERED_OFF: EventDetail(
        description="Node powered off", level=DEBUG
    ),
    EVENT_TYPES.NODE_POWER_ON_FAILED: EventDetail(
        description="Failed to power on node", level=ERROR
    ),
    EVENT_TYPES.NODE_POWER_OFF_FAILED: EventDetail(
        description="Failed to power off node", level=ERROR
    ),
    EVENT_TYPES.NODE_POWER_CYCLE_FAILED: EventDetail(
        description="Failed to power cycle node", level=ERROR
    ),
    EVENT_TYPES.NODE_POWER_QUERY_FAILED: EventDetail(
        description="Failed to query node's BMC", level=WARN
    ),
    EVENT_TYPES.NODE_TFTP_REQUEST: EventDetail(
        description="TFTP Request", level=DEBUG
    ),
    EVENT_TYPES.NODE_HTTP_REQUEST: EventDetail(
        description="HTTP Request", level=DEBUG
    ),
    EVENT_TYPES.NODE_PXE_REQUEST: EventDetail(
        description="PXE Request", level=DEBUG
    ),
    EVENT_TYPES.NODE_INSTALLATION_FINISHED: EventDetail(
        description="Installation complete", level=DEBUG
    ),
    EVENT_TYPES.NODE_CHANGED_STATUS: EventDetail(
        description="Node changed status", level=DEBUG
    ),
    EVENT_TYPES.NODE_STATUS_EVENT: EventDetail(
        description="Node status event", level=DEBUG
    ),
    EVENT_TYPES.NODE_COMMISSIONING_EVENT: EventDetail(
        description="Node commissioning", level=DEBUG
    ),
    EVENT_TYPES.NODE_COMMISSIONING_EVENT_FAILED: EventDetail(
        description="Node commissioning failure", level=ERROR
    ),
    EVENT_TYPES.NODE_INSTALL_EVENT: EventDetail(
        description="Node installation", level=DEBUG
    ),
    EVENT_TYPES.NODE_INSTALL_EVENT_FAILED: EventDetail(
        description="Node installation failure", level=ERROR
    ),
    EVENT_TYPES.NODE_POST_INSTALL_EVENT_FAILED: EventDetail(
        description="Node post-installation failure", level=ERROR
    ),
    EVENT_TYPES.NODE_ENTERING_RESCUE_MODE_EVENT: EventDetail(
        description="Node entering rescue mode", level=DEBUG
    ),
    EVENT_TYPES.NODE_ENTERING_RESCUE_MODE_EVENT_FAILED: EventDetail(
        description="Node entering rescue mode failure", level=ERROR
    ),
    EVENT_TYPES.NODE_EXITING_RESCUE_MODE_EVENT: EventDetail(
        description="Node exiting rescue mode", level=DEBUG
    ),
    EVENT_TYPES.NODE_EXITING_RESCUE_MODE_EVENT_FAILED: EventDetail(
        description="Node exiting rescue mode failure", level=ERROR
    ),
    EVENT_TYPES.NODE_HARDWARE_SYNC_BMC: EventDetail(
        description="Node BMC hardware sync state change", level=INFO
    ),
    EVENT_TYPES.NODE_HARDWARE_SYNC_BLOCK_DEVICE: EventDetail(
        description="Node Block Device hardware sync state change", level=INFO
    ),
    EVENT_TYPES.NODE_HARDWARE_SYNC_CPU: EventDetail(
        description="Node CPU hardware sync state change", level=INFO
    ),
    EVENT_TYPES.NODE_HARDWARE_SYNC_INTERFACE: EventDetail(
        description="Node Interface hardware sync state change", level=INFO
    ),
    EVENT_TYPES.NODE_HARDWARE_SYNC_MEMORY: EventDetail(
        description="Node Memory hardware sync state change", level=INFO
    ),
    EVENT_TYPES.NODE_HARDWARE_SYNC_PCI_DEVICE: EventDetail(
        description="Node PCI Device hardware sync state change", level=INFO
    ),
    EVENT_TYPES.NODE_HARDWARE_SYNC_USB_DEVICE: EventDetail(
        description="Node USB Device hardware sync state chage", level=INFO
    ),
    EVENT_TYPES.REQUEST_NODE_START_COMMISSIONING: EventDetail(
        description="User starting node commissioning", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_ABORT_COMMISSIONING: EventDetail(
        description="User aborting node commissioning", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_START_TESTING: EventDetail(
        description="User starting node testing", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_ABORT_TESTING: EventDetail(
        description="User aborting node testing", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_OVERRIDE_FAILED_TESTING: EventDetail(
        description="User overrode 'Failed testing' status", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_ABORT_DEPLOYMENT: EventDetail(
        description="User aborting deployment", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_ACQUIRE: EventDetail(
        description="User acquiring node", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_ERASE_DISK: EventDetail(
        description="User erasing disk", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_ABORT_ERASE_DISK: EventDetail(
        description="User aborting disk erase", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_RELEASE: EventDetail(
        description="User releasing node", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_MARK_FAILED: EventDetail(
        description="User marking node failed", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_MARK_FAILED_SYSTEM: EventDetail(
        description="Marking node failed", level=ERROR
    ),
    EVENT_TYPES.REQUEST_NODE_MARK_BROKEN: EventDetail(
        description="User marking node broken", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_MARK_BROKEN_SYSTEM: EventDetail(
        description="Marking node broken", level=ERROR
    ),
    EVENT_TYPES.REQUEST_NODE_MARK_FIXED: EventDetail(
        description="User marking node fixed", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_MARK_FIXED_SYSTEM: EventDetail(
        description="Marking node fixed", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_LOCK: EventDetail(
        description="User locking node", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_UNLOCK: EventDetail(
        description="User unlocking node", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_START_DEPLOYMENT: EventDetail(
        description="User starting deployment", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_START: EventDetail(
        description="User powering up node", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_STOP: EventDetail(
        description="User powering down node", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_START_RESCUE_MODE: EventDetail(
        description="User starting rescue mode", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_NODE_STOP_RESCUE_MODE: EventDetail(
        description="User stopping rescue mode", level=DEBUG
    ),
    EVENT_TYPES.REQUEST_CONTROLLER_REFRESH: EventDetail(
        description=(
            "Starting refresh of controller hardware and networking "
            "information"
        ),
        level=DEBUG,
    ),
    EVENT_TYPES.REQUEST_RACK_CONTROLLER_ADD_CHASSIS: EventDetail(
        description="Querying chassis and enlisting all machines", level=DEBUG
    ),
    EVENT_TYPES.RACK_IMPORT_WARNING: EventDetail(
        description="Rack import warning", level=WARN
    ),
    EVENT_TYPES.RACK_IMPORT_ERROR: EventDetail(
        description="Rack import error", level=ERROR
    ),
    EVENT_TYPES.RACK_IMPORT_INFO: EventDetail(
        description="Rack import info", level=DEBUG
    ),
    EVENT_TYPES.REGION_IMPORT_WARNING: EventDetail(
        description="Region import warning", level=WARN
    ),
    EVENT_TYPES.REGION_IMPORT_ERROR: EventDetail(
        description="Region import error", level=ERROR
    ),
    EVENT_TYPES.REGION_IMPORT_INFO: EventDetail(
        description="Region import info", level=DEBUG
    ),
    EVENT_TYPES.SCRIPT_RESULT_ERROR: EventDetail(
        description="Script result lookup or storage error", level=ERROR
    ),
    EVENT_TYPES.AUTHORISATION: EventDetail(
        description="Authorisation", level=AUDIT
    ),
    EVENT_TYPES.SETTINGS: EventDetail(description="Settings", level=AUDIT),
    EVENT_TYPES.NODE: EventDetail(description="Node", level=AUDIT),
    EVENT_TYPES.IMAGES: EventDetail(description="Images", level=AUDIT),
    EVENT_TYPES.POD: EventDetail(description="Pod", level=AUDIT),
    EVENT_TYPES.TAG: EventDetail(description="Tag", level=AUDIT),
    EVENT_TYPES.NETWORKING: EventDetail(description="Networking", level=AUDIT),
    EVENT_TYPES.ZONES: EventDetail(description="Zones", level=AUDIT),
    EVENT_TYPES.CONFIGURING_STORAGE: EventDetail(
        description="Configuring storage", level=INFO
    ),
    EVENT_TYPES.INSTALLING_OS: EventDetail(
        description="Installing OS", level=INFO
    ),
    EVENT_TYPES.CONFIGURING_OS: EventDetail(
        description="Configuring OS", level=INFO
    ),
    EVENT_TYPES.REBOOTING: EventDetail(description="Rebooting", level=INFO),
    EVENT_TYPES.PERFORMING_PXE_BOOT: EventDetail(
        description="Performing PXE boot", level=INFO
    ),
    EVENT_TYPES.LOADING_EPHEMERAL: EventDetail(
        description="Loading ephemeral", level=INFO
    ),
    EVENT_TYPES.NEW: EventDetail(description="New", level=INFO),
    EVENT_TYPES.COMMISSIONING: EventDetail(
        description="Commissioning", level=INFO
    ),
    EVENT_TYPES.FAILED_COMMISSIONING: EventDetail(
        description="Failed commissioning", level=INFO
    ),
    EVENT_TYPES.TESTING: EventDetail(description="Testing", level=INFO),
    EVENT_TYPES.FAILED_TESTING: EventDetail(
        description="Failed testing", level=INFO
    ),
    EVENT_TYPES.READY: EventDetail(description="Ready", level=INFO),
    EVENT_TYPES.DEPLOYING: EventDetail(description="Deploying", level=INFO),
    EVENT_TYPES.DEPLOYED: EventDetail(description="Deployed", level=INFO),
    EVENT_TYPES.IMAGE_DEPLOYED: EventDetail(
        description="Image Deployed", level=INFO
    ),
    EVENT_TYPES.RELEASING: EventDetail(description="Releasing", level=INFO),
    EVENT_TYPES.RELEASED: EventDetail(description="Released", level=INFO),
    EVENT_TYPES.ENTERING_RESCUE_MODE: EventDetail(
        description="Entering rescue mode", level=INFO
    ),
    EVENT_TYPES.RESCUE_MODE: EventDetail(
        description="Rescue mode", level=INFO
    ),
    EVENT_TYPES.FAILED_EXITING_RESCUE_MODE: EventDetail(
        description="Failed exiting rescue mode", level=INFO
    ),
    EVENT_TYPES.EXITED_RESCUE_MODE: EventDetail(
        description="Exited rescue mode", level=INFO
    ),
    EVENT_TYPES.GATHERING_INFO: EventDetail(
        description="Gathering information", level=INFO
    ),
    EVENT_TYPES.RUNNING_TEST: EventDetail(
        description="Running test", level=INFO
    ),
    EVENT_TYPES.SCRIPT_DID_NOT_COMPLETE: EventDetail(
        description="Script", level=INFO
    ),
    EVENT_TYPES.SCRIPT_RESULT_CHANGED_STATUS: EventDetail(
        description="Script result", level=DEBUG
    ),
    EVENT_TYPES.ABORTED_DISK_ERASING: EventDetail(
        description="Aborted disk erasing", level=INFO
    ),
    EVENT_TYPES.ABORTED_COMMISSIONING: EventDetail(
        description="Aborted commissioning", level=INFO
    ),
    EVENT_TYPES.ABORTED_DEPLOYMENT: EventDetail(
        description="Aborted deployment", level=INFO
    ),
    EVENT_TYPES.ABORTED_TESTING: EventDetail(
        description="Aborted testing", level=INFO
    ),
}


class NodeEventHub:
    """Singleton for sending node events to the region.

    This automatically ensures that the event type is registered before
    sending logs to the region.
    """

    def __init__(self):
        super().__init__()
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
                RegisterEventType,
                name=event_type,
                level=details.level,
                description=details.description,
            )

        d = maybeDeferred(getRegionClient).addCallback(register)
        # Whatever happens, we are now done registering.
        d.addBoth(callOut, self._types_registering.pop, event_type)
        # On success, record that the event type has been registered. On
        # failure, ensure that the set of registered event types does NOT
        # contain the event type.
        d.addCallbacks(
            callback=callOut,
            callbackArgs=(self._types_registered.add, event_type),
            errback=callOut,
            errbackArgs=(self._types_registered.discard, event_type),
        )
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
                SendEvent,
                system_id=system_id,
                type_name=event_type,
                description=description,
            )

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
                SendEventMACAddress,
                mac_address=mac_address,
                type_name=event_type,
                description=description,
            )

        d = self.ensureEventTypeRegistered(event_type).addCallback(send)
        d.addErrback(self._checkEventTypeRegistered, event_type)

        # Suppress NoSuchNode. This happens during enlistment because the
        # region does not yet know of the node; it's quite normal. Logging
        # tracebacks telling us about it is not useful. Perhaps the region
        # should store these logs anyway. Then, if and when the node is
        # enlisted, logs prior to enlistment can be seen.
        d.addErrback(suppress, NoSuchNode)

        return d

    @asynchronous
    def logByIP(self, event_type, ip_address, description=""):
        """Send the given node event to the region.

        The node is specified by its MAC address.

        :param event_type: The type of the event.
        :type event_type: unicode
        :param ip_address: The IP address of the node.
        :type ip_address: unicode
        :param description: An optional description of the event.
        :type description: unicode
        """

        def send(_):
            client = getRegionClient()
            return client(
                SendEventIPAddress,
                ip_address=ip_address,
                type_name=event_type,
                description=description,
            )

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
def send_node_event(event_type, system_id, hostname, description=""):
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
def send_node_event_mac_address(event_type, mac_address, description=""):
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
def send_node_event_ip_address(event_type, ip_address, description=""):
    """Send the given node event to the region for the given IP address.

    :param event_type: The type of the event.
    :type event_type: unicode
    :param ip_address: The IP Address of the node of the event.
    :type ip_address: unicode
    :param description: An optional description of the event.
    :type description: unicode
    """
    return nodeEventHub.logByIP(event_type, ip_address, description)


@asynchronous
def send_rack_event(event_type, description=""):
    """Send an event about the running rack to the region.

    :param event_type: The type of the event.
    :type event_type: unicode
    :param description: An optional description of the event.
    :type description: unicode
    """
    return nodeEventHub.logByID(event_type, MAAS_ID.get(), description)


@asynchronous(timeout=FOREVER)
def try_send_rack_event(event_type, description=""):
    """Try to send a rack event to the region.

    Log something locally if this fails but otherwise supress all
    failures.
    """
    d = send_rack_event(event_type, description)
    d.addErrback(
        log.err,
        "Failure sending rack event to region: %s - %s"
        % (event_type, description),
    )
    return d
