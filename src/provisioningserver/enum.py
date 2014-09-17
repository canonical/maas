# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Enums."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'TIMER_TYPE',
    ]


class TIMER_TYPE:
    """Type of timers."""
    # Timer in charge of tracking a node's progress through a
    # MAAS-managed step.
    NODE_STATE_CHANGE = 0
