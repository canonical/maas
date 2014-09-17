# Copyright 2014 Canonical Ltd.  This software is licensed under the
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
    ]


from maasserver.enum import NODE_STATUS

# State transitions for when a node fails:
# Mapping between in-progress statuses and the corresponding failed
# statuses.
NODE_FAILURE_STATUS_TRANSITIONS = {
    NODE_STATUS.COMMISSIONING: NODE_STATUS.FAILED_COMMISSIONING,
    NODE_STATUS.DEPLOYING: NODE_STATUS.FAILED_DEPLOYMENT,
}

# Statuses that correspond to managed steps for which MAAS actively
# monitors that the status changes after a fixed period of time.
MONITORED_STATUSES = NODE_FAILURE_STATUS_TRANSITIONS.keys()


def get_failed_status(status):
    """Returns the failed status corresponding to the given status.

    If no corresponding failed status exists, return None.
    """
    return NODE_FAILURE_STATUS_TRANSITIONS.get(status, None)
