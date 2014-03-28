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
    'COMMISSIONING_DISTRO_SERIES_CHOICES',
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


class DISTRO_SERIES:
    """List of supported ubuntu releases."""
    #:
    default = ''
    #:
    precise = 'precise'
    #:
    quantal = 'quantal'
    #:
    raring = 'raring'
    #:
    saucy = 'saucy'
    #:
    trusty = 'trusty'

DISTRO_SERIES_CHOICES = (
    (DISTRO_SERIES.default, 'Default Ubuntu Release'),
    (DISTRO_SERIES.precise, 'Ubuntu 12.04 LTS "Precise Pangolin"'),
    (DISTRO_SERIES.quantal, 'Ubuntu 12.10 "Quantal Quetzal"'),
    (DISTRO_SERIES.raring, 'Ubuntu 13.04 "Raring Ringtail"'),
    (DISTRO_SERIES.saucy, 'Ubuntu 13.10 "Saucy Salamander"'),
    (DISTRO_SERIES.trusty, 'Ubuntu 14.04 LTS "Trusty Tahr"'),
)


COMMISSIONING_DISTRO_SERIES_CHOICES = (
    (DISTRO_SERIES.trusty, dict(DISTRO_SERIES_CHOICES)[DISTRO_SERIES.trusty]),
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
