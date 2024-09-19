#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import Enum, IntEnum


class NodeDeviceBus(IntEnum):
    PCIE = 1
    USB = 2


class NodeStatus(IntEnum):
    """The vocabulary of a `Node`'s possible statuses."""

    # A node starts out as NEW (DEFAULT is an alias for NEW).
    DEFAULT = 0

    # The node has been created and has a system ID assigned to it.
    NEW = 0
    # Testing and other commissioning steps are taking place.
    COMMISSIONING = 1
    # The commissioning step failed.
    FAILED_COMMISSIONING = 2
    # The node can't be contacted.
    MISSING = 3
    # The node is in the general pool ready to be deployed.
    READY = 4
    # The node is ready for named deployment.
    RESERVED = 5
    # The node has booted into the operating system of its owner's choice
    # and is ready for use.
    DEPLOYED = 6
    # The node has been removed from service manually until an admin
    # overrides the retirement.
    RETIRED = 7
    # The node is broken: a step in the node lifecyle failed.
    # More details can be found in the node's event log.
    BROKEN = 8
    # The node is being installed.
    DEPLOYING = 9
    # The node has been allocated to a user and is ready for deployment.
    ALLOCATED = 10
    # The deployment of the node failed.
    FAILED_DEPLOYMENT = 11
    # The node is powering down after a release request.
    RELEASING = 12
    # The releasing of the node failed.
    FAILED_RELEASING = 13
    # The node is erasing its disks.
    DISK_ERASING = 14
    # The node failed to erase its disks.
    FAILED_DISK_ERASING = 15
    # The node is in rescue mode.
    RESCUE_MODE = 16
    # The node is entering rescue mode.
    ENTERING_RESCUE_MODE = 17
    # The node failed to enter rescue mode.
    FAILED_ENTERING_RESCUE_MODE = 18
    # The node is exiting rescue mode.
    EXITING_RESCUE_MODE = 19
    # The node failed to exit rescue mode.
    FAILED_EXITING_RESCUE_MODE = 20
    # Running tests on Node
    TESTING = 21
    # Testing has failed
    FAILED_TESTING = 22


class NodeTypeEnum(IntEnum):
    """Valid node types."""

    DEFAULT = 0
    MACHINE = 0
    DEVICE = 1
    RACK_CONTROLLER = 2
    REGION_CONTROLLER = 3
    REGION_AND_RACK_CONTROLLER = 4


class SimplifiedNodeStatusEnum(str, Enum):
    """The vocabulary of a `Node`'s possible simplified statuses."""

    ALLOCATED = "Allocated"
    BROKEN = "Broken"
    COMMISSIONING = "Commissioning"
    DEPLOYED = "Deployed"
    DEPLOYING = "Deploying"
    FAILED = "Failed"
    NEW = "New"
    READY = "Ready"
    RELEASING = "Releasing"
    RESCUE_MODE = "Rescue Mode"
    TESTING = "Testing"
    OTHER = "Other"
