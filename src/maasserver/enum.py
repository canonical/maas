# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Enumerations meaningful to the maasserver application."""

__all__ = [
    "CACHE_MODE_TYPE",
    "CACHE_MODE_TYPE_CHOICES",
    "COMPONENT",
    "DEVICE_IP_ASSIGNMENT_TYPE",
    "FILESYSTEM_GROUP_TYPE",
    "FILESYSTEM_GROUP_TYPE_CHOICES",
    "FILESYSTEM_TYPE",
    "FILESYSTEM_TYPE_CHOICES",
    "INTERFACE_TYPE",
    "INTERFACE_TYPE_CHOICES",
    "INTERFACE_TYPE_CHOICES_DICT",
    "IPADDRESS_TYPE",
    "NODE_STATUS",
    "NODE_STATUS_CHOICES",
    "NODE_STATUS_CHOICES_DICT",
    "PARTITION_TABLE_TYPE",
    "PARTITION_TABLE_TYPE_CHOICES",
    "PRESEED_TYPE",
    "RDNS_MODE",
    "RDNS_MODE_CHOICES",
    "RDNS_MODE_CHOICES_DICT",
    "KEYS_PROTOCOL_TYPE",
    "KEYS_PROTOCOL_TYPE_CHOICES",
]

from collections import OrderedDict
from typing import Callable, cast

from provisioningserver.enum import enum_choices


class COMPONENT:
    """Major moving parts of the application that may have failure states."""

    PSERV = "provisioning server"
    IMPORT_PXE_FILES = "maas-import-pxe-files script"
    RACK_CONTROLLERS = "clusters"
    REGION_IMAGE_IMPORT = "Image importer"


class NODE_STATUS:
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


# Django choices for NODE_STATUS: sequence of tuples (key, UI
# representation).
NODE_STATUS_CHOICES = (
    (NODE_STATUS.NEW, "New"),
    (NODE_STATUS.COMMISSIONING, "Commissioning"),
    (NODE_STATUS.FAILED_COMMISSIONING, "Failed commissioning"),
    (NODE_STATUS.MISSING, "Missing"),
    (NODE_STATUS.READY, "Ready"),
    (NODE_STATUS.RESERVED, "Reserved"),
    (NODE_STATUS.ALLOCATED, "Allocated"),
    (NODE_STATUS.DEPLOYING, "Deploying"),
    (NODE_STATUS.DEPLOYED, "Deployed"),
    (NODE_STATUS.RETIRED, "Retired"),
    (NODE_STATUS.BROKEN, "Broken"),
    (NODE_STATUS.FAILED_DEPLOYMENT, "Failed deployment"),
    (NODE_STATUS.RELEASING, "Releasing"),
    (NODE_STATUS.FAILED_RELEASING, "Releasing failed"),
    (NODE_STATUS.DISK_ERASING, "Disk erasing"),
    (NODE_STATUS.FAILED_DISK_ERASING, "Failed disk erasing"),
    (NODE_STATUS.RESCUE_MODE, "Rescue mode"),
    (NODE_STATUS.ENTERING_RESCUE_MODE, "Entering rescue mode"),
    (NODE_STATUS.FAILED_ENTERING_RESCUE_MODE, "Failed to enter rescue mode"),
    (NODE_STATUS.EXITING_RESCUE_MODE, "Exiting rescue mode"),
    (NODE_STATUS.FAILED_EXITING_RESCUE_MODE, "Failed to exit rescue mode"),
    (NODE_STATUS.TESTING, "Testing"),
    (NODE_STATUS.FAILED_TESTING, "Failed testing"),
)

# A version of NODE_STATUS_CHOICES with one-word labels
NODE_STATUS_SHORT_LABEL_CHOICES = tuple(
    sorted(
        (attr.lower(), attr.lower())
        for attr in dir(NODE_STATUS)
        if not attr.startswith("_") and attr != "DEFAULT"
    )
)

NODE_STATUS_CHOICES_DICT = OrderedDict(NODE_STATUS_CHOICES)


