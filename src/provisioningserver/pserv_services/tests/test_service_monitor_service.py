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

from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
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

    def test_monitor_services_defers_ensure_all_services_to_thread(self):
        service = self.make_monitor_service()
        mock_deferToThread = self.patch(sms, "deferToThread")
        service.monitor_services()
        self.assertThat(
            mock_deferToThread,
            MockCalledOnceWith(service_monitor.ensure_all_services))
