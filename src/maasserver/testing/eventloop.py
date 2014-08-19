# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing utilities for the region event-loop."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "RegionEventLoopFixture",
    "RunningEventLoopFixture",
]

from crochet import wait_for_reactor
from fixtures import Fixture
from maasserver import eventloop
from maasserver.eventloop import loop
from twisted.application.service import Service


class RegionEventLoopFixture(Fixture):
    """Stubs-out services in the event-loop to avoid side-effects.

    Sometimes we need only a single service, or no services, running
    when starting the event-loop. This fixture, by default, will stub-
    out all services by switching their factory callable out. This means
    that the services will be created, started, and stopped, but they
    won't do anything.
    """

    def __init__(self, *services):
        super(RegionEventLoopFixture, self).__init__()
        self.services = services

    def checkEventLoopClean(self):
        # Don't proceed if the event-loop is running.
        if loop.services.running:
            raise RuntimeError(
                "The event-loop has been left running; this fixture cannot "
                "make a reasonable decision about what to do next.")
        # Don't proceed if any services are registered.
        services = list(loop.services)
        if services != []:
            raise RuntimeError(
                "One or more services are registered; this fixture cannot "
                "make a reasonable decision about what to do next.  "
                "The services are: %s."
                % ', '.join(service.name for service in services))

    def setUp(self):
        super(RegionEventLoopFixture, self).setUp()
        # Check that the event-loop is dormant and clean.
        self.checkEventLoopClean()
        # Ensure the event-loop will be left in a consistent state.
        self.addCleanup(self.checkEventLoopClean)
        # Restore the current `factories` tuple on exit.
        self.addCleanup(setattr, loop, "factories", loop.factories)
        # Set the new `factories` tuple, with all factories stubbed-out
        # except those in `self.services`.
        loop.factories = tuple(
            (name, (factory if name in self.services else Service))
            for name, factory in loop.factories)


class RunningEventLoopFixture(Fixture):
    """Starts and stops the region's event-loop.

    Note that this does *not* start and stop the Twisted reactor. Typically in
    region tests you'll find that the reactor is always running as a
    side-effect of importing :py:mod:`maasserver.eventloop`.
    """

    @wait_for_reactor
    def start(self):
        return eventloop.start()

    @wait_for_reactor
    def stop(self):
        return eventloop.reset()

    def checkEventLoopClean(self):
        # Don't proceed if the event-loop is running.
        if loop.services.running:
            raise RuntimeError(
                "The event-loop has been left running; this fixture cannot "
                "make a reasonable decision about what to do next.")

    def setUp(self):
        super(RunningEventLoopFixture, self).setUp()
        # Check that the event-loop is dormant and clean.
        self.checkEventLoopClean()
        # Check that the event-loop will be left dormant and clean.
        self.addCleanup(self.checkEventLoopClean)
        # Stop the event-loop on exit.
        self.addCleanup(self.stop)
        # Start the event-loop.
        self.start()