# NODE_STATUS when the node is owned by an owner and it is not commissioning.
ALLOCATED_NODE_STATUSES = frozenset(
    [
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.DEPLOYING,
        NODE_STATUS.DEPLOYED,
        NODE_STATUS.FAILED_DEPLOYMENT,
        NODE_STATUS.RELEASING,
        NODE_STATUS.FAILED_RELEASING,
        NODE_STATUS.DISK_ERASING,
        NODE_STATUS.FAILED_DISK_ERASING,
        NODE_STATUS.RESCUE_MODE,
        NODE_STATUS.ENTERING_RESCUE_MODE,
        NODE_STATUS.FAILED_ENTERING_RESCUE_MODE,
        NODE_STATUS.EXITING_RESCUE_MODE,
        NODE_STATUS.FAILED_EXITING_RESCUE_MODE,
        NODE_STATUS.TESTING,
        NODE_STATUS.FAILED_TESTING,
    ]
)


class SIMPLIFIED_NODE_STATUS:
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


SIMPLIFIED_NODE_STATUS_CHOICES = enum_choices(SIMPLIFIED_NODE_STATUS)

SIMPLIFIED_NODE_STATUS_CHOICES_DICT = OrderedDict(
    SIMPLIFIED_NODE_STATUS_CHOICES
)

# A version of SIMPLIFIED_NODE_STATUS_CHOICES with one-word labels
SIMPLIFIED_NODE_STATUS_LABEL_CHOICES = tuple(
    sorted(
        (attr.lower(), attr.lower())
        for attr in dir(SIMPLIFIED_NODE_STATUS)
        if not attr.startswith("_") and attr != "DEFAULT"
    )
)

SIMPLIFIED_NODE_STATUSES_MAP = {
    SIMPLIFIED_NODE_STATUS.ALLOCATED: [NODE_STATUS.ALLOCATED],
    SIMPLIFIED_NODE_STATUS.BROKEN: [NODE_STATUS.BROKEN],
    SIMPLIFIED_NODE_STATUS.COMMISSIONING: [NODE_STATUS.COMMISSIONING],
    SIMPLIFIED_NODE_STATUS.DEPLOYED: [NODE_STATUS.DEPLOYED],
    SIMPLIFIED_NODE_STATUS.DEPLOYING: [NODE_STATUS.DEPLOYING],
    SIMPLIFIED_NODE_STATUS.FAILED: [
        NODE_STATUS.FAILED_COMMISSIONING,
        NODE_STATUS.FAILED_DEPLOYMENT,
        NODE_STATUS.FAILED_DISK_ERASING,
        NODE_STATUS.FAILED_ENTERING_RESCUE_MODE,
        NODE_STATUS.FAILED_EXITING_RESCUE_MODE,
        NODE_STATUS.FAILED_RELEASING,
        NODE_STATUS.FAILED_TESTING,
    ],
    SIMPLIFIED_NODE_STATUS.NEW: [NODE_STATUS.NEW],
    SIMPLIFIED_NODE_STATUS.READY: [NODE_STATUS.READY],
    SIMPLIFIED_NODE_STATUS.RELEASING: [
        NODE_STATUS.DISK_ERASING,
        NODE_STATUS.RELEASING,
    ],
    SIMPLIFIED_NODE_STATUS.RESCUE_MODE: [
        NODE_STATUS.ENTERING_RESCUE_MODE,
        NODE_STATUS.EXITING_RESCUE_MODE,
        NODE_STATUS.RESCUE_MODE,
    ],
    SIMPLIFIED_NODE_STATUS.TESTING: [NODE_STATUS.TESTING],
}

SIMPLIFIED_NODE_STATUSES_MAP_REVERSED = {
    val: simple_status
    for simple_status, values in SIMPLIFIED_NODE_STATUSES_MAP.items()
    for val in values
}


class NODE_TYPE:
    """Valid node types."""

    DEFAULT = 0
    MACHINE = 0
    DEVICE = 1
    RACK_CONTROLLER = 2
    REGION_CONTROLLER = 3
    REGION_AND_RACK_CONTROLLER = 4


