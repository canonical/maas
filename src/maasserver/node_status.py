# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Node status utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "get_failed_status",
    "is_failed_status",
    "NODE_TRANSITIONS",
    ]


from maasserver.enum import NODE_STATUS
from provisioningserver.utils.enum import map_enum

# Define valid node status transitions. This is enforced in the code, so
# get it right.
#
# The format is:
# {
#  old_status1: [
#      new_status11,
#      new_status12,
#      new_status13,
#      ],
# ...
# }
#
NODE_TRANSITIONS = {
    None: [
        NODE_STATUS.NEW,
        NODE_STATUS.MISSING,
        NODE_STATUS.RETIRED,
        ],
    NODE_STATUS.NEW: [
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.MISSING,
        NODE_STATUS.READY,
        NODE_STATUS.RETIRED,
        NODE_STATUS.BROKEN,
        ],
    NODE_STATUS.COMMISSIONING: [
        NODE_STATUS.FAILED_COMMISSIONING,
        NODE_STATUS.READY,
        NODE_STATUS.RETIRED,
        NODE_STATUS.MISSING,
        NODE_STATUS.NEW,
        NODE_STATUS.BROKEN,
        ],
    NODE_STATUS.FAILED_COMMISSIONING: [
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.MISSING,
        NODE_STATUS.RETIRED,
        NODE_STATUS.BROKEN,
        ],
    NODE_STATUS.READY: [
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.RESERVED,
        NODE_STATUS.RETIRED,
        NODE_STATUS.MISSING,
        NODE_STATUS.BROKEN,
        ],
    NODE_STATUS.RESERVED: [
        NODE_STATUS.READY,
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.RETIRED,
        NODE_STATUS.MISSING,
        NODE_STATUS.BROKEN,
        NODE_STATUS.DISK_ERASING,
        NODE_STATUS.RELEASING,
        ],
    NODE_STATUS.ALLOCATED: [
        NODE_STATUS.READY,
        NODE_STATUS.RETIRED,
        NODE_STATUS.MISSING,
        NODE_STATUS.BROKEN,
        NODE_STATUS.DEPLOYING,
        NODE_STATUS.DISK_ERASING,
        NODE_STATUS.RELEASING,
        ],
    NODE_STATUS.RELEASING: [
        NODE_STATUS.READY,
        NODE_STATUS.BROKEN,
        NODE_STATUS.MISSING,
        NODE_STATUS.FAILED_RELEASING,
        ],
    NODE_STATUS.DEPLOYING: [
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.MISSING,
        NODE_STATUS.BROKEN,
        NODE_STATUS.FAILED_DEPLOYMENT,
        NODE_STATUS.DEPLOYED,
        NODE_STATUS.READY,
        NODE_STATUS.DISK_ERASING,
        NODE_STATUS.RELEASING,
    ],
    NODE_STATUS.FAILED_DEPLOYMENT: [
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.MISSING,
        NODE_STATUS.BROKEN,
        NODE_STATUS.READY,
        NODE_STATUS.DISK_ERASING,
        NODE_STATUS.RELEASING,
    ],
    NODE_STATUS.DEPLOYED: [
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.MISSING,
        NODE_STATUS.BROKEN,
        NODE_STATUS.READY,
        NODE_STATUS.DISK_ERASING,
        NODE_STATUS.RELEASING,
    ],
    NODE_STATUS.MISSING: [
        NODE_STATUS.NEW,
        NODE_STATUS.READY,
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.BROKEN,
        ],
    NODE_STATUS.RETIRED: [
        NODE_STATUS.NEW,
        NODE_STATUS.READY,
        NODE_STATUS.MISSING,
        NODE_STATUS.BROKEN,
        ],
    NODE_STATUS.BROKEN: [
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.READY,
        NODE_STATUS.DISK_ERASING,
        NODE_STATUS.RELEASING,
        ],
    NODE_STATUS.FAILED_RELEASING: [
        NODE_STATUS.RELEASING,
        NODE_STATUS.DISK_ERASING,
        NODE_STATUS.READY,
        NODE_STATUS.BROKEN,
        ],
    NODE_STATUS.DISK_ERASING: [
        NODE_STATUS.BROKEN,
        NODE_STATUS.DISK_ERASING,
        NODE_STATUS.FAILED_DISK_ERASING,
        NODE_STATUS.READY,
        NODE_STATUS.RELEASING,
        ],
    NODE_STATUS.FAILED_DISK_ERASING: [
        NODE_STATUS.DISK_ERASING,
        NODE_STATUS.RELEASING,
        NODE_STATUS.BROKEN,
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.READY,
        ],
    }

# State transitions for when a node fails:
# Mapping between in-progress statuses and the corresponding failed
# statuses.
NODE_FAILURE_STATUS_TRANSITIONS = {
    NODE_STATUS.COMMISSIONING: NODE_STATUS.FAILED_COMMISSIONING,
    NODE_STATUS.DEPLOYING: NODE_STATUS.FAILED_DEPLOYMENT,
    NODE_STATUS.RELEASING: NODE_STATUS.FAILED_RELEASING,
    NODE_STATUS.DISK_ERASING: NODE_STATUS.FAILED_DISK_ERASING,
}

# Statuses that correspond to managed steps for which MAAS actively
# monitors that the status changes after a fixed period of time.
MONITORED_STATUSES = NODE_FAILURE_STATUS_TRANSITIONS.keys()

# Non-active statuses.
NON_MONITORED_STATUSES = set(
    map_enum(NODE_STATUS).values()).difference(set(MONITORED_STATUSES))


FAILED_STATUSES = NODE_FAILURE_STATUS_TRANSITIONS.values()

# Statuses that are like commissioning, in that we boot an
# an ephemeral environment of the latest LTS, run some scripts
# provided via user data, and report back success/fail status.
COMMISSIONING_LIKE_STATUSES = [
    NODE_STATUS.COMMISSIONING,
    NODE_STATUS.DISK_ERASING,
]

# Node state transitions that perform query actions. This is to keep the
# power state of the node up-to-date when transitions occur that do not
# perform a power action directly.
QUERY_TRANSITIONS = {
    None: [
        NODE_STATUS.NEW,
        ],
    NODE_STATUS.COMMISSIONING: [
        NODE_STATUS.FAILED_COMMISSIONING,
        NODE_STATUS.READY,
        ],
    NODE_STATUS.DEPLOYING: [
        NODE_STATUS.FAILED_DEPLOYMENT,
        NODE_STATUS.DEPLOYED,
    ],
    NODE_STATUS.DISK_ERASING: [
        NODE_STATUS.FAILED_DISK_ERASING,
        ],
    }


def get_failed_status(status):
    """Returns the failed status corresponding to the given status.

    If no corresponding failed status exists, return None.
    """
    return NODE_FAILURE_STATUS_TRANSITIONS.get(status, None)


def is_failed_status(status):
    """Returns if the status is a 'failed' status."""
    return status in FAILED_STATUSES
