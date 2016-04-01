# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for service monitoring in the regiond."""

__all__ = []

import random

from crochet import wait_for
from maasserver import service_monitor as service_monitor_module
from maasserver.enum import SERVICE_STATUS
from maasserver.models.config import Config
from maasserver.models.service import Service
from maasserver.service_monitor import (
    ProxyService,
    service_monitor,
    ServiceMonitorService,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from maastesting.twisted import TwistedLoggerFixture
from mock import (
    Mock,
    sentinel,
)
from provisioningserver.utils.service_monitor import (
    SERVICE_STATE,
    ServiceState,
)
from provisioningserver.utils.twisted import DeferredValue
from testtools.matchers import MatchesStructure
from twisted.internet.defer import (
    fail,
    inlineCallbacks,
    maybeDeferred,
    succeed,
)
from twisted.internet.task import Clock


wait_for_reactor = wait_for(30)  # 30 seconds.


class TestGlobalServiceMonitor(MAASTestCase):

    def test__includes_all_services(self):
        self.assertItemsEqual(
            ["bind9", "proxy"], service_monitor._services.keys())


class TestServiceMonitorService(MAASTransactionServerTestCase):

    def pick_service(self):
        return random.choice(list(service_monitor._services.values()))

    def test_init_sets_up_timer_correctly(self):
        monitor_service = ServiceMonitorService(
            sentinel.advertisingService, sentinel.clock)
        self.assertThat(monitor_service, MatchesStructure.byEquality(
            call=(monitor_service.monitorServices, (), {}),
            step=(60), advertisingService=sentinel.advertisingService,
            clock=sentinel.clock))

    def test_monitorServices_does_not_do_anything_in_dev_environment(self):
        # Belt-n-braces make sure we're in a development environment.
        self.assertTrue(service_monitor_module.is_dev_environment())

        monitor_service = ServiceMonitorService(
            sentinel.advertisingService, Clock())
        mock_ensureServices = self.patch(service_monitor, "ensureServices")
        with TwistedLoggerFixture() as logger:
            monitor_service.monitorServices()
        self.assertThat(mock_ensureServices, MockNotCalled())
        self.assertDocTestMatches(
            "Skipping check of services; they're not running under the "
            "supervision of systemd.", logger.output)

    def test_monitorServices_calls_ensureServices(self):
        # Pretend we're in a production environment.
        self.patch(
            service_monitor_module, "is_dev_environment").return_value = False

        monitor_service = ServiceMonitorService(
            sentinel.advertisingService, Clock())
        mock_ensureServices = self.patch(service_monitor, "ensureServices")
        monitor_service.monitorServices()
        self.assertThat(
            mock_ensureServices,
            MockCalledOnceWith())

    def test_monitorServices_handles_failure(self):
        # Pretend we're in a production environment.
        self.patch(
            service_monitor_module, "is_dev_environment").return_value = False

        monitor_service = ServiceMonitorService(
            sentinel.advertisingService, Clock())
        mock_ensureServices = self.patch(service_monitor, "ensureServices")
        mock_ensureServices.return_value = fail(factory.make_exception())
        with TwistedLoggerFixture() as logger:
            monitor_service.monitorServices()
        self.assertDocTestMatches("""\
            Failed to monitor services and update database.
            Traceback (most recent call last):
            ...""", logger.output)

    @wait_for_reactor
    @inlineCallbacks
    def test_updates_services_in_database(self):
        # Pretend we're in a production environment.
        self.patch(
            service_monitor_module, "is_dev_environment").return_value = False

        service = self.pick_service()
        state = ServiceState(SERVICE_STATE.ON, "running")
        mock_ensureServices = self.patch(service_monitor, "ensureServices")
        mock_ensureServices.return_value = succeed({
            service.name: state
        })

        advertisingService = Mock()
        advertisingService.processId = DeferredValue()
        monitor_service = ServiceMonitorService(
            advertisingService, Clock())
        yield monitor_service.startService()

        region = yield deferToDatabase(
            transactional(factory.make_RegionController))
        region_process = yield deferToDatabase(
            transactional(factory.make_RegionControllerProcess), region)
        advertisingService.processId.set(region_process.id)
        yield monitor_service.stopService()

        service = yield deferToDatabase(
            transactional(Service.objects.get), node=region, name=service.name)
        self.assertThat(
            service,
            MatchesStructure.byEquality(
                name=service.name, status=SERVICE_STATUS.RUNNING,
                status_info=""))

    @wait_for_reactor
    @inlineCallbacks
    def test__buildServices_builds_services_list(self):
        monitor_service = ServiceMonitorService(
            sentinel.advertisingService, Clock())
        service = self.pick_service()
        state = ServiceState(SERVICE_STATE.ON, "running")
        observed_services = yield monitor_service._buildServices({
            service.name: state
        })
        expected_services = [{
            "name": service.name,
            "status": "running",
            "status_info": "",
        }]
        self.assertEqual(expected_services, observed_services)


class TestProxyService(MAASTransactionServerTestCase):

    def make_proxy_service(self):
        class FakeProxyService(ProxyService):
            name = factory.make_name("name")
            service_name = factory.make_name("service")
        return FakeProxyService()

    @wait_for_reactor
    @inlineCallbacks
    def test_get_expected_state_returns_on_for_proxy_off_and_unset(self):
        service = self.make_proxy_service()
        yield deferToDatabase(
            transactional(Config.objects.set_config),
            "enable_http_proxy", False)
        yield deferToDatabase(
            transactional(Config.objects.set_config),
            "http_proxy", "")
        expected_state = yield maybeDeferred(service.get_expected_state)
        self.assertEqual((SERVICE_STATUS.ON, None), expected_state)

    @wait_for_reactor
    @inlineCallbacks
    def test_get_expected_state_returns_on_for_proxy_off_and_set(self):
        service = self.make_proxy_service()
        yield deferToDatabase(
            transactional(Config.objects.set_config),
            "enable_http_proxy", False)
        yield deferToDatabase(
            transactional(Config.objects.set_config),
            "http_proxy", factory.make_url())
        expected_state = yield maybeDeferred(service.get_expected_state)
        self.assertEqual((SERVICE_STATUS.ON, None), expected_state)

    @wait_for_reactor
    @inlineCallbacks
    def test_get_expected_state_returns_on_for_proxy_on_but_unset(self):
        service = self.make_proxy_service()
        yield deferToDatabase(
            transactional(Config.objects.set_config),
            "enable_http_proxy", True)
        yield deferToDatabase(
            transactional(Config.objects.set_config),
            "http_proxy", "")
        expected_state = yield maybeDeferred(service.get_expected_state)
        self.assertEqual((SERVICE_STATUS.ON, None), expected_state)

    @wait_for_reactor
    @inlineCallbacks
    def test_get_expected_state_returns_off_for_proxy_on_and_set(self):
        service = self.make_proxy_service()
        yield deferToDatabase(
            transactional(Config.objects.set_config),
            "enable_http_proxy", True)
        yield deferToDatabase(
            transactional(Config.objects.set_config),
            "http_proxy", factory.make_url())
        expected_state = yield maybeDeferred(service.get_expected_state)
        self.assertEqual(
            (SERVICE_STATUS.OFF,
             'disabled, alternate proxy is configured in settings.'),
            expected_state)