# This is copied in static/js/angular/controllers/subnet_details.js. If you
# update any choices you also need to update the controller.
NODE_TYPE_CHOICES = (
    (NODE_TYPE.MACHINE, "Machine"),
    (NODE_TYPE.DEVICE, "Device"),
    (NODE_TYPE.RACK_CONTROLLER, "Rack controller"),
    (NODE_TYPE.REGION_CONTROLLER, "Region controller"),
    (NODE_TYPE.REGION_AND_RACK_CONTROLLER, "Region and rack controller"),
)

NODE_TYPE_CHOICES_DICT = OrderedDict(NODE_TYPE_CHOICES)


class BMC_TYPE:
    """Valid BMC types."""

    DEFAULT = 0
    BMC = 0
    POD = 1


BMC_TYPE_CHOICES = ((BMC_TYPE.BMC, "BMC"), (BMC_TYPE.POD, "POD"))


class NODE_ACTION_TYPE:
    """Types of action a node can have done."""

    LIFECYCLE = "lifecycle"
    POWER = "power"
    TESTING = "testing"
    LOCK = "lock"
    MISC = "misc"


class DEVICE_IP_ASSIGNMENT_TYPE:
    """The vocabulary of a `Device`'s possible IP assignment type. This value
    is calculated by looking at the overall model for a `Device`. This is not
    set directly on the model."""

    # Device is outside of MAAS control.
    EXTERNAL = "external"

    # Device receives ip address from the appropriate dynamic range.
    DYNAMIC = "dynamic"

    # Device has ip address assigned from some appropriate subnet.
    STATIC = "static"


class PRESEED_TYPE:
    """Types of preseed documents that can be generated."""

    COMMISSIONING = "commissioning"
    ENLIST = "enlist"
    CURTIN = "curtin"


class RDNS_MODE:
    """The vocabulary of a `Subnet`'s possible reverse DNS modes."""

    # By default, we do what we've always done: assume we rule the DNS world.
    DEFAULT = 2
    # Do not generate reverse DNS for this Subnet.
    DISABLED = 0
    # Generate reverse DNS only for the CIDR.
    ENABLED = 1
    # Generate RFC2317 glue if needed (Subnet is too small for its own zone.)
    RFC2317 = 2


# Django choices for RDNS_MODE: sequence of tuples (key, UI representation.)
RDNS_MODE_CHOICES = (
    (RDNS_MODE.DISABLED, "Disabled"),
    (RDNS_MODE.ENABLED, "Enabled"),
    (RDNS_MODE.RFC2317, "Enabled, with rfc2317 glue zone."),
)


RDNS_MODE_CHOICES_DICT = OrderedDict(RDNS_MODE_CHOICES)


class IPADDRESS_FAMILY:
    """The vocabulary of possible IP family for `StaticIPAddress`."""

    IPv4 = 4
    IPv6 = 6


class IPADDRESS_TYPE:
    """The vocabulary of possible types of `StaticIPAddress`."""

    # Note: when this enum is changed, the custom SQL query
    # in StaticIPAddressManager.get_hostname_ip_mapping() must also
    # be changed.

    # Automatically assigned IP address for a node or device out of the
    # connected clusters managed range. MUST NOT be assigned to a Interface
    # with a STICKY address of the same address family.
    AUTO = 0

    # User-specified static IP address for a node or device.
    # Permanent until removed by the user, or the node or device is deleted.
    STICKY = 1

    # User-specified static IP address.
    # Specifying a MAC address is optional. If the MAC address is not present,
    # it is created in the database (thus creating a MAC address not linked
    # to a node or a device).
    # USER_RESERVED IP addresses that correspond to a MAC address,
    # and reside within a cluster interface range, will be added to the DHCP
    # leases file.
    USER_RESERVED = 4

    # Assigned to tell the interface that it should DHCP from a managed
    # clusters dynamic range or from an external DHCP server.
    DHCP = 5

    # IP address was discovered on the interface during commissioning and/or
    # lease parsing. Only commissioning or lease parsing creates these IP
    # addresses.
    DISCOVERED = 6


