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
    'IPADDRESS_TYPE',
    'NODEGROUP_STATUS',
    'NODEGROUP_STATUS_CHOICES',
    'NODEGROUPINTERFACE_MANAGEMENT',
    'NODEGROUPINTERFACE_MANAGEMENT_CHOICES',
    'NODEGROUPINTERFACE_MANAGEMENT_CHOICES_DICT',
    'NODE_PERMISSION',
    'NODE_STATUS',
    'NODE_STATUS_CHOICES',
    'NODE_STATUS_CHOICES_DICT',
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


class NODE_STATUS:
    """The vocabulary of a `Node`'s possible statuses."""
    # A node starts out as READY.
    DEFAULT = 0

    #: The node has been created and has a system ID assigned to it.
    NEW = 0
    #: Testing and other commissioning steps are taking place.
    COMMISSIONING = 1
    #: Smoke or burn-in testing has a found a problem.
    FAILED_TESTS = 2
    #: The node can't be contacted.
    MISSING = 3
    #: The node is in the general pool ready to be deployed.
    READY = 4
    #: The node is ready for named deployment.
    RESERVED = 5
    #: The node is powering a service from a charm or is ready for use with
    #: a fresh Ubuntu install.
    ALLOCATED = 6
    #: The node has been removed from service manually until an admin
    #: overrides the retirement.
    RETIRED = 7
    #: The node is broken: a step in the node lifecyle failed.
    #: More details can be found in the node's event log.
    BROKEN = 8


# Django choices for NODE_STATUS: sequence of tuples (key, UI
# representation).
NODE_STATUS_CHOICES = (
    (NODE_STATUS.NEW, "New"),
    (NODE_STATUS.COMMISSIONING, "Commissioning"),
    (NODE_STATUS.FAILED_TESTS, "Failed tests"),
    (NODE_STATUS.MISSING, "Missing"),
    (NODE_STATUS.READY, "Ready"),
    (NODE_STATUS.RESERVED, "Reserved"),
    (NODE_STATUS.ALLOCATED, "Allocated"),
    (NODE_STATUS.RETIRED, "Retired"),
    (NODE_STATUS.BROKEN, "Broken"),
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
    (NODEGROUPINTERFACE_MANAGEMENT.DHCP, "Manage DHCP"),
    (NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS, "Manage DHCP and DNS"),
    )


NODEGROUPINTERFACE_MANAGEMENT_CHOICES_DICT = (
    OrderedDict(NODEGROUPINTERFACE_MANAGEMENT_CHOICES))


class IPADDRESS_TYPE:
    """The vocabulary of possible types of `StaticIPAddress`."""
    # Automatically assigned.
    AUTO = 0

    # Pre-assigned and permanent until removed.
    STICKY = 1

    # Not associated to hardware managed by MAAS.
    UNMANAGED = 2

    # Additional IP requested by a user for a node.
    EXTRA = 3

    # Reserved by a user, no DHCP map required in MAAS.
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


class BOOT_RESOURCE_FILE_TYPE:
    """The vocabulary of possible file types for `BootResource`."""
    #: Tarball of root image.
    TGZ = 'tgz'

    #: Tarball of dd image.
    DDTGZ = 'dd-tgz'

    # Following are not allowed on user upload. Only used for syncing
    # from another simplestreams source. (Most likely maas.ubuntu.com)

    #: Root Image (gets converted to root-image root-tgz, on Cluster)
    ROOT_IMAGE = 'root-image.gz'

    #: Boot Kernel (ISCSI kernel)
    BOOT_KERNEL = 'boot-kernel'

    #: Boot Initrd (ISCSI initrd)
    BOOT_INITRD = 'boot-initrd'

    #: DI Kernel (Debian Installer kernel)
    DI_KERNEL = 'di-kernel'

    #: DI Initrd (Debian Installer initrd)
    DI_INITRD = 'di-initrd'


# Django choices for BOOT_RESOURCE_FILE_TYPE: sequence of tuples (key, UI
# representation).
BOOT_RESOURCE_FILE_TYPE_CHOICES = (
    (BOOT_RESOURCE_FILE_TYPE.TGZ, "Root Image (tar.gz)"),
    (BOOT_RESOURCE_FILE_TYPE.DDTGZ, "Root Compreseed DD (dd -> tar.gz)"),
    (BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE, "Compressed Root Image"),
    (BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL, "Linux ISCSI Kernel"),
    (BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD, "Initial ISCSI Ramdisk"),
    (BOOT_RESOURCE_FILE_TYPE.DI_KERNEL, "Linux DI Kernel"),
    (BOOT_RESOURCE_FILE_TYPE.DI_INITRD, "Initial DI Ramdisk"),
    )


# Django choices for BOOT_RESOURCE_FILE_TYPE: sequence of tuples (key, UI
# representation). (Choices allowed for user uploading.)
BOOT_RESOURCE_FILE_TYPE_CHOICES_UPLOAD = (
    (BOOT_RESOURCE_FILE_TYPE.TGZ, "Root Image (tar.gz)"),
    (BOOT_RESOURCE_FILE_TYPE.DDTGZ, "Root Compreseed DD (dd -> tar.gz)"),
    )
