# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing utilities for the region event-loop."""

from fixtures import Fixture
from twisted.application.service import Service
from twisted.internet import defer

from maasserver import eventloop
from maasserver.eventloop import loop
from maastesting.crochet import wait_for

wait_for_reactor = wait_for()


class RegionEventLoopFixture(Fixture):
    """Stubs-out services in the event-loop to avoid side-effects.

    Sometimes we need only a single service, or no services, running
    when starting the event-loop. This fixture, by default, will stub-
    out all services by switching their factory callable out. This means
    that the services will be created, started, and stopped, but they
    won't do anything.
    """

    def __init__(self, *services):
        super().__init__()
        self.services = services

    def checkEventLoopClean(self):
        # Don't proceed if the event-loop is running.
        if loop.services.running:
            raise RuntimeError(
                "The event-loop has been left running; this fixture cannot "
                "make a reasonable decision about what to do next."
            )
        # Don't proceed if any services are registered.
        services = list(loop.services)
        if services != []:
            raise RuntimeError(
                "One or more services are registered; this fixture cannot "
                "make a reasonable decision about what to do next.  "
                "The services are: %s."
                % ", ".join(service.name for service in services)
            )

    def resetStartUp(self):
        eventloop.loop.prepare = self.original_prepare
        eventloop.loop.services._set_globals = self.original_set_globals

    def setUp(self):
        super().setUp()
        # Patch start_up in the eventloop.
        self.original_prepare = eventloop.loop.prepare
        self.original_set_globals = eventloop.loop.services._set_globals
        eventloop.loop.prepare = lambda: defer.succeed(None)
        eventloop.loop.services._set_globals = lambda: defer.succeed(None)
        # Check that the event-loop is dormant and clean.
        self.checkEventLoopClean()
        # Ensure the event-loop will be left in a consistent state.
        self.addCleanup(self.checkEventLoopClean)
        # Restore the current `factories` tuple on exit.
        self.addCleanup(setattr, loop, "factories", loop.factories)
        # Stop the event-loop on exit.
        self.addCleanup(self.resetStartUp)
        # Set the new `factories` tuple, with all factories stubbed-out
        # except those in `self.services`.
        fakeFactoryInfo = {
            "factory": Service,
            "requires": [],
            "only_on_master": False,
        }
        loop.factories = {
            name: (factoryInfo if name in self.services else fakeFactoryInfo)
            for name, factoryInfo in loop.factories.items()
        }


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
                "make a reasonable decision about what to do next."
            )

    def resetStartUp(self):
        eventloop.loop.prepare = self.original_prepare
        eventloop.loop.services._set_globals = self.original_set_globals

    def setUp(self):
        super().setUp()
        # Patch start_up in the eventloop.
        self.original_prepare = eventloop.loop.prepare
        self.original_set_globals = eventloop.loop.services._set_globals
        eventloop.loop.prepare = lambda: defer.succeed(None)
        eventloop.loop.services._set_globals = lambda: defer.succeed(None)
        # Check that the event-loop is dormant and clean.
        self.checkEventLoopClean()
        # Check that the event-loop will be left dormant and clean.
        self.addCleanup(self.checkEventLoopClean)
        # Stop the event-loop on exit.
        self.addCleanup(self.stop)
        # Stop the event-loop on exit.
        self.addCleanup(self.resetStartUp)
        # Start the event-loop.
        self.start()
