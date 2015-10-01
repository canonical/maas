# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test helpers for `provisioningserver.events`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "EventTypesAllRegistered",
]

from fixtures import Fixture
from provisioningserver import events


class EventTypesAllRegistered(Fixture):
    """Pretend that all event types are registered.

    This prevents `RegisterEventType` calls.
    """

    def setUp(self):
        super(EventTypesAllRegistered, self).setUp()
        types_registered = events.nodeEventHub._types_registered
        types_registered.update(events.EVENT_DETAILS)
        self.addCleanup(types_registered.clear)
