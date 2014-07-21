# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test event catalog."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    ]

from maastesting.testcase import MAASTestCase
from provisioningserver.events import (
    EVENT_DETAILS,
    EVENT_TYPES,
    EventDetail,
    )
from provisioningserver.utils import map_enum
from testtools.matchers import (
    AllMatch,
    IsInstance,
    )


class TestEvents(MAASTestCase):

    def test_every_event_has_details(self):
        all_events = map_enum(EVENT_TYPES)
        self.assertItemsEqual(all_events.values(), EVENT_DETAILS)
        self.assertThat(
            EVENT_DETAILS.values(), AllMatch(IsInstance(EventDetail)))