# This is copied in static/js/angular/controllers/subnet_details.js. If you
# update any choices you also need to update the controller.
IPADDRESS_TYPE_CHOICES = (
    (IPADDRESS_TYPE.AUTO, "Automatic"),
    (IPADDRESS_TYPE.STICKY, "Static"),
    (IPADDRESS_TYPE.USER_RESERVED, "User reserved"),
    (IPADDRESS_TYPE.DHCP, "DHCP"),
    (IPADDRESS_TYPE.DISCOVERED, "Observed"),
)


IPADDRESS_TYPE_CHOICES_DICT = OrderedDict(IPADDRESS_TYPE_CHOICES)


class IPRANGE_TYPE:
    """The vocabulary of possible types of `IPRange` objects."""

    # Dynamic IP Range.
    DYNAMIC = "dynamic"

    # Reserved for exclusive use by MAAS (and possibly a particular user).
    RESERVED = "reserved"


IPRANGE_TYPE_CHOICES = (
    (IPRANGE_TYPE.DYNAMIC, "Dynamic IP Range"),
    (IPRANGE_TYPE.RESERVED, "Reserved IP Range"),
)


class POWER_WORKFLOW_ACTIONS:
    # Temporal parameter to execute a workflow for powering on
    # a machine
    ON = "power_on"

    # Temporal parameter to execute a workflow for powering on
    # a machine
    OFF = "power_off"

    # Temporal parameter to execute a workflow for powering on
    # a machine
    CYCLE = "power_cycle"

    # Temporal parameter to execute a workflow for powering on
    # a machine
    QUERY = "power_query"


class DEPLOYMENT_TARGET:
    # A node has been deployed ephemerally
    MEMORY = "memory"

    DISK = "disk"


DEPLOYMENT_TARGET_CHOICES = enum_choices(
    DEPLOYMENT_TARGET, transform=cast(Callable[[str], str], str.capitalize)
)


class BOOT_RESOURCE_TYPE:
    """Possible types for `BootResource`."""

    SYNCED = 0  # downloaded from BootSources
    # index 1 was GENERATED, now unused
    UPLOADED = 2  # uploaded by user


# Django choices for BOOT_RESOURCE_TYPE: sequence of tuples (key, UI
# representation).
BOOT_RESOURCE_TYPE_CHOICES = (
    (BOOT_RESOURCE_TYPE.SYNCED, "Synced"),
    (BOOT_RESOURCE_TYPE.UPLOADED, "Uploaded"),
)


BOOT_RESOURCE_TYPE_CHOICES_DICT = OrderedDict(BOOT_RESOURCE_TYPE_CHOICES)


class BOOT_RESOURCE_FILE_TYPE:
    """The vocabulary of possible file types for `BootResource`."""

    # Tarball of root image.
    ROOT_TGZ = "root-tgz"
    ROOT_TBZ = "root-tbz"
    ROOT_TXZ = "root-txz"

    # Tarball of dd image.
    ROOT_DD = "root-dd"
    ROOT_DDTAR = "root-dd.tar"

    # Raw dd image
    ROOT_DDRAW = "root-dd.raw"

    # Compressed dd image types
    ROOT_DDBZ2 = "root-dd.bz2"
    ROOT_DDGZ = "root-dd.gz"
    ROOT_DDXZ = "root-dd.xz"

    # Compressed tarballs of dd images
    ROOT_DDTBZ = "root-dd.tar.bz2"
    ROOT_DDTXZ = "root-dd.tar.xz"
    # For backwards compatibility, DDTGZ files are named root-dd
    ROOT_DDTGZ = "root-dd"

    # Following are not allowed on user upload. Only used for syncing
    # from another simplestreams source. (Most likely images.maas.io)

    # Root Image (gets converted to root-image root-tgz, on the rack)
    ROOT_IMAGE = "root-image.gz"

    # Root image in SquashFS form, does not need to be converted
    SQUASHFS_IMAGE = "squashfs"

    # Boot Kernel
    BOOT_KERNEL = "boot-kernel"

    # Boot Initrd
    BOOT_INITRD = "boot-initrd"

    # Boot DTB
    BOOT_DTB = "boot-dtb"

    # tar.xz of files which need to be extracted so the files are usable
    # by MAAS
    ARCHIVE_TAR_XZ = "archive.tar.xz"


