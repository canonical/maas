# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Enumerations meaningful to the maasserver application."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'CACHE_MODE_TYPE',
    'CACHE_MODE_TYPE_CHOICES',
    'COMPONENT',
    'FILESYSTEM_GROUP_TYPE',
    'FILESYSTEM_GROUP_TYPE_CHOICES',
    'FILESYSTEM_TYPE',
    'FILESYSTEM_TYPE_CHOICES',
    'INTERFACE_TYPE',
    'INTERFACE_TYPE_CHOICES',
    'INTERFACE_TYPE_CHOICES_DICT',
    'IPADDRESS_TYPE',
    'NODEGROUP_STATUS',
    'NODEGROUP_STATUS_CHOICES',
    'NODEGROUPINTERFACE_MANAGEMENT',
    'NODEGROUPINTERFACE_MANAGEMENT_CHOICES',
    'NODEGROUPINTERFACE_MANAGEMENT_CHOICES_DICT',
    'NODE_PERMISSION',
    'NODE_BOOT',
    'NODE_STATUS',
    'NODE_STATUS_CHOICES',
    'NODE_STATUS_CHOICES_DICT',
    'PARTITION_TABLE_TYPE',
    'PARTITION_TABLE_TYPE_CHOICES',
    'PRESEED_TYPE',
    'USERDATA_TYPE',
    ]

from collections import OrderedDict

# *** IMPORTANT ***
# Note to all ye who enter here: comments beginning with #: are special
# to Sphinx. They are extracted and form part of the documentation of
# the field they directly precede.


class COMPONENT:
    """Major moving parts of the application that may have failure states."""
    PSERV = 'provisioning server'
    IMPORT_PXE_FILES = 'maas-import-pxe-files script'
    CLUSTERS = 'clusters'
    REGION_IMAGE_IMPORT = 'Image importer'


class NODE_STATUS:
    """The vocabulary of a `Node`'s possible statuses."""
    #: A node starts out as NEW (DEFAULT is an alias for NEW).
    DEFAULT = 0

    #: The node has been created and has a system ID assigned to it.
    NEW = 0
    #: Testing and other commissioning steps are taking place.
    COMMISSIONING = 1
    #: The commissioning step failed.
    FAILED_COMMISSIONING = 2
    #: The node can't be contacted.
    MISSING = 3
    #: The node is in the general pool ready to be deployed.
    READY = 4
    #: The node is ready for named deployment.
    RESERVED = 5
    #: The node has booted into the operating system of its owner's choice
    #: and is ready for use.
    DEPLOYED = 6
    #: The node has been removed from service manually until an admin
    #: overrides the retirement.
    RETIRED = 7
    #: The node is broken: a step in the node lifecyle failed.
    #: More details can be found in the node's event log.
    BROKEN = 8
    #: The node is being installed.
    DEPLOYING = 9
    #: The node has been allocated to a user and is ready for deployment.
    ALLOCATED = 10
    #: The deployment of the node failed.
    FAILED_DEPLOYMENT = 11
    #: The node is powering down after a release request.
    RELEASING = 12
    #: The releasing of the node failed.
    FAILED_RELEASING = 13
    #: The node is erasing its disks.
    DISK_ERASING = 14
    #: The node failed to erase its disks.
    FAILED_DISK_ERASING = 15


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
)


NODE_STATUS_CHOICES_DICT = OrderedDict(NODE_STATUS_CHOICES)


# NODE_STATUS when the node is owned by an owner and its is not commissioning.
ALLOCATED_NODE_STATUSES = [
    NODE_STATUS.ALLOCATED,
    NODE_STATUS.DEPLOYING,
    NODE_STATUS.DEPLOYED,
    NODE_STATUS.FAILED_DEPLOYMENT,
    NODE_STATUS.RELEASING,
    NODE_STATUS.FAILED_RELEASING,
    NODE_STATUS.DISK_ERASING,
    NODE_STATUS.FAILED_DISK_ERASING,
]


class NODE_PERMISSION:
    """Permissions relating to nodes."""
    VIEW = 'view_node'
    EDIT = 'edit_node'
    ADMIN = 'admin_node'


class NODE_BOOT:
    """Types of booting methods a node can use."""
    FASTPATH = 'fastpath'  #: http://launchpad.net/curtin
    DEBIAN = 'di'


# Django choices for NODE_BOOT: sequence of tuples (key, UI
# representation).
NODE_BOOT_CHOICES = (
    (NODE_BOOT.FASTPATH, "Fastpath Installer"),
    (NODE_BOOT.DEBIAN, "Debian Installer"),
)


