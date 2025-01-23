#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import Enum, IntEnum


class EndpointTypeEnum(IntEnum):
    API = 0
    UI = 1
    CLI = 2


class EventTypeEnum(str, Enum):

    # Power-related events.
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
    NODE_DISKS_ERASED = "NODE_DISKS_ERASED"
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
    NODE_RELEASE_SCRIPTS_OK = "NODE_RELEASE_SCRIPTS_OK"
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