# Django choices for BOOT_RESOURCE_FILE_TYPE: sequence of tuples (key, UI
# representation).
BOOT_RESOURCE_FILE_TYPE_CHOICES = (
    (BOOT_RESOURCE_FILE_TYPE.ROOT_TGZ, "Root Image (tar.gz)"),
    (BOOT_RESOURCE_FILE_TYPE.ROOT_TBZ, "Root Image (tar.bz2)"),
    (BOOT_RESOURCE_FILE_TYPE.ROOT_TXZ, "Root image (tar.xz)"),
    (BOOT_RESOURCE_FILE_TYPE.ROOT_DD, "Root Compressed DD (dd -> tar.gz)"),
    (BOOT_RESOURCE_FILE_TYPE.ROOT_DDTGZ, "Root Compressed DD (dd -> tar.gz)"),
    (
        BOOT_RESOURCE_FILE_TYPE.ROOT_DDTAR,
        "Root Tarfile with DD (dd -> root-dd.tar)",
    ),
    (
        BOOT_RESOURCE_FILE_TYPE.ROOT_DDRAW,
        "Raw root DD image(dd -> root-dd.raw)",
    ),
    (
        BOOT_RESOURCE_FILE_TYPE.ROOT_DDTBZ,
        "Root Compressed DD (dd -> root-dd.tar.bz2)",
    ),
    (
        BOOT_RESOURCE_FILE_TYPE.ROOT_DDTXZ,
        "Root Compressed DD (dd -> root-dd.tar.xz)",
    ),
    (BOOT_RESOURCE_FILE_TYPE.ROOT_DDBZ2, "Root Compressed DD (root-dd.bz2)"),
    (BOOT_RESOURCE_FILE_TYPE.ROOT_DDGZ, "Root Compressed DD (root-dd.gz)"),
    (BOOT_RESOURCE_FILE_TYPE.ROOT_DDXZ, "Root Compressed DD (root-dd.xz)"),
    (BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE, "Compressed Root Image"),
    (BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE, "SquashFS Root Image"),
    (BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL, "Linux ISCSI Kernel"),
    (BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD, "Initial ISCSI Ramdisk"),
    (BOOT_RESOURCE_FILE_TYPE.BOOT_DTB, "ISCSI Device Tree Blob"),
    (BOOT_RESOURCE_FILE_TYPE.ARCHIVE_TAR_XZ, "Archives.tar.xz set of files"),
)


class PARTITION_TABLE_TYPE:
    """The vocabulary of possible partition types for `PartitionTable`."""

    # GUID partition table.
    GPT = "GPT"

    # Master boot record..
    MBR = "MBR"


# Django choices for PARTITION_TABLE_TYPE: sequence of tuples (key, UI
# representation).
PARTITION_TABLE_TYPE_CHOICES = (
    (PARTITION_TABLE_TYPE.MBR, "Master boot record"),
    (PARTITION_TABLE_TYPE.GPT, "GUID parition table"),
)


class FILESYSTEM_TYPE:
    """The vocabulary of possible partition types for `Filesystem`."""

    # Second extended filesystem.
    EXT2 = "ext2"

    # Fourth extended filesystem.
    EXT4 = "ext4"

    # XFS
    XFS = "xfs"

    # FAT32
    FAT32 = "fat32"

    # VFAT
    VFAT = "vfat"

    # LVM Physical Volume.
    LVM_PV = "lvm-pv"

    # RAID.
    RAID = "raid"

    # RAID spare.
    RAID_SPARE = "raid-spare"

    # Bcache cache.
    BCACHE_CACHE = "bcache-cache"

    # Bcache backing.
    BCACHE_BACKING = "bcache-backing"

    # Swap
    SWAP = "swap"

    # RAMFS. Note that tmpfs provides a superset of ramfs's features and can
    # be safer.
    RAMFS = "ramfs"

    # TMPFS
    TMPFS = "tmpfs"

    # BTRFS
    BTRFS = "btrfs"

    # ZFS
    ZFSROOT = "zfsroot"

    # VMFS6
    VMFS6 = "vmfs6"