class PRESEED_TYPE:
    """Types of preseed documents that can be generated."""
    DEFAULT = ''
    COMMISSIONING = 'commissioning'
    ENLIST = 'enlist'
    CURTIN = 'curtin'


class USERDATA_TYPE:
    """Types of user-data documents that can be generated."""
    ENLIST = 'enlist_userdata'
    CURTIN = 'curtin_userdata'


class NODEGROUP_STATUS:
    """The vocabulary of a `NodeGroup`'s possible statuses."""
    #: A nodegroup starts out as ``ENABLED``.
    DEFAULT = 1

    #: An ENABLED cluster is one that should be operational.
    ENABLED = 1
    #: A DISABLED cluster should not sync images or deploy new nodes.
    DISABLED = 2


# Django choices for NODEGROUP_STATUS: sequence of tuples (key, UI
# representation).
NODEGROUP_STATUS_CHOICES = (
    (NODEGROUP_STATUS.ENABLED, "Enabled"),
    (NODEGROUP_STATUS.DISABLED, "Disabled"),
    )


class NODEGROUP_STATE:
    """The vocabulary of a `NodeGroup`'s possible state."""
    #:
    DISCONNECTED = "Disconnected"
    #:
    OUT_OF_SYNC = "Out-of-sync"
    #:
    SYNCING = "Syncing"
    #:
    SYNCED = "Synced"


class NODEGROUPINTERFACE_MANAGEMENT:
    """The vocabulary of a `NodeGroupInterface`'s possible statuses."""
    # A nodegroupinterface starts out as UNMANAGED.
    DEFAULT = 0
    #: Do not manage DHCP or DNS for this interface.
    UNMANAGED = 0
    #: Manage DHCP for this interface.
    DHCP = 1
    #: Manage DHCP and DNS for this interface.
    DHCP_AND_DNS = 2


# Django choices for NODEGROUP_STATUS: sequence of tuples (key, UI
# representation).
NODEGROUPINTERFACE_MANAGEMENT_CHOICES = (
    (NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED, "Unmanaged"),
    (NODEGROUPINTERFACE_MANAGEMENT.DHCP, "DHCP"),
    (NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS, "DHCP and DNS"),
    )


NODEGROUPINTERFACE_MANAGEMENT_CHOICES_DICT = (
    OrderedDict(NODEGROUPINTERFACE_MANAGEMENT_CHOICES))


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


IPADDRESS_TYPE_CHOICES = (
    (IPADDRESS_TYPE.AUTO, "Auto"),
    (IPADDRESS_TYPE.STICKY, "Sticky"),
    (IPADDRESS_TYPE.USER_RESERVED, "User reserved"),
    (IPADDRESS_TYPE.DHCP, "DHCP"),
    (IPADDRESS_TYPE.DISCOVERED, "Discovered"),
    )


IPADDRESS_TYPE_CHOICES_DICT = OrderedDict(IPADDRESS_TYPE_CHOICES)


class POWER_STATE:

    # Node is on
    ON = 'on'

    # Node is off
    OFF = 'off'

    # Node is power state is unknown
    UNKNOWN = 'unknown'

    # Error getting the nodes power state
    ERROR = 'error'


POWER_STATE_CHOICES = (
    (POWER_STATE.ON, "On"),
    (POWER_STATE.OFF, "Off"),
    (POWER_STATE.UNKNOWN, "Unknown"),
    (POWER_STATE.ERROR, "Error"),
    )


class BOOT_RESOURCE_TYPE:
    """The vocabulary of possible types for `BootResource`."""
    # Downloaded from `BootSources`.
    SYNCED = 0

    # Generate by MAAS.
    GENERATED = 1

    # Uploaded by User.
    UPLOADED = 2


# Django choices for BOOT_RESOURCE_TYPE: sequence of tuples (key, UI
# representation).
BOOT_RESOURCE_TYPE_CHOICES = (
    (BOOT_RESOURCE_TYPE.SYNCED, "Synced"),
    (BOOT_RESOURCE_TYPE.GENERATED, "Generated"),
    (BOOT_RESOURCE_TYPE.UPLOADED, "Uploaded"),
    )


BOOT_RESOURCE_TYPE_CHOICES_DICT = OrderedDict(BOOT_RESOURCE_TYPE_CHOICES)


