# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for service monitoring in the regiond."""

import random
from unittest.mock import sentinel

from twisted.internet.defer import fail, inlineCallbacks, succeed
from twisted.internet.task import Clock

from maasserver import proxyconfig
from maasserver.enum import SERVICE_STATUS
from maasserver.models.node import RegionController
from maasserver.models.service import Service
from maasserver.regiondservices import service_monitor_service
from maasserver.regiondservices.service_monitor_service import (
    ServiceMonitorService,
)
from maasserver.service_monitor import service_monitor
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.utils.service_monitor import (
    SERVICE_STATE,
    ServiceState,
)

wait_for_reactor = wait_for()


class TestServiceMonitorService(MAASTransactionServerTestCase):
    def pick_service(self):
        # Skip the proxy service because of the expected state is conditional.
        return random.choice(
            [
                service
                for service in service_monitor._services.values()
                if service.name != "proxy"
            ]
        )

    def test_init_sets_up_timer_correctly(self):
        monitor_service = ServiceMonitorService(sentinel.clock)
        self.assertIs(monitor_service.clock, sentinel.clock)
        self.assertEqual(
            monitor_service.call, (monitor_service.monitorServices, (), {})
        )
        self.assertEqual(monitor_service.step, 30)

    def test_monitorServices_does_not_do_anything_in_dev_environment(self):
        # Belt-n-braces make sure we're in a development environment.
        self.assertTrue(service_monitor_service.is_dev_environment())

        monitor_service = ServiceMonitorService(Clock())
        mock_ensureServices = self.patch(service_monitor, "ensureServices")
        with TwistedLoggerFixture() as logger:
            monitor_service.monitorServices()
        mock_ensureServices.assert_not_called()
        self.assertIn(
            "Skipping check of services; they're not running under the "
            "supervision of systemd.",
            logger.output,
        )

    def test_monitorServices_calls_ensureServices(self):
        # Pretend we're in a production environment.
        self.patch(
            service_monitor_service, "is_dev_environment"
        ).return_value = False

        monitor_service = ServiceMonitorService(Clock())
        mock_ensureServices = self.patch(service_monitor, "ensureServices")
        monitor_service.monitorServices()
        mock_ensureServices.assert_called_once_with()

    def test_monitorServices_handles_failure(self):
        # Pretend we're in a production environment.
        self.patch(
            service_monitor_service, "is_dev_environment"
        ).return_value = False

        monitor_service = ServiceMonitorService(Clock())
        mock_ensureServices = self.patch(service_monitor, "ensureServices")
        mock_ensureServices.return_value = fail(factory.make_exception())
        with TwistedLoggerFixture() as logger:
            monitor_service.monitorServices()
        self.assertIn(
            "Failed to monitor services and update database.\nTraceback (most recent call last):",
            logger.output,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_updates_services_in_database(self):
        # Pretend we're in a production environment.
        self.patch(
            service_monitor_service, "is_dev_environment"
        ).return_value = False
        self.patch(proxyconfig, "is_config_present").return_value = True

        service = self.pick_service()
        state = ServiceState(SERVICE_STATE.ON, "running")
        mock_ensureServices = self.patch(service_monitor, "ensureServices")
        mock_ensureServices.return_value = succeed({service.name: state})

        region = yield deferToDatabase(
            transactional(factory.make_RegionController)
        )
        self.patch(
            RegionController.objects, "get_running_controller"
        ).return_value = region
        monitor_service = ServiceMonitorService(Clock())
        yield monitor_service.startService()
        yield monitor_service.stopService()

        a_service = yield deferToDatabase(
            transactional(Service.objects.get), node=region, name=service.name
        )
        self.assertEqual(a_service.name, service.name)
        self.assertEqual(a_service.status, SERVICE_STATUS.RUNNING)
        self.assertEqual(a_service.status_info, "")

    @wait_for_reactor
    @inlineCallbacks
    def test_buildServices_builds_services_list(self):
        self.patch(proxyconfig, "is_config_present").return_value = True
        monitor_service = ServiceMonitorService(Clock())
        service = self.pick_service()
        state = ServiceState(SERVICE_STATE.ON, "running")
        observed_services = yield monitor_service._buildServices(
            {service.name: state}
        )
        expected_services = [
            {"name": service.name, "status": "running", "status_info": ""}
        ]
        self.assertEqual(expected_services, observed_services)