# Django choices for FILESYSTEM_TYPE: sequence of tuples (key, UI
# representation).
FILESYSTEM_TYPE_CHOICES = (
    (FILESYSTEM_TYPE.EXT2, "ext2"),
    (FILESYSTEM_TYPE.EXT4, "ext4"),
    # XFS, FAT32, and VFAT are typically written all-caps. However, the UI/UX
    # team want them displayed lower-case to fit with the style guidelines.
    (FILESYSTEM_TYPE.XFS, "xfs"),
    (FILESYSTEM_TYPE.FAT32, "fat32"),
    (FILESYSTEM_TYPE.VFAT, "vfat"),
    (FILESYSTEM_TYPE.LVM_PV, "lvm"),
    (FILESYSTEM_TYPE.RAID, "raid"),
    (FILESYSTEM_TYPE.RAID_SPARE, "raid-spare"),
    (FILESYSTEM_TYPE.BCACHE_CACHE, "bcache-cache"),
    (FILESYSTEM_TYPE.BCACHE_BACKING, "bcache-backing"),
    (FILESYSTEM_TYPE.SWAP, "swap"),
    (FILESYSTEM_TYPE.RAMFS, "ramfs"),
    (FILESYSTEM_TYPE.TMPFS, "tmpfs"),
    (FILESYSTEM_TYPE.BTRFS, "btrfs"),
    (FILESYSTEM_TYPE.ZFSROOT, "zfsroot"),
    (FILESYSTEM_TYPE.VMFS6, "vmfs6"),
)


# Django choices for FILESYSTEM_TYPE: sequence of tuples (key, UI
# representation). When a user does a format operation only these values
# are allowed. The other values are reserved for internal use.
FILESYSTEM_FORMAT_TYPE_CHOICES = (
    (FILESYSTEM_TYPE.EXT2, "ext2"),
    (FILESYSTEM_TYPE.EXT4, "ext4"),
    # XFS, FAT32, and VFAT are typically written all-caps. However, the UI/UX
    # team want them displayed lower-case to fit with the style guidelines.
    (FILESYSTEM_TYPE.XFS, "xfs"),
    (FILESYSTEM_TYPE.FAT32, "fat32"),
    (FILESYSTEM_TYPE.VFAT, "vfat"),
    (FILESYSTEM_TYPE.SWAP, "swap"),
    (FILESYSTEM_TYPE.RAMFS, "ramfs"),
    (FILESYSTEM_TYPE.TMPFS, "tmpfs"),
    (FILESYSTEM_TYPE.BTRFS, "btrfs"),
    (FILESYSTEM_TYPE.ZFSROOT, "zfsroot"),
)


FILESYSTEM_FORMAT_TYPE_CHOICES_DICT = OrderedDict(
    FILESYSTEM_FORMAT_TYPE_CHOICES
)


class FILESYSTEM_GROUP_TYPE:
    """The vocabulary of possible partition types for `FilesystemGroup`."""

    # LVM volume group.
    LVM_VG = "lvm-vg"

    # RAID level 0
    RAID_0 = "raid-0"

    # RAID level 1
    RAID_1 = "raid-1"

    # RAID level 5
    RAID_5 = "raid-5"

    # RAID level 6
    RAID_6 = "raid-6"

    # RAID level 10
    RAID_10 = "raid-10"

    # Bcache
    BCACHE = "bcache"

    # VMFS6
    VMFS6 = "vmfs6"


FILESYSTEM_GROUP_RAID_TYPES = [
    FILESYSTEM_GROUP_TYPE.RAID_0,
    FILESYSTEM_GROUP_TYPE.RAID_1,
    FILESYSTEM_GROUP_TYPE.RAID_5,
    FILESYSTEM_GROUP_TYPE.RAID_6,
    FILESYSTEM_GROUP_TYPE.RAID_10,
]