class BOOT_RESOURCE_FILE_TYPE:
    """The vocabulary of possible file types for `BootResource`."""
    #: Tarball of root image.
    ROOT_TGZ = 'root-tgz'

    #: Tarball of dd image.
    ROOT_DD = 'root-dd'

    # Following are not allowed on user upload. Only used for syncing
    # from another simplestreams source. (Most likely maas.ubuntu.com)

    #: Root Image (gets converted to root-image root-tgz, on Cluster)
    ROOT_IMAGE = 'root-image.gz'

    #: Boot Kernel (ISCSI kernel)
    BOOT_KERNEL = 'boot-kernel'

    #: Boot Initrd (ISCSI initrd)
    BOOT_INITRD = 'boot-initrd'

    #: Boot DTB (ISCSI dtb)
    BOOT_DTB = 'boot-dtb'

    #: DI Kernel (Debian Installer kernel)
    DI_KERNEL = 'di-kernel'

    #: DI Initrd (Debian Installer initrd)
    DI_INITRD = 'di-initrd'

    #: DI DTB (Debian Installer dtb)
    DI_DTB = 'di-dtb'


# Django choices for BOOT_RESOURCE_FILE_TYPE: sequence of tuples (key, UI
# representation).
BOOT_RESOURCE_FILE_TYPE_CHOICES = (
    (BOOT_RESOURCE_FILE_TYPE.ROOT_TGZ, "Root Image (tar.gz)"),
    (BOOT_RESOURCE_FILE_TYPE.ROOT_DD, "Root Compressed DD (dd -> tar.gz)"),
    (BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE, "Compressed Root Image"),
    (BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL, "Linux ISCSI Kernel"),
    (BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD, "Initial ISCSI Ramdisk"),
    (BOOT_RESOURCE_FILE_TYPE.BOOT_DTB, "ISCSI Device Tree Blob"),
    (BOOT_RESOURCE_FILE_TYPE.DI_KERNEL, "Linux DI Kernel"),
    (BOOT_RESOURCE_FILE_TYPE.DI_INITRD, "Initial DI Ramdisk"),
    (BOOT_RESOURCE_FILE_TYPE.DI_DTB, "DI Device Tree Blob"),
    )


class PARTITION_TABLE_TYPE:
    """The vocabulary of possible partition types for `PartitionTable`."""
    #: GUID partition table.
    GPT = 'GPT'

    #: Master boot record..
    MBR = 'MBR'


# Django choices for PARTITION_TABLE_TYPE: sequence of tuples (key, UI
# representation).
PARTITION_TABLE_TYPE_CHOICES = (
    (PARTITION_TABLE_TYPE.MBR, "Master boot record"),
    (PARTITION_TABLE_TYPE.GPT, "GUID parition table"),
    )


class FILESYSTEM_TYPE:
    """The vocabulary of possible partition types for `Filesystem`."""
    #: Third extended filesystem.
    EXT3 = 'ext3'

    #: Fourth extended filesystem.
    EXT4 = 'ext4'

    #: FAT32
    FAT32 = 'fat32'

    #: LVM Physical Volume.
    LVM_PV = 'lvm-pv'

    #: RAID.
    RAID = 'raid'

    #: RAID spare.
    RAID_SPARE = 'raid-spare'

    #: Bcache cache.
    BCACHE_CACHE = 'bcache-cache'

    #: Bcache backing.
    BCACHE_BACKING = 'bcache-backing'


# Django choices for FILESYSTEM_TYPE: sequence of tuples (key, UI
# representation).
FILESYSTEM_TYPE_CHOICES = (
    (FILESYSTEM_TYPE.EXT3, "ext3"),
    (FILESYSTEM_TYPE.EXT4, "ext4"),
    (FILESYSTEM_TYPE.FAT32, "fat32"),
    (FILESYSTEM_TYPE.LVM_PV, "lvm"),
    (FILESYSTEM_TYPE.RAID, "raid"),
    (FILESYSTEM_TYPE.RAID_SPARE, "raid-spare"),
    (FILESYSTEM_TYPE.BCACHE_CACHE, "bcache-cache"),
    (FILESYSTEM_TYPE.BCACHE_BACKING, "bcache-backing"),
    )


# Django choices for FILESYSTEM_TYPE: sequence of tuples (key, UI
# representation). When a user does a format operation only these values
# are allowed. The other values are reserved for internal use.
FILESYSTEM_FORMAT_TYPE_CHOICES = (
    (FILESYSTEM_TYPE.EXT3, "ext3"),
    (FILESYSTEM_TYPE.EXT4, "ext4"),
    (FILESYSTEM_TYPE.FAT32, "fat32"),
    )


