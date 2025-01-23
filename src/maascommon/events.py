#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from collections import namedtuple
from logging import DEBUG, ERROR, INFO, WARN

from maascommon.enums.events import EventTypeEnum

# AUDIT event logging level
AUDIT = 0

EventDetail = namedtuple("EventDetail", ("description", "level"))


EVENT_DETAILS_MAP = {
    EventTypeEnum.NODE_POWERED_ON: EventDetail(
        description="Node powered on", level=DEBUG
    ),
    EventTypeEnum.NODE_POWERED_OFF: EventDetail(
        description="Node powered off", level=DEBUG
    ),
    EventTypeEnum.NODE_POWER_ON_FAILED: EventDetail(
        description="Failed to power on node", level=ERROR
    ),
    EventTypeEnum.NODE_POWER_OFF_FAILED: EventDetail(
        description="Failed to power off node", level=ERROR
    ),
    EventTypeEnum.NODE_POWER_CYCLE_FAILED: EventDetail(
        description="Failed to power cycle node", level=ERROR
    ),
    EventTypeEnum.NODE_POWER_QUERY_FAILED: EventDetail(
        description="Failed to query node's BMC", level=WARN
    ),
    EventTypeEnum.NODE_TFTP_REQUEST: EventDetail(
        description="TFTP Request", level=DEBUG
    ),
    EventTypeEnum.NODE_HTTP_REQUEST: EventDetail(
        description="HTTP Request", level=DEBUG
    ),
    EventTypeEnum.NODE_PXE_REQUEST: EventDetail(
        description="PXE Request", level=DEBUG
    ),
    EventTypeEnum.NODE_INSTALLATION_FINISHED: EventDetail(
        description="Installation complete", level=DEBUG
    ),
    EventTypeEnum.NODE_DISKS_ERASED: EventDetail(
        description="Disks erased", level=INFO
    ),
    EventTypeEnum.NODE_CHANGED_STATUS: EventDetail(
        description="Node changed status", level=DEBUG
    ),
    EventTypeEnum.NODE_STATUS_EVENT: EventDetail(
        description="Node status event", level=DEBUG
    ),
    EventTypeEnum.NODE_COMMISSIONING_EVENT: EventDetail(
        description="Node commissioning", level=DEBUG
    ),
    EventTypeEnum.NODE_COMMISSIONING_EVENT_FAILED: EventDetail(
        description="Node commissioning failure", level=ERROR
    ),
    EventTypeEnum.NODE_INSTALL_EVENT: EventDetail(
        description="Node installation", level=DEBUG
    ),
    EventTypeEnum.NODE_INSTALL_EVENT_FAILED: EventDetail(
        description="Node installation failure", level=ERROR
    ),
    EventTypeEnum.NODE_POST_INSTALL_EVENT_FAILED: EventDetail(
        description="Node post-installation failure", level=ERROR
    ),
    EventTypeEnum.NODE_ENTERING_RESCUE_MODE_EVENT: EventDetail(
        description="Node entering rescue mode", level=DEBUG
    ),
    EventTypeEnum.NODE_ENTERING_RESCUE_MODE_EVENT_FAILED: EventDetail(
        description="Node entering rescue mode failure", level=ERROR
    ),
    EventTypeEnum.NODE_EXITING_RESCUE_MODE_EVENT: EventDetail(
        description="Node exiting rescue mode", level=DEBUG
    ),
    EventTypeEnum.NODE_EXITING_RESCUE_MODE_EVENT_FAILED: EventDetail(
        description="Node exiting rescue mode failure", level=ERROR
    ),
    EventTypeEnum.NODE_HARDWARE_SYNC_BMC: EventDetail(
        description="Node BMC hardware sync state change", level=INFO
    ),
    EventTypeEnum.NODE_HARDWARE_SYNC_BLOCK_DEVICE: EventDetail(
        description="Node Block Device hardware sync state change", level=INFO
    ),
    EventTypeEnum.NODE_HARDWARE_SYNC_CPU: EventDetail(
        description="Node CPU hardware sync state change", level=INFO
    ),
    EventTypeEnum.NODE_HARDWARE_SYNC_INTERFACE: EventDetail(
        description="Node Interface hardware sync state change", level=INFO
    ),
    EventTypeEnum.NODE_HARDWARE_SYNC_MEMORY: EventDetail(
        description="Node Memory hardware sync state change", level=INFO
    ),
    EventTypeEnum.NODE_HARDWARE_SYNC_PCI_DEVICE: EventDetail(
        description="Node PCI Device hardware sync state change", level=INFO
    ),
    EventTypeEnum.NODE_HARDWARE_SYNC_USB_DEVICE: EventDetail(
        description="Node USB Device hardware sync state chage", level=INFO
    ),
    EventTypeEnum.NODE_RELEASE_SCRIPTS_OK: EventDetail(
        description="Release scripts executed successfully.", level=INFO
    ),
    EventTypeEnum.REQUEST_NODE_START_COMMISSIONING: EventDetail(
        description="User starting node commissioning", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_ABORT_COMMISSIONING: EventDetail(
        description="User aborting node commissioning", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_START_TESTING: EventDetail(
        description="User starting node testing", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_ABORT_TESTING: EventDetail(
        description="User aborting node testing", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_OVERRIDE_FAILED_TESTING: EventDetail(
        description="User overrode 'Failed testing' status", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_ABORT_DEPLOYMENT: EventDetail(
        description="User aborting deployment", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_ACQUIRE: EventDetail(
        description="User acquiring node", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_ERASE_DISK: EventDetail(
        description="User erasing disk", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_ABORT_ERASE_DISK: EventDetail(
        description="User aborting disk erase", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_RELEASE: EventDetail(
        description="User releasing node", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_MARK_FAILED: EventDetail(
        description="User marking node failed", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_MARK_FAILED_SYSTEM: EventDetail(
        description="Marking node failed", level=ERROR
    ),
    EventTypeEnum.REQUEST_NODE_MARK_BROKEN: EventDetail(
        description="User marking node broken", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_MARK_BROKEN_SYSTEM: EventDetail(
        description="Marking node broken", level=ERROR
    ),
    EventTypeEnum.REQUEST_NODE_MARK_FIXED: EventDetail(
        description="User marking node fixed", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_MARK_FIXED_SYSTEM: EventDetail(
        description="Marking node fixed", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_LOCK: EventDetail(
        description="User locking node", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_UNLOCK: EventDetail(
        description="User unlocking node", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_START_DEPLOYMENT: EventDetail(
        description="User starting deployment", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_START: EventDetail(
        description="User powering up node", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_STOP: EventDetail(
        description="User powering down node", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_START_RESCUE_MODE: EventDetail(
        description="User starting rescue mode", level=DEBUG
    ),
    EventTypeEnum.REQUEST_NODE_STOP_RESCUE_MODE: EventDetail(
        description="User stopping rescue mode", level=DEBUG
    ),
    EventTypeEnum.REQUEST_CONTROLLER_REFRESH: EventDetail(
        description=(
            "Starting refresh of controller hardware and networking "
            "information"
        ),
        level=DEBUG,
    ),
    EventTypeEnum.REQUEST_RACK_CONTROLLER_ADD_CHASSIS: EventDetail(
        description="Querying chassis and enlisting all machines", level=DEBUG
    ),
    EventTypeEnum.RACK_IMPORT_WARNING: EventDetail(
        description="Rack import warning", level=WARN
    ),
    EventTypeEnum.RACK_IMPORT_ERROR: EventDetail(
        description="Rack import error", level=ERROR
    ),
    EventTypeEnum.RACK_IMPORT_INFO: EventDetail(
        description="Rack import info", level=DEBUG
    ),
    EventTypeEnum.REGION_IMPORT_WARNING: EventDetail(
        description="Region import warning", level=WARN
    ),
    EventTypeEnum.REGION_IMPORT_ERROR: EventDetail(
        description="Region import error", level=ERROR
    ),
    EventTypeEnum.REGION_IMPORT_INFO: EventDetail(
        description="Region import info", level=DEBUG
    ),
    EventTypeEnum.SCRIPT_RESULT_ERROR: EventDetail(
        description="Script result lookup or storage error", level=ERROR
    ),
    EventTypeEnum.AUTHORISATION: EventDetail(
        description="Authorisation", level=AUDIT
    ),
    EventTypeEnum.SETTINGS: EventDetail(description="Settings", level=AUDIT),
    EventTypeEnum.NODE: EventDetail(description="Node", level=AUDIT),
    EventTypeEnum.IMAGES: EventDetail(description="Images", level=AUDIT),
    EventTypeEnum.POD: EventDetail(description="Pod", level=AUDIT),
    EventTypeEnum.TAG: EventDetail(description="Tag", level=AUDIT),
    EventTypeEnum.NETWORKING: EventDetail(
        description="Networking", level=AUDIT
    ),
    EventTypeEnum.ZONES: EventDetail(description="Zones", level=AUDIT),
    EventTypeEnum.CONFIGURING_STORAGE: EventDetail(
        description="Configuring storage", level=INFO
    ),
    EventTypeEnum.INSTALLING_OS: EventDetail(
        description="Installing OS", level=INFO
    ),
    EventTypeEnum.CONFIGURING_OS: EventDetail(
        description="Configuring OS", level=INFO
    ),
    EventTypeEnum.REBOOTING: EventDetail(description="Rebooting", level=INFO),
    EventTypeEnum.PERFORMING_PXE_BOOT: EventDetail(
        description="Performing PXE boot", level=INFO
    ),
    EventTypeEnum.LOADING_EPHEMERAL: EventDetail(
        description="Loading ephemeral", level=INFO
    ),
    EventTypeEnum.NEW: EventDetail(description="New", level=INFO),
    EventTypeEnum.COMMISSIONING: EventDetail(
        description="Commissioning", level=INFO
    ),
    EventTypeEnum.FAILED_COMMISSIONING: EventDetail(
        description="Failed commissioning", level=INFO
    ),
    EventTypeEnum.TESTING: EventDetail(description="Testing", level=INFO),
    EventTypeEnum.FAILED_TESTING: EventDetail(
        description="Failed testing", level=INFO
    ),
    EventTypeEnum.READY: EventDetail(description="Ready", level=INFO),
    EventTypeEnum.DEPLOYING: EventDetail(description="Deploying", level=INFO),
    EventTypeEnum.DEPLOYED: EventDetail(description="Deployed", level=INFO),
    EventTypeEnum.IMAGE_DEPLOYED: EventDetail(
        description="Image Deployed", level=INFO
    ),
    EventTypeEnum.RELEASING: EventDetail(description="Releasing", level=INFO),
    EventTypeEnum.RELEASED: EventDetail(description="Released", level=INFO),
    EventTypeEnum.ENTERING_RESCUE_MODE: EventDetail(
        description="Entering rescue mode", level=INFO
    ),
    EventTypeEnum.RESCUE_MODE: EventDetail(
        description="Rescue mode", level=INFO
    ),
    EventTypeEnum.FAILED_EXITING_RESCUE_MODE: EventDetail(
        description="Failed exiting rescue mode", level=INFO
    ),
    EventTypeEnum.EXITED_RESCUE_MODE: EventDetail(
        description="Exited rescue mode", level=INFO
    ),
    EventTypeEnum.GATHERING_INFO: EventDetail(
        description="Gathering information", level=INFO
    ),
    EventTypeEnum.RUNNING_TEST: EventDetail(
        description="Running test", level=INFO
    ),
    EventTypeEnum.SCRIPT_DID_NOT_COMPLETE: EventDetail(
        description="Script", level=INFO
    ),
    EventTypeEnum.SCRIPT_RESULT_CHANGED_STATUS: EventDetail(
        description="Script result", level=DEBUG
    ),
    EventTypeEnum.ABORTED_DISK_ERASING: EventDetail(
        description="Aborted disk erasing", level=INFO
    ),
    EventTypeEnum.ABORTED_COMMISSIONING: EventDetail(
        description="Aborted commissioning", level=INFO
    ),
    EventTypeEnum.ABORTED_DEPLOYMENT: EventDetail(
        description="Aborted deployment", level=INFO
    ),
    EventTypeEnum.ABORTED_TESTING: EventDetail(
        description="Aborted testing", level=INFO
    ),
}