# Django choices for FILESYSTEM_GROUP_RAID_TYPES: sequence of tuples (key, UI
# representation).
FILESYSTEM_GROUP_RAID_TYPE_CHOICES = (
    (FILESYSTEM_GROUP_TYPE.RAID_0, "RAID 0"),
    (FILESYSTEM_GROUP_TYPE.RAID_1, "RAID 1"),
    (FILESYSTEM_GROUP_TYPE.RAID_5, "RAID 5"),
    (FILESYSTEM_GROUP_TYPE.RAID_6, "RAID 6"),
    (FILESYSTEM_GROUP_TYPE.RAID_10, "RAID 10"),
)

# Django choices for FILESYSTEM_GROUP_TYPE: sequence of tuples (key, UI
# representation).
FILESYSTEM_GROUP_TYPE_CHOICES = FILESYSTEM_GROUP_RAID_TYPE_CHOICES + (
    (FILESYSTEM_GROUP_TYPE.LVM_VG, "LVM VG"),
    (FILESYSTEM_GROUP_TYPE.BCACHE, "Bcache"),
    (FILESYSTEM_GROUP_TYPE.VMFS6, "VMFS6"),
)


class CACHE_MODE_TYPE:
    """The vocabulary of possible types of cache."""

    WRITEBACK = "writeback"
    WRITETHROUGH = "writethrough"
    WRITEAROUND = "writearound"


# Django choices for CACHE_MODE_TYPE: sequence of tuples (key, UI
# representation).
CACHE_MODE_TYPE_CHOICES = enum_choices(
    CACHE_MODE_TYPE, transform=cast(Callable[[str], str], str.capitalize)
)


class INTERFACE_TYPE:
    """The vocabulary of possible types for `Interface`."""

    # Note: when these constants are changed, the custom SQL query
    # in StaticIPAddressManager.get_hostname_ip_mapping() must also
    # be changed.
    PHYSICAL = "physical"
    BOND = "bond"
    BRIDGE = "bridge"
    VLAN = "vlan"
    ALIAS = "alias"
    # Interface that is created when it is not linked to a node.
    UNKNOWN = "unknown"


INTERFACE_TYPE_CHOICES = (
    (INTERFACE_TYPE.PHYSICAL, "Physical interface"),
    (INTERFACE_TYPE.BOND, "Bond"),
    (INTERFACE_TYPE.BRIDGE, "Bridge"),
    (INTERFACE_TYPE.VLAN, "VLAN interface"),
    (INTERFACE_TYPE.ALIAS, "Alias"),
    (INTERFACE_TYPE.UNKNOWN, "Unknown"),
)


INTERFACE_TYPE_CHOICES_DICT = OrderedDict(INTERFACE_TYPE_CHOICES)


class INTERFACE_LINK_TYPE:
    """The vocabulary of possible types to link a `Subnet` to a `Interface`."""

    AUTO = "auto"
    DHCP = "dhcp"
    STATIC = "static"
    LINK_UP = "link_up"


INTERFACE_LINK_TYPE_CHOICES = (
    (INTERFACE_LINK_TYPE.AUTO, "Auto IP"),
    (INTERFACE_LINK_TYPE.DHCP, "DHCP"),
    (INTERFACE_LINK_TYPE.STATIC, "Static IP"),
    (INTERFACE_LINK_TYPE.LINK_UP, "Link up"),
)


class BOND_MODE:
    BALANCE_RR = "balance-rr"
    ACTIVE_BACKUP = "active-backup"
    BALANCE_XOR = "balance-xor"
    BROADCAST = "broadcast"
    LINK_AGGREGATION = "802.3ad"
    BALANCE_TLB = "balance-tlb"
    BALANCE_ALB = "balance-alb"


BOND_MODE_CHOICES = (
    (BOND_MODE.BALANCE_RR, BOND_MODE.BALANCE_RR),
    (BOND_MODE.ACTIVE_BACKUP, BOND_MODE.ACTIVE_BACKUP),
    (BOND_MODE.BALANCE_XOR, BOND_MODE.BALANCE_XOR),
    (BOND_MODE.BROADCAST, BOND_MODE.BROADCAST),
    (BOND_MODE.LINK_AGGREGATION, BOND_MODE.LINK_AGGREGATION),
    (BOND_MODE.BALANCE_TLB, BOND_MODE.BALANCE_TLB),
    (BOND_MODE.BALANCE_ALB, BOND_MODE.BALANCE_ALB),
)


