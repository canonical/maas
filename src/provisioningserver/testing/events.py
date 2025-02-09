# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test helpers for `provisioningserver.events`."""

from fixtures import Fixture

from provisioningserver import events


class EventTypesAllRegistered(Fixture):
    """Pretend that all event types are registered.

    This prevents `RegisterEventType` calls.
    """

    def setUp(self):
        super().setUp()
        types_registered = events.nodeEventHub._types_registered
        types_registered.update(events.EVENT_DETAILS)
        self.addCleanup(types_registered.clear)
