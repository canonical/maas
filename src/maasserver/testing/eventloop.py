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
]

from fixtures import Fixture
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

    def setUp(self):
        super(RegionEventLoopFixture, self).setUp()
        # Restore the current `factories` tuple on exit.
        self.addCleanup(setattr, loop, "factories", loop.factories)
        # Set the new `factories` tuple, with all factories stubbed-out
        # except those in `self.services`.
        loop.factories = tuple(
            (name, (factory if name in self.services else Service))
            for name, factory in loop.factories)
