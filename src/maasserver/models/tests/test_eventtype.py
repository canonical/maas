# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Event model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.models.eventtype import LOGGING_LEVELS
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class EventTypeTest(MAASServerTestCase):

    def test_displays_event_type_description(self):
        event_type = factory.make_event_type()
        self.assertIn(event_type.description, "%s" % event_type)

    def test_level_str_returns_level_description(self):
        events_and_levels = [
            (
                level,
                factory.make_event(type=factory.make_event_type(level=level))
            )
            for level in LOGGING_LEVELS
        ]

        self.assertEquals(
            [event.type.level_str for level, event in events_and_levels],
            [LOGGING_LEVELS[level] for level, event in events_and_levels],
        )
