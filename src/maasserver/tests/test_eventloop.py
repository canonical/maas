# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.eventloop`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver import eventloop
from maastesting.testcase import MAASTestCase
from twisted.application.service import (
    MultiService,
    Service,
    )


class TestRegionEventLoop(MAASTestCase):

    def test_name(self):
        self.patch(eventloop, "gethostname").return_value = "foo"
        self.patch(eventloop, "getpid").return_value = 12345
        self.assertEqual("foo:pid=12345", eventloop.loop.name)

    def test_start_and_stop(self):
        # Replace RegionService with a non-functional dummy to avoid
        # bringing up real services here, and reset the service list.
        self.patch(eventloop, "RegionService").return_value = Service()
        self.patch(eventloop.loop, "services", MultiService())
        # At the outset, the eventloop's services are dorment.
        self.assertFalse(eventloop.loop.services.running)
        self.assertEqual(
            set(eventloop.loop.services),
            set())
        # After starting the loop, the services list is populated, and
        # the services are started too.
        eventloop.loop.start().wait(5)
        self.assertTrue(eventloop.loop.services.running)
        self.assertEqual(
            set(eventloop.loop.services),
            {eventloop.RegionService.return_value})
        # A shutdown hook is registered with the reactor.
        stopService = eventloop.loop.services.stopService
        self.assertEqual(
            ("shutdown", ("before", stopService, (), {})),
            eventloop.loop.handle)
        # After stopping the loop, the services list remains populated,
        # but the services are all stopped.
        eventloop.loop.stop().wait(5)
        self.assertFalse(eventloop.loop.services.running)
        self.assertEqual(
            set(eventloop.loop.services),
            {eventloop.RegionService.return_value})
        # The hook has been cleared.
        self.assertIsNone(eventloop.loop.handle)

    def test_module_globals(self):
        # Several module globals are references to a shared RegionEventLoop.
        self.assertIs(eventloop.services, eventloop.loop.services)
        # Must compare by equality here; these methods are decorated.
        self.assertEqual(eventloop.start, eventloop.loop.start)
        self.assertEqual(eventloop.stop, eventloop.loop.stop)
