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

import random
import threading

from django.db import IntegrityError
from maasserver.models.eventtype import (
    EventType,
    LOGGING_LEVELS,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import transactional
from maastesting.djangotestcase import DjangoTransactionTestCase
from testtools.matchers import (
    AfterPreprocessing,
    AllMatch,
    Equals,
    GreaterThan,
    MatchesAny,
    MatchesStructure,
    )


class EventTypeTest(MAASServerTestCase):

    def test_displays_event_type_description(self):
        event_type = factory.make_EventType()
        self.assertIn(event_type.description, "%s" % event_type)

    def test_level_str_returns_level_description(self):
        events_and_levels = [
            (
                level,
                factory.make_Event(type=factory.make_EventType(level=level))
            )
            for level in LOGGING_LEVELS
        ]

        self.assertEquals(
            [event.type.level_str for level, event in events_and_levels],
            [LOGGING_LEVELS[level] for level, event in events_and_levels],
        )

    def test_register(self):
        name = factory.make_name("name")
        desc = factory.make_name("desc")
        level = random.choice(list(LOGGING_LEVELS))
        event_type = EventType.objects.register(name, desc, level)
        self.assertThat(event_type, MatchesStructure.byEquality(
            name=name, description=desc, level=level))


class EventTypeConcurrencyTest(DjangoTransactionTestCase):

    def test_register_is_safe_with_concurrency(self):
        name = factory.make_name("name")
        desc = factory.make_name("desc")
        level = random.choice(list(LOGGING_LEVELS))

        # Intercept calls to EventType.objects.create() so that we can capture
        # IntegrityErrors. Later on, all but one thread should experience an
        # IntegrityError, indicating that the event type has already been
        # registered.
        create_original = EventType.objects.create
        create_errors_lock = threading.Lock()
        create_errors = []

        def create_and_capture(**kwargs):
            # Capture IntegrityError but don't change the behaviour of
            # EventType.objects.create().
            try:
                return create_original(**kwargs)
            except IntegrityError as e:
                with create_errors_lock:
                    create_errors.append(e)
                raise

        self.patch(EventType.objects, "create", create_and_capture)

        # A list to store the event types that are being registered, and a
        # lock to synchronise write access to it.
        event_types_lock = threading.Lock()
        event_types = []

        # Use the transactional decorator to ensure that old connections are
        # closed in the threads we're spawning. If we don't do that Django
        # sometimes gets angry.
        @transactional
        def make_event_type():
            # Create the event type then wait a short time to increase the
            # chances that transactions between threads overlap.
            return EventType.objects.register(name, desc, level)

        # Only save the event type when the txn that make_event_type() runs is
        # has been committed. This is when we're likely to see errors.
        def make_event_type_in_thread():
            event_type = make_event_type()
            with event_types_lock:
                event_types.append(event_type)

        # Create a number of threads to simulate a race.
        threads = [
            threading.Thread(target=make_event_type_in_thread)
            for _ in xrange(5)
        ]

        # Start all the threads at the same time.
        for thread in threads:
            thread.start()
        # Now wait for them all to finish.
        for thread in threads:
            thread.join()

        # All but one thread fails to create the event type at least once.
        # Each /may/ fail more than once, if the event-type is not yet visible
        # in that thread's transaction; see the comments in register().
        expected_create_errors_min = len(threads) - 1
        expected_create_errors_count = MatchesAny(
            Equals(expected_create_errors_min),
            GreaterThan(expected_create_errors_min),
        )
        self.expectThat(
            create_errors, AfterPreprocessing(
                len, expected_create_errors_count))
        # All threads return the same event type.
        self.expectThat(len(threads), Equals(len(event_types)))
        self.expectThat(
            event_types, AllMatch(MatchesStructure.byEquality(
                name=name, description=desc, level=level)))