FILESYSTEM_FORMAT_TYPE_CHOICES_DICT = OrderedDict(
    FILESYSTEM_FORMAT_TYPE_CHOICES)


class FILESYSTEM_GROUP_TYPE:
    """The vocabulary of possible partition types for `FilesystemGroup`."""
    #: LVM volume group.
    LVM_VG = 'lvm-vg'

    #: RAID level 0
    RAID_0 = 'raid-0'

    #: RAID level 1
    RAID_1 = 'raid-1'

    #: RAID level 5
    RAID_5 = 'raid-5'

    #: RAID level 6
    RAID_6 = 'raid-6'

    #: Bcache
    BCACHE = 'bcache'


FILESYSTEM_GROUP_RAID_TYPES = [
    FILESYSTEM_GROUP_TYPE.RAID_0,
    FILESYSTEM_GROUP_TYPE.RAID_1,
    FILESYSTEM_GROUP_TYPE.RAID_5,
    FILESYSTEM_GROUP_TYPE.RAID_6,
    ]

# Django choices for FILESYSTEM_GROUP_RAID_TYPES: sequence of tuples (key, UI
# representation).
FILESYSTEM_GROUP_RAID_TYPE_CHOICES = (
    (FILESYSTEM_GROUP_TYPE.RAID_0, "RAID 0"),
    (FILESYSTEM_GROUP_TYPE.RAID_1, "RAID 1"),
    (FILESYSTEM_GROUP_TYPE.RAID_5, "RAID 5"),
    (FILESYSTEM_GROUP_TYPE.RAID_6, "RAID 6"),
    )

# Django choices for FILESYSTEM_GROUP_TYPE: sequence of tuples (key, UI
# representation).
FILESYSTEM_GROUP_TYPE_CHOICES = FILESYSTEM_GROUP_RAID_TYPE_CHOICES + (
    (FILESYSTEM_GROUP_TYPE.LVM_VG, "LVM VG"),
    (FILESYSTEM_GROUP_TYPE.BCACHE, "Bcache"),
    )


class CACHE_MODE_TYPE:
    """The vocabulary of possible types of cache."""
    WRITEBACK = 'writeback'
    WRITETHROUGH = 'writethrough'
    WRITEAROUND = 'writearound'


# Django choices for CACHE_MODE_TYPE: sequence of tuples (key, UI
# representation).
CACHE_MODE_TYPE_CHOICES = (
    (CACHE_MODE_TYPE.WRITEBACK, 'Writeback'),
    (CACHE_MODE_TYPE.WRITETHROUGH, 'Writethrough'),
    (CACHE_MODE_TYPE.WRITEAROUND, 'Writearound'),
    )


class INTERFACE_TYPE:
    """The vocabulary of possible types for `Interface`."""
    # Note: when these constants are changed, the custom SQL query
    # in StaticIPAddressManager.get_hostname_ip_mapping() must also
    # be changed.
    PHYSICAL = 'physical'
    BOND = 'bond'
    VLAN = 'vlan'
    ALIAS = 'alias'
    # Interface that is created when it is not linked to a node.
    UNKNOWN = 'unknown'


INTERFACE_TYPE_CHOICES = (
    (INTERFACE_TYPE.PHYSICAL, "Physical interface"),
    (INTERFACE_TYPE.BOND, "Bond"),
    (INTERFACE_TYPE.VLAN, "VLAN interface"),
    (INTERFACE_TYPE.ALIAS, "Alias"),
    (INTERFACE_TYPE.UNKNOWN, "Unknown"),
    )


INTERFACE_TYPE_CHOICES_DICT = OrderedDict(INTERFACE_TYPE_CHOICES)


class INTERFACE_LINK_TYPE:
    """The vocabulary of possible types to link a `Subnet` to a `Interface`."""
    AUTO = 'auto'
    DHCP = 'dhcp'
    STATIC = 'static'
    LINK_UP = 'link_up'


INTERFACE_LINK_TYPE_CHOICES = (
    (INTERFACE_LINK_TYPE.AUTO, "Auto IP"),
    (INTERFACE_LINK_TYPE.DHCP, "DHCP"),
    (INTERFACE_LINK_TYPE.STATIC, "Static IP"),
    (INTERFACE_LINK_TYPE.LINK_UP, "Link up"),
    )
