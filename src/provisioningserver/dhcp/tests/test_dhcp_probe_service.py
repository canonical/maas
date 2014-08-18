# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for periodic DHCP prober."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.matchers import get_mock_calls
from maastesting.testcase import MAASTestCase
from provisioningserver.dhcp import detect
from provisioningserver.dhcp.dhcp_probe_service import (
    PeriodicDHCPProbeService,
    )
from testtools.deferredruntest import AsynchronousDeferredRunTest
from twisted.internet.task import Clock


class TestDHCPProbeService(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def setUp(self):
        super(TestDHCPProbeService, self).setUp()

    def test_is_called_every_interval(self):
        clock = Clock()
        # Avoid actually probing
        probe_task = self.patch(detect, "periodic_probe_task")
        service = PeriodicDHCPProbeService(clock)

        # Until the service has started, periodic_probe_task() won't
        # be called.
        self.assertEqual(0, len(get_mock_calls(probe_task)))

        # Avoid actual downloads:
        service.startService()

        # The first call is issued at startup.
        self.assertEqual(1, len(get_mock_calls(probe_task)))

        # Wind clock forward one second less than the desired interval.
        clock.advance(service.check_interval - 1)
        # No more periodic calls made.
        self.assertEqual(1, len(get_mock_calls(probe_task)))

        # Wind clock forward one second, past the interval.
        clock.advance(1)

        # Now there were two calls.
        self.assertEqual(2, len(get_mock_calls(probe_task)))
