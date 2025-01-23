# Copyright 2014-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Event catalog."""

from twisted.internet.defer import maybeDeferred, succeed

from maascommon.enums.events import EventTypeEnum
from maascommon.events import EVENT_DETAILS_MAP
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


class EVENT_TYPES:
    # Power-related events.
    NODE_POWERED_ON = EventTypeEnum.NODE_POWERED_ON.value
    NODE_POWERED_OFF = EventTypeEnum.NODE_POWERED_OFF.value
    NODE_POWER_ON_FAILED = EventTypeEnum.NODE_POWER_ON_FAILED.value
    NODE_POWER_OFF_FAILED = EventTypeEnum.NODE_POWER_OFF_FAILED.value
    NODE_POWER_CYCLE_FAILED = EventTypeEnum.NODE_POWER_CYCLE_FAILED.value
    NODE_POWER_QUERY_FAILED = EventTypeEnum.NODE_POWER_QUERY_FAILED.value
    # PXE request event.
    NODE_PXE_REQUEST = EventTypeEnum.NODE_PXE_REQUEST.value
    # TFTP request event.
    NODE_TFTP_REQUEST = EventTypeEnum.NODE_TFTP_REQUEST.value
    # HTTP request event.
    NODE_HTTP_REQUEST = EventTypeEnum.NODE_HTTP_REQUEST.value
    # Other installation-related event types.
    NODE_INSTALLATION_FINISHED = EventTypeEnum.NODE_INSTALLATION_FINISHED.value
    # Node status transition event.
    NODE_CHANGED_STATUS = EventTypeEnum.NODE_CHANGED_STATUS.value
    # Node status events
    NODE_STATUS_EVENT = EventTypeEnum.NODE_STATUS_EVENT.value
    NODE_COMMISSIONING_EVENT = EventTypeEnum.NODE_COMMISSIONING_EVENT.value
    NODE_COMMISSIONING_EVENT_FAILED = (
        EventTypeEnum.NODE_COMMISSIONING_EVENT_FAILED.value
    )
    NODE_INSTALL_EVENT = EventTypeEnum.NODE_INSTALL_EVENT.value
    NODE_INSTALL_EVENT_FAILED = EventTypeEnum.NODE_INSTALL_EVENT_FAILED.value
    NODE_POST_INSTALL_EVENT_FAILED = (
        EventTypeEnum.NODE_POST_INSTALL_EVENT_FAILED.value
    )
    NODE_DISKS_ERASED = EventTypeEnum.NODE_DISKS_ERASED.value
    NODE_ENTERING_RESCUE_MODE_EVENT = (
        EventTypeEnum.NODE_ENTERING_RESCUE_MODE_EVENT.value
    )
    NODE_ENTERING_RESCUE_MODE_EVENT_FAILED = (
        EventTypeEnum.NODE_ENTERING_RESCUE_MODE_EVENT_FAILED.value
    )
    NODE_EXITING_RESCUE_MODE_EVENT = (
        EventTypeEnum.NODE_EXITING_RESCUE_MODE_EVENT.value
    )
    NODE_EXITING_RESCUE_MODE_EVENT_FAILED = (
        EventTypeEnum.NODE_EXITING_RESCUE_MODE_EVENT_FAILED.value
    )
    # Node hardware sync events
    NODE_HARDWARE_SYNC_BMC = EventTypeEnum.NODE_HARDWARE_SYNC_BMC.value
    NODE_HARDWARE_SYNC_BLOCK_DEVICE = (
        EventTypeEnum.NODE_HARDWARE_SYNC_BLOCK_DEVICE.value
    )
    NODE_HARDWARE_SYNC_CPU = EventTypeEnum.NODE_HARDWARE_SYNC_CPU.value
    NODE_HARDWARE_SYNC_INTERFACE = (
        EventTypeEnum.NODE_HARDWARE_SYNC_INTERFACE.value
    )
    NODE_HARDWARE_SYNC_MEMORY = EventTypeEnum.NODE_HARDWARE_SYNC_MEMORY.value
    NODE_HARDWARE_SYNC_PCI_DEVICE = (
        EventTypeEnum.NODE_HARDWARE_SYNC_PCI_DEVICE.value
    )
    NODE_HARDWARE_SYNC_USB_DEVICE = (
        EventTypeEnum.NODE_HARDWARE_SYNC_USB_DEVICE.value
    )
    NODE_RELEASE_SCRIPTS_OK = EventTypeEnum.NODE_RELEASE_SCRIPTS_OK.value
    # Node user request events
    REQUEST_NODE_START_COMMISSIONING = (
        EventTypeEnum.REQUEST_NODE_START_COMMISSIONING.value
    )
    REQUEST_NODE_ABORT_COMMISSIONING = (
        EventTypeEnum.REQUEST_NODE_ABORT_COMMISSIONING.value
    )
    REQUEST_NODE_START_TESTING = EventTypeEnum.REQUEST_NODE_START_TESTING.value
    REQUEST_NODE_ABORT_TESTING = EventTypeEnum.REQUEST_NODE_ABORT_TESTING.value
    REQUEST_NODE_OVERRIDE_FAILED_TESTING = (
        EventTypeEnum.REQUEST_NODE_OVERRIDE_FAILED_TESTING.value
    )
    REQUEST_NODE_ABORT_DEPLOYMENT = (
        EventTypeEnum.REQUEST_NODE_ABORT_DEPLOYMENT.value
    )
    REQUEST_NODE_ACQUIRE = EventTypeEnum.REQUEST_NODE_ACQUIRE.value
    REQUEST_NODE_ERASE_DISK = EventTypeEnum.REQUEST_NODE_ERASE_DISK.value
    REQUEST_NODE_ABORT_ERASE_DISK = (
        EventTypeEnum.REQUEST_NODE_ABORT_ERASE_DISK.value
    )
    REQUEST_NODE_RELEASE = EventTypeEnum.REQUEST_NODE_RELEASE.value
    REQUEST_NODE_MARK_FAILED = EventTypeEnum.REQUEST_NODE_MARK_FAILED.value
    REQUEST_NODE_MARK_FAILED_SYSTEM = (
        EventTypeEnum.REQUEST_NODE_MARK_FAILED_SYSTEM.value
    )
    REQUEST_NODE_MARK_BROKEN = EventTypeEnum.REQUEST_NODE_MARK_BROKEN.value
    REQUEST_NODE_MARK_BROKEN_SYSTEM = (
        EventTypeEnum.REQUEST_NODE_MARK_BROKEN_SYSTEM.value
    )
    REQUEST_NODE_MARK_FIXED = EventTypeEnum.REQUEST_NODE_MARK_FIXED.value
    REQUEST_NODE_MARK_FIXED_SYSTEM = (
        EventTypeEnum.REQUEST_NODE_MARK_FIXED_SYSTEM.value
    )
    REQUEST_NODE_LOCK = EventTypeEnum.REQUEST_NODE_LOCK.value
    REQUEST_NODE_UNLOCK = EventTypeEnum.REQUEST_NODE_UNLOCK.value
    REQUEST_NODE_START_DEPLOYMENT = (
        EventTypeEnum.REQUEST_NODE_START_DEPLOYMENT.value
    )
    REQUEST_NODE_START = EventTypeEnum.REQUEST_NODE_START.value
    REQUEST_NODE_STOP = EventTypeEnum.REQUEST_NODE_STOP.value
    REQUEST_NODE_START_RESCUE_MODE = (
        EventTypeEnum.REQUEST_NODE_START_RESCUE_MODE.value
    )
    REQUEST_NODE_STOP_RESCUE_MODE = (
        EventTypeEnum.REQUEST_NODE_STOP_RESCUE_MODE.value
    )
    # Rack controller request events
    REQUEST_CONTROLLER_REFRESH = EventTypeEnum.REQUEST_CONTROLLER_REFRESH.value
    REQUEST_RACK_CONTROLLER_ADD_CHASSIS = (
        EventTypeEnum.REQUEST_RACK_CONTROLLER_ADD_CHASSIS.value
    )
    # Rack import events
    RACK_IMPORT_WARNING = EventTypeEnum.RACK_IMPORT_WARNING.value
    RACK_IMPORT_ERROR = EventTypeEnum.RACK_IMPORT_ERROR.value
    RACK_IMPORT_INFO = EventTypeEnum.RACK_IMPORT_INFO.value
    # Region import events
    REGION_IMPORT_WARNING = EventTypeEnum.REGION_IMPORT_WARNING.value
    REGION_IMPORT_ERROR = EventTypeEnum.REGION_IMPORT_ERROR.value
    REGION_IMPORT_INFO = EventTypeEnum.REGION_IMPORT_INFO.value
    # Script result storage and lookup events
    SCRIPT_RESULT_ERROR = EventTypeEnum.SCRIPT_RESULT_ERROR.value
    # Authorisation events
    AUTHORISATION = EventTypeEnum.AUTHORISATION.value
    # Settings events
    SETTINGS = EventTypeEnum.SETTINGS.value
    # Node events
    NODE = EventTypeEnum.NODE.value
    # Images events
    IMAGES = EventTypeEnum.IMAGES.value
    # Pod events
    POD = EventTypeEnum.POD.value
    # Networking events
    NETWORKING = EventTypeEnum.NETWORKING.value
    # Zones events
    ZONES = EventTypeEnum.ZONES.value
    # Tag events
    TAG = EventTypeEnum.TAG.value
    # Status message events
    CONFIGURING_STORAGE = EventTypeEnum.CONFIGURING_STORAGE.value
    INSTALLING_OS = EventTypeEnum.INSTALLING_OS.value
    CONFIGURING_OS = EventTypeEnum.CONFIGURING_OS.value
    REBOOTING = EventTypeEnum.REBOOTING.value
    PERFORMING_PXE_BOOT = EventTypeEnum.PERFORMING_PXE_BOOT.value
    LOADING_EPHEMERAL = EventTypeEnum.LOADING_EPHEMERAL.value
    NEW = EventTypeEnum.NEW.value
    COMMISSIONING = EventTypeEnum.COMMISSIONING.value
    FAILED_COMMISSIONING = EventTypeEnum.FAILED_COMMISSIONING.value
    TESTING = EventTypeEnum.TESTING.value
    FAILED_TESTING = EventTypeEnum.FAILED_TESTING.value
    READY = EventTypeEnum.READY.value
    DEPLOYING = EventTypeEnum.DEPLOYING.value
    DEPLOYED = EventTypeEnum.DEPLOYED.value
    IMAGE_DEPLOYED = EventTypeEnum.IMAGE_DEPLOYED.value
    RELEASING = EventTypeEnum.RELEASING.value
    RELEASED = EventTypeEnum.RELEASED.value
    ENTERING_RESCUE_MODE = EventTypeEnum.ENTERING_RESCUE_MODE.value
    RESCUE_MODE = EventTypeEnum.RESCUE_MODE.value
    FAILED_EXITING_RESCUE_MODE = EventTypeEnum.FAILED_EXITING_RESCUE_MODE.value
    EXITED_RESCUE_MODE = EventTypeEnum.EXITED_RESCUE_MODE.value
    GATHERING_INFO = EventTypeEnum.GATHERING_INFO.value
    RUNNING_TEST = EventTypeEnum.RUNNING_TEST.value
    SCRIPT_DID_NOT_COMPLETE = EventTypeEnum.SCRIPT_DID_NOT_COMPLETE.value
    SCRIPT_RESULT_CHANGED_STATUS = (
        EventTypeEnum.SCRIPT_RESULT_CHANGED_STATUS.value
    )
    ABORTED_DISK_ERASING = EventTypeEnum.ABORTED_DISK_ERASING.value
    ABORTED_COMMISSIONING = EventTypeEnum.ABORTED_COMMISSIONING.value
    ABORTED_DEPLOYMENT = EventTypeEnum.ABORTED_DEPLOYMENT.value
    ABORTED_TESTING = EventTypeEnum.ABORTED_TESTING.value


# Used to create new events used for the machine's status.
# The keys are the messages sent from cloud-init and curtin
# to the metadataserver.
EVENT_STATUS_MESSAGES = {
    "cmd-install/stage-partitioning": EVENT_TYPES.CONFIGURING_STORAGE,
    "cmd-install/stage-extract": EVENT_TYPES.INSTALLING_OS,
    "cmd-install/stage-curthooks": EVENT_TYPES.CONFIGURING_OS,
}

EVENT_DETAILS = {k.value: v for k, v in EVENT_DETAILS_MAP.items()}


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
