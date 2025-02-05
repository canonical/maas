from maascommon.enums.node import NodeStatus

NODE_FAILURE_STATUS_TRANSITION_MAP = {
    NodeStatus.COMMISSIONING: NodeStatus.FAILED_COMMISSIONING,
    NodeStatus.DEPLOYING: NodeStatus.FAILED_DEPLOYMENT,
    NodeStatus.RELEASING: NodeStatus.FAILED_RELEASING,
    NodeStatus.DISK_ERASING: NodeStatus.FAILED_DISK_ERASING,
    NodeStatus.ENTERING_RESCUE_MODE: NodeStatus.FAILED_ENTERING_RESCUE_MODE,
    NodeStatus.EXITING_RESCUE_MODE: NodeStatus.FAILED_EXITING_RESCUE_MODE,
    NodeStatus.TESTING: NodeStatus.FAILED_TESTING,
}

NODE_STATUS_LABELS = {
    NodeStatus.NEW: "New",
    NodeStatus.COMMISSIONING: "Commissioning",
    NodeStatus.FAILED_COMMISSIONING: "Failed commissioning",
    NodeStatus.MISSING: "Missing",
    NodeStatus.READY: "Ready",
    NodeStatus.RESERVED: "Reserved",
    NodeStatus.ALLOCATED: "Allocated",
    NodeStatus.DEPLOYING: "Deploying",
    NodeStatus.DEPLOYED: "Deployed",
    NodeStatus.RETIRED: "Retired",
    NodeStatus.BROKEN: "Broken",
    NodeStatus.FAILED_DEPLOYMENT: "Failed deployment",
    NodeStatus.RELEASING: "Releasing",
    NodeStatus.FAILED_RELEASING: "Releasing failed",
    NodeStatus.DISK_ERASING: "Disk erasing",
    NodeStatus.FAILED_DISK_ERASING: "Failed disk erasing",
    NodeStatus.RESCUE_MODE: "Rescue mode",
    NodeStatus.ENTERING_RESCUE_MODE: "Entering rescue mode",
    NodeStatus.FAILED_ENTERING_RESCUE_MODE: "Failed to enter rescue mode",
    NodeStatus.EXITING_RESCUE_MODE: "Exiting rescue mode",
    NodeStatus.FAILED_EXITING_RESCUE_MODE: "Failed to exit rescue mode",
    NodeStatus.TESTING: "Testing",
    NodeStatus.FAILED_TESTING: "Failed testing",
}
