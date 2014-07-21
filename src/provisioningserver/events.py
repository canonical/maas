# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Event catalog."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'EVENT_DETAILS',
    'EVENT_TYPES',
    ]

from collections import namedtuple
from logging import (
    ERROR,
    INFO,
    )


class EVENT_TYPES:
    # Power-related events.
    NODE_POWERED_ON = 'NODE_POWERED_ON'
    NODE_POWERED_OFF = 'NODE_POWERED_OFF'
    NODE_POWER_ON_FAILED = 'NODE_POWER_ON_FAILED'
    NODE_POWER_OFF_FAILED = 'NODE_POWER_OFF_FAILED'


EventDetail = namedtuple("EventDetail", ("description", "level"))


EVENT_DETAILS = {
    # Event type -> EventDetail mapping.
    EVENT_TYPES.NODE_POWERED_ON: EventDetail(
        description="Node powered on",
        level=INFO,
    ),
    EVENT_TYPES.NODE_POWERED_OFF: EventDetail(
        description="Node powered off",
        level=INFO,
    ),
    EVENT_TYPES.NODE_POWER_ON_FAILED: EventDetail(
        description="Failed to power on node",
        level=ERROR,
    ),
    EVENT_TYPES.NODE_POWER_OFF_FAILED: EventDetail(
        description="Failed to power off node",
        level=ERROR,
    ),
}