class BOND_LACP_RATE:
    SLOW = "slow"
    FAST = "fast"


BOND_LACP_RATE_CHOICES = (
    (BOND_LACP_RATE.FAST, BOND_LACP_RATE.FAST),
    (BOND_LACP_RATE.SLOW, BOND_LACP_RATE.SLOW),
)


class BOND_XMIT_HASH_POLICY:
    LAYER2 = "layer2"
    LAYER2_3 = "layer2+3"
    LAYER3_4 = "layer3+4"
    ENCAP2_3 = "encap2+3"
    ENCAP3_4 = "encap3+4"


BOND_XMIT_HASH_POLICY_CHOICES = (
    (BOND_XMIT_HASH_POLICY.LAYER2, BOND_XMIT_HASH_POLICY.LAYER2),
    (BOND_XMIT_HASH_POLICY.LAYER2_3, BOND_XMIT_HASH_POLICY.LAYER2_3),
    (BOND_XMIT_HASH_POLICY.LAYER3_4, BOND_XMIT_HASH_POLICY.LAYER3_4),
    (BOND_XMIT_HASH_POLICY.ENCAP2_3, BOND_XMIT_HASH_POLICY.ENCAP2_3),
    (BOND_XMIT_HASH_POLICY.ENCAP3_4, BOND_XMIT_HASH_POLICY.ENCAP3_4),
)


class BRIDGE_TYPE:
    """A bridge type."""

    STANDARD = "standard"
    OVS = "ovs"


BRIDGE_TYPE_CHOICES = (
    (BRIDGE_TYPE.STANDARD, BRIDGE_TYPE.STANDARD),
    (BRIDGE_TYPE.OVS, BRIDGE_TYPE.OVS),
)

BRIDGE_TYPE_CHOICES_DICT = OrderedDict(BRIDGE_TYPE_CHOICES)


class SERVICE_STATUS:
    """Service statuses"""

    # Status of the service is not known.
    UNKNOWN = "unknown"
    # Service is running and operational.
    RUNNING = "running"
    # Service is running but is in a degraded state.
    DEGRADED = "degraded"
    # Service is dead. (Should be on but is off).
    DEAD = "dead"
    # Service is off. (Should be off and is off).
    OFF = "off"


SERVICE_STATUS_CHOICES = enum_choices(
    SERVICE_STATUS, transform=cast(Callable[[str], str], str.capitalize)
)


class KEYS_PROTOCOL_TYPE:
    """The vocabulary of possible protocol types for `KeySource`."""

    # Launchpad
    LP = "lp"

    # Github
    GH = "gh"


KEYS_PROTOCOL_TYPE_CHOICES = (
    (KEYS_PROTOCOL_TYPE.LP, "launchpad"),
    (KEYS_PROTOCOL_TYPE.GH, "github"),
)


class NODE_METADATA:
    # Record metadata using a variant of SNMP OID names. See:
    #     http://www.ietf.org/rfc/rfc2737.txt
    # (eg. turn entPhysicalModelName into "physical-model-name").
    PHYSICAL_HARDWARE_REV = "physical-hardware-rev"
    PHYSICAL_MFG_NAME = "physical-mfg-name"
    PHYSICAL_MODEL_NAME = "physical-model-name"
    PHYSICAL_NAME = "physical-name"
    PHYSICAL_SERIAL_NUM = "physical-serial-num"
    VENDOR_NAME = "vendor-name"


class ENDPOINT:
    API = 0
    UI = 1
    CLI = 2


ENDPOINT_CHOICES = (
    (ENDPOINT.API, "API"),
    (ENDPOINT.UI, "WebUI"),
    (ENDPOINT.CLI, "CLI"),
)


class NODE_DEVICE_BUS:
    PCIE = 1
    USB = 2


NODE_DEVICE_BUS_CHOICES = (
    (NODE_DEVICE_BUS.PCIE, "PCIE"),
    (NODE_DEVICE_BUS.USB, "USB"),
)
