# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for
:py:module:`~provisioningserver.pserv_services.service_monitor_service`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.pserv_services import service_monitor_service as sms
from provisioningserver.service_monitor import service_monitor
from testtools.matchers import MatchesStructure
from twisted.internet.task import Clock


class TestServiceMonitorService(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_init_sets_up_timer_correctly(self):
        service = sms.ServiceMonitorService()
        self.assertThat(service, MatchesStructure.byEquality(
            call=(service.monitor_services, (), {}),
            step=(2 * 60), clock=None))

    def make_monitor_service(self):
        service = sms.ServiceMonitorService(Clock())
        return service

    def test_monitor_services_does_not_do_anything_in_dev_environment(self):
        # Belt-n-braces make sure we're in a development environment.
        self.assertTrue(sms.is_dev_environment())

        service = self.make_monitor_service()
        mock_deferToThread = self.patch(sms, "deferToThread")
        with TwistedLoggerFixture() as logger:
            service.monitor_services()
        self.assertThat(mock_deferToThread, MockNotCalled())
        self.assertDocTestMatches(
            "Skipping check of services; they're not running under the "
            "supervision of Upstart or systemd.", logger.output)

    def test_monitor_services_defers_ensure_all_services_to_thread(self):
        # Pretend we're in a production environment.
        self.patch(sms, "is_dev_environment").return_value = False

        service = self.make_monitor_service()
        mock_deferToThread = self.patch(sms, "deferToThread")
        service.monitor_services()
        self.assertThat(
            mock_deferToThread,
            MockCalledOnceWith(service_monitor.ensure_all_services))
