from maasserver.enum import NODE_STATUS

from .common import make_weighted_item_getter

MACHINES_PER_FABRIC = 48  # Each ToR switch is its own fabric
VLAN_PER_FABRIC_COUNT = 4  # in addition to the default one
VMHOST_COUNT = 5
OWNERDATA_PER_MACHINE_COUNT = 5
TAG_COUNT = 100
EVENT_TYPE_COUNT = 50
ADMIN_COUNT = 5
USER_COUNT = 10
RACKCONTROLLER_COUNT = 5

MACHINE_ARCHES = ("x86_64", "aarch64", "ppc64le")
STORAGE_SETUPS = (
    "basic",
    "bcache",
    "lvm",
    "raid-0",
    "raid-1",
    "raid-10",
    "raid-5",
    "raid-6",
)

MACHINE_STATUSES = make_weighted_item_getter(
    {
        NODE_STATUS.NEW: 5,
        NODE_STATUS.COMMISSIONING: 15,
        NODE_STATUS.FAILED_COMMISSIONING: 1,
        NODE_STATUS.BROKEN: 1,
        NODE_STATUS.READY: 100,
        NODE_STATUS.TESTING: 2,
        NODE_STATUS.DEPLOYING: 30,
        NODE_STATUS.DEPLOYED: 500,
        NODE_STATUS.ALLOCATED: 5,
        NODE_STATUS.RELEASING: 30,
        NODE_STATUS.DISK_ERASING: 2,
        NODE_STATUS.FAILED_DISK_ERASING: 1,
        NODE_STATUS.FAILED_DEPLOYMENT: 1,
        NODE_STATUS.RESCUE_MODE: 5,
        NODE_STATUS.FAILED_ENTERING_RESCUE_MODE: 1,
        NODE_STATUS.EXITING_RESCUE_MODE: 1,
        NODE_STATUS.FAILED_EXITING_RESCUE_MODE: 1,
        NODE_STATUS.FAILED_TESTING: 1,
    }
)

EVENT_PER_MACHINE = make_weighted_item_getter(
    {
        10000: 1,
        1000: 100,
        500: 200,
        100: 500,
    }
)
