# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Enumerations meaningful to the maasserver application."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'ARCHITECTURE',
    'ARCHITECTURE_CHOICES',
    'ARCHITECTURE_CHOICES_DICT',
    'COMPONENT',
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
    'DISTRO_SERIES',
    'DISTRO_SERIES_CHOICES',
    ]

from collections import OrderedDict


class COMPONENT:
    """Major moving parts of the application that may have failure states."""
    PSERV = 'provisioning server'
    IMPORT_PXE_FILES = 'maas-import-pxe-files script'


class NODE_STATUS:
    """The vocabulary of a `Node`'s possible statuses."""
    # A node starts out as READY.
    DEFAULT_STATUS = 0

    #: The node has been created and has a system ID assigned to it.
    DECLARED = 0
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


# Django choices for NODE_STATUS: sequence of tuples (key, UI
# representation).
NODE_STATUS_CHOICES = (
    (NODE_STATUS.DECLARED, "Declared"),
    (NODE_STATUS.COMMISSIONING, "Commissioning"),
    (NODE_STATUS.FAILED_TESTS, "Failed tests"),
    (NODE_STATUS.MISSING, "Missing"),
    (NODE_STATUS.READY, "Ready"),
    (NODE_STATUS.RESERVED, "Reserved"),
    (NODE_STATUS.ALLOCATED, "Allocated"),
    (NODE_STATUS.RETIRED, "Retired"),
)


NODE_STATUS_CHOICES_DICT = OrderedDict(NODE_STATUS_CHOICES)


class NODE_AFTER_COMMISSIONING_ACTION:
    """The vocabulary of a `Node`'s possible value for its field
    after_commissioning_action.

    """
# TODO: document this when it's stabilized.
    #:
    DEFAULT = 0
    #:
    QUEUE = 0
    #:
    #CHECK = 1
    #:
    #DEPLOY_12_04 = 2


NODE_AFTER_COMMISSIONING_ACTION_CHOICES = (
    (NODE_AFTER_COMMISSIONING_ACTION.QUEUE,
        "Queue for dynamic allocation to services"),
    #(NODE_AFTER_COMMISSIONING_ACTION.CHECK,
    #    "Check compatibility and hold for future decision"),
    #(NODE_AFTER_COMMISSIONING_ACTION.DEPLOY_12_04,
    #    "Deploy with Ubuntu 12.04 LTS"),
)


NODE_AFTER_COMMISSIONING_ACTION_CHOICES_DICT = dict(
    NODE_AFTER_COMMISSIONING_ACTION_CHOICES)


class ARCHITECTURE:
    """List of supported architectures."""
    #:
    i386 = 'i386/generic'
    #:
    amd64 = 'amd64/generic'
    #:
    armhf_highbank = 'armhf/highbank'


# Architecture names.
ARCHITECTURE_CHOICES = (
    (ARCHITECTURE.i386, "i386"),
    (ARCHITECTURE.amd64, "amd64"),
    (ARCHITECTURE.armhf_highbank, "armhf/highbank"),
)


ARCHITECTURE_CHOICES_DICT = OrderedDict(ARCHITECTURE_CHOICES)


class DISTRO_SERIES:
    """List of supported ubuntu releases."""
    #:
    default = ''
    #:
    precise = 'precise'
    #:
    quantal = 'quantal'

DISTRO_SERIES_CHOICES = (
    (DISTRO_SERIES.default, 'Default Ubuntu Release'),
    (DISTRO_SERIES.precise, 'Ubuntu 12.04 LTS "Precise Pangolin"'),
    (DISTRO_SERIES.quantal, 'Ubuntu 12.10 "Quantal Quetzal"'),
)


class NODE_PERMISSION:
    """Permissions relating to nodes."""
    VIEW = 'view_node'
    EDIT = 'edit_node'
    ADMIN = 'admin_node'


class PRESEED_TYPE:
    """Types of preseed documents that can be generated."""
    DEFAULT = ''
    COMMISSIONING = 'commissioning'
    ENLIST = 'enlist'
    ENLIST_USERDATA = 'enlist_userdata'


class NODEGROUP_STATUS:
    """The vocabulary of a `NodeGroup`'s possible statuses."""
    # A nodegroup starts out as PENDING.
    DEFAULT_STATUS = 0

    #: The nodegroup has been created and awaits approval.
    PENDING = 0
    ACCEPTED = 1
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

    # Do not manage DHCP or DNS for this interface.
    UNMANAGED = 0
    # Manage DHCP for this interface.
    DHCP = 1
    # Manage DHCP and DNS for this interface.
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
