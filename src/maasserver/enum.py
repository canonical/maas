# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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
    'COMPONENT',
    'FILESYSTEM_GROUP_TYPE',
    'FILESYSTEM_GROUP_TYPE_CHOICES',
    'FILESYSTEM_TYPE',
    'FILESYSTEM_TYPE_CHOICES',
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
    #: A nodegroup starts out as ``PENDING``.
    DEFAULT = 0

    #: The nodegroup has been created and awaits approval.
    PENDING = 0
    #:
    ACCEPTED = 1
    #:
    REJECTED = 2


# Django choices for NODEGROUP_STATUS: sequence of tuples (key, UI
# representation).
NODEGROUP_STATUS_CHOICES = (
    (NODEGROUP_STATUS.PENDING, "Pending"),
    (NODEGROUP_STATUS.ACCEPTED, "Accepted"),
    (NODEGROUP_STATUS.REJECTED, "Rejected"),
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


class IPADDRESS_TYPE:
    """The vocabulary of possible types of `StaticIPAddress`."""
    # Automatically assigned IP address for a node or device.
    # MUST be within a cluster interface range.
    # MUST NOT be assigned to a MAC address with a STICKY address of
    # the same address family.
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

    #: LVM Physical Volume.
    LVM_PV = 'lvm-pv'


# Django choices for FILESYSTEM_TYPE: sequence of tuples (key, UI
# representation).
FILESYSTEM_TYPE_CHOICES = (
    (FILESYSTEM_TYPE.EXT3, "ext3"),
    (FILESYSTEM_TYPE.EXT4, "ext4"),
    (FILESYSTEM_TYPE.LVM_PV, "lvm"),
    )


class FILESYSTEM_GROUP_TYPE:
    """The vocabulary of possible partition types for `FilesystemGroup`."""
    #: LVM volume group.
    LVM_VG = 'lvm-vg'


# Django choices for FILESYSTEM_GROUP_TYPE: sequence of tuples (key, UI
# representation).
FILESYSTEM_GROUP_TYPE_CHOICES = (
    (FILESYSTEM_GROUP_TYPE.LVM_VG, "LVM VG"),
    )
