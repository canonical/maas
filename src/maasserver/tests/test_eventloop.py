# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.eventloop`."""


from unittest.mock import ANY, call, Mock, sentinel

from django.db import connections
from twisted.application.internet import StreamServerEndpointService
from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks
from twisted.python.threadable import isInIOThread

from maasserver import (
    bootresources,
    eventloop,
    ipc,
    nonces_cleanup,
    rack_controller,
    region_controller,
    stats,
    status_monitor,
    webapp,
    workers,
)
from maasserver.eventloop import MAASServices
from maasserver.prometheus.service import REGION_PROMETHEUS_PORT
from maasserver.prometheus.stats import PrometheusService
from maasserver.regiondservices import ntp, service_monitor_service, syslog
from maasserver.regiondservices.certificate_expiration_check import (
    CertificateExpirationCheckService,
)
from maasserver.regiondservices.vault_secrets_cleanup import (
    VaultSecretsCleanupService,
)
from maasserver.regiondservices.version_update_check import (
    RegionVersionUpdateCheckService,
)
from maasserver.rpc import regionservice
from maasserver.testing.eventloop import RegionEventLoopFixture
from maasserver.testing.listener import FakePostgresListenerService
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import dbtasks
from maasserver.utils.orm import DisabledDatabaseConnection, transactional
from maastesting import get_testing_timeout
from maastesting.crochet import wait_for
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from metadataserver import api_twisted
from provisioningserver.utils.twisted import asynchronous

TIMEOUT = get_testing_timeout()
wait_for_reactor = wait_for()


class TestMAASServices(MAASServerTestCase):
    @wait_for_reactor
    @inlineCallbacks
    def test_calls_prepare(self):
        fake_eventloop = Mock()
        calls = Mock()
        fake_eventloop.prepare = calls
        fake_services = [Mock(), Mock()]
        services = MAASServices(fake_eventloop)
        for service in fake_services:
            service.startService = Mock()
            services.addService(service)
        yield services.startService()
        calls.assert_called_once_with()
        self.assertEqual(1, services.running)

    @wait_for_reactor
    @inlineCallbacks
    def test_starts_each_service(self):
        fake_eventloop = Mock()
        fake_eventloop.prepare = Mock()
        calls = Mock()
        fake_services = [Mock(), Mock()]
        services = MAASServices(fake_eventloop)
        for service in fake_services:
            service.startService = calls
            services.addService(service)
        yield services.startService()
        calls.assert_has_calls((call(), call()))
        self.assertEqual(1, services.running)

    @wait_for_reactor
    @inlineCallbacks
    def test_sets_global_labels(self):
        mock_set_global_labels = self.patch(eventloop, "set_global_labels")
        fake_eventloop = Mock()
        services = MAASServices(fake_eventloop)
        yield services.startService()
        mock_set_global_labels.assert_called_once_with(
            maas_uuid=ANY, service_type="region"
        )


class TestRegionEventLoop(MAASTestCase):
    def test_name(self):
        self.patch(eventloop, "gethostname").return_value = "foo"
        self.patch(eventloop.os, "getpid").return_value = 12345
        self.assertEqual("foo:pid=12345", eventloop.loop.name)

    def test_populateService_prevent_worker_service_on_master(self):
        self.patch(eventloop.services, "getServiceNamed")
        an_eventloop = eventloop.RegionEventLoop()

        @asynchronous
        def tryPopulate(*args, **kwargs):
            self.assertRaises(
                ValueError, an_eventloop.populateService, *args, **kwargs
            )

        tryPopulate("web", master=True).wait(TIMEOUT)

    def test_populateService_prevent_master_service_on_worker(self):
        self.patch(eventloop.services, "getServiceNamed")
        an_eventloop = eventloop.RegionEventLoop()

        @asynchronous
        def tryPopulate(*args, **kwargs):
            self.assertRaises(
                ValueError, an_eventloop.populateService, *args, **kwargs
            )

        tryPopulate("workers", master=False).wait(TIMEOUT)

    def test_populateService_prevent_service_on_all_in_one(self):
        self.patch(eventloop.services, "getServiceNamed")
        an_eventloop = eventloop.RegionEventLoop()

        @asynchronous
        def tryPopulate(*args, **kwargs):
            self.assertRaises(
                ValueError, an_eventloop.populateService, *args, **kwargs
            )

        tryPopulate("workers", master=True, all_in_one=True).wait(TIMEOUT)

    def test_populate_on_worker_without_import_services(self):
        self.patch(eventloop.services, "getServiceNamed")
        an_eventloop = eventloop.RegionEventLoop()
        # At first there are no services.
        self.assertEqual(
            set(), {service.name for service in an_eventloop.services}
        )
        # populate() creates a service with each factory.
        an_eventloop.populate(master=False).wait(TIMEOUT)
        self.assertEqual(
            {
                name
                for name, item in an_eventloop.factories.items()
                if item["only_on_master"] is False
                and (item.get("import_service", False) is False)
            },
            {svc.name for svc in an_eventloop.services},
        )
        # The services are not started.
        self.assertEqual(
            {
                name: False
                for name, item in an_eventloop.factories.items()
                if item["only_on_master"] is False
                and (item.get("import_service", False) is False)
            },
            {svc.name: svc.running for svc in an_eventloop.services},
        )

    def test_populate_on_worker_with_import_services(self):
        self.patch(eventloop.services, "getServiceNamed")
        an_eventloop = eventloop.RegionEventLoop()
        # At first there are no services.
        self.assertEqual(
            set(), {service.name for service in an_eventloop.services}
        )
        # populate() creates a service with each factory.
        an_eventloop.populate(master=False, import_services=True).wait(TIMEOUT)
        self.assertEqual(
            {
                name
                for name, item in an_eventloop.factories.items()
                if item["only_on_master"] is False
            },
            {svc.name for svc in an_eventloop.services},
        )
        # The services are not started.
        self.assertEqual(
            {
                name: False
                for name, item in an_eventloop.factories.items()
                if item["only_on_master"] is False
            },
            {svc.name: svc.running for svc in an_eventloop.services},
        )

    def test_populate_on_master(self):
        self.patch(eventloop.services, "getServiceNamed")
        an_eventloop = eventloop.RegionEventLoop()
        # At first there are no services.
        self.assertEqual(
            set(), {service.name for service in an_eventloop.services}
        )
        # populate() creates a service with each factory.
        an_eventloop.populate(master=True).wait(TIMEOUT)
        self.assertEqual(
            {
                name
                for name, item in an_eventloop.factories.items()
                if item["only_on_master"] is True
            },
            {svc.name for svc in an_eventloop.services},
        )
        # The services are not started.
        self.assertEqual(
            {
                name: False
                for name, item in an_eventloop.factories.items()
                if item["only_on_master"] is True
            },
            {svc.name: svc.running for svc in an_eventloop.services},
        )

    def test_populate_on_all_in_one(self):
        self.patch(eventloop.services, "getServiceNamed")
        an_eventloop = eventloop.RegionEventLoop()
        # At first there are no services.
        self.assertEqual(
            set(), {service.name for service in an_eventloop.services}
        )
        # populate() creates a service with each factory.
        an_eventloop.populate(
            master=True, all_in_one=True, import_services=True
        ).wait(TIMEOUT)
        self.assertEqual(
            {
                name
                for name, item in an_eventloop.factories.items()
                if item.get("not_all_in_one", False) is False
            },
            {svc.name for svc in an_eventloop.services},
        )
        # The services are not started.
        self.assertEqual(
            {
                name: False
                for name, item in an_eventloop.factories.items()
                if item.get("not_all_in_one", False) is False
            },
            {svc.name: svc.running for svc in an_eventloop.services},
        )

    def test_start_and_stop(self):
        # Replace the factories in RegionEventLoop with non-functional
        # dummies to avoid bringing up real services here, and ensure
        # that the services list is empty.
        self.useFixture(RegionEventLoopFixture())
        # At the outset, the eventloop's services are dorment.
        self.assertFalse(eventloop.loop.services.running)
        # RegionEventLoop.running is an alias for .services.running.
        self.assertFalse(eventloop.loop.running)
        self.assertEqual(set(eventloop.loop.services), set())
        # Patch prepare so it's not actually run.
        self.patch(eventloop.loop, "prepare").return_value = defer.succeed(
            None
        )
        # After starting the loop, the services list is populated, and
        # the services are started too.
        eventloop.loop.start().wait(TIMEOUT)
        self.addCleanup(lambda: eventloop.loop.reset().wait(TIMEOUT))
        self.assertTrue(eventloop.loop.services.running)
        self.assertTrue(eventloop.loop.running)
        self.assertEqual(
            {service.name for service in eventloop.loop.services},
            {name for name in eventloop.loop.factories.keys()},
        )
        # A shutdown hook is registered with the reactor.
        stopService = eventloop.loop.services.stopService
        self.assertEqual(
            ("shutdown", ("before", stopService, (), {})),
            eventloop.loop.handle,
        )
        # After stopping the loop, the services list remains populated,
        # but the services are all stopped.
        eventloop.loop.stop().wait(TIMEOUT)
        self.assertFalse(eventloop.loop.services.running)
        self.assertFalse(eventloop.loop.running)
        self.assertEqual(
            {service.name for service in eventloop.loop.services},
            {name for name in eventloop.loop.factories.keys()},
        )
        # The hook has been cleared.
        self.assertIsNone(eventloop.loop.handle)

    def test_reset(self):
        # Replace the factories in RegionEventLoop with non-functional
        # dummies to avoid bringing up real services here, and ensure
        # that the services list is empty.
        self.useFixture(RegionEventLoopFixture())
        # Patch prepare so it's not actually run.
        self.patch(eventloop.loop, "prepare").return_value = defer.succeed(
            None
        )
        eventloop.loop.start().wait(TIMEOUT)
        eventloop.loop.reset().wait(TIMEOUT)
        # After stopping the loop, the services list is also emptied.
        self.assertFalse(eventloop.loop.services.running)
        self.assertFalse(eventloop.loop.running)
        self.assertEqual(set(eventloop.loop.services), set())
        # The hook has also been cleared.
        self.assertIsNone(eventloop.loop.handle)

    def test_reset_clears_factories(self):
        eventloop.loop.factories = ((factory.make_name("service"), None),)
        eventloop.loop.reset().wait(TIMEOUT)
        # The loop's factories are also reset.
        self.assertEqual(
            eventloop.loop.__class__.factories, eventloop.loop.factories
        )

    def test_restart(self):
        # Replace the factories in RegionEventLoop with non-functional
        # dummies to avoid bringing up real services here, and ensure
        # that the services list is empty.
        self.useFixture(RegionEventLoopFixture())
        # Stop and reset eventloop afterwards
        self.addCleanup(lambda: eventloop.loop.reset().wait(TIMEOUT))
        # Patch prepare so it's not actually run.
        self.patch(eventloop.loop, "prepare").return_value = defer.succeed(
            None
        )
        reset_mock = self.patch(eventloop.loop, "reset")
        reset_mock.return_value = defer.succeed(None)

        eventloop.loop.start().wait(TIMEOUT)
        start_mock = self.patch(eventloop.loop, "start")
        start_mock.return_value = defer.succeed(None)
        eventloop.loop.restart().wait(TIMEOUT)

        reset_mock.assert_called_once()
        start_mock.assert_called_once_with(
            master=eventloop.loop.master, all_in_one=eventloop.loop.all_in_one
        )
        eventloop.loop.stop().wait(TIMEOUT)

    def test_module_globals(self):
        # Several module globals are references to a shared RegionEventLoop.
        self.assertIs(eventloop.services, eventloop.loop.services)
        # Must compare by equality here; these methods are decorated.
        self.assertEqual(eventloop.reset, eventloop.loop.reset)
        self.assertEqual(eventloop.start, eventloop.loop.start)
        self.assertEqual(eventloop.stop, eventloop.loop.stop)
        self.assertEqual(eventloop.restart, eventloop.loop.restart)


class TestFactories(MAASServerTestCase):
    def test_make_DatabaseTaskService(self):
        service = eventloop.make_DatabaseTaskService()
        self.assertIsInstance(service, dbtasks.DatabaseTasksService)
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_DatabaseTaskService,
            eventloop.loop.factories["database-tasks"]["factory"],
        )
        self.assertFalse(
            eventloop.loop.factories["database-tasks"]["only_on_master"]
        )

    def test_make_MasterDatabaseTaskService(self):
        service = eventloop.make_DatabaseTaskService()
        self.assertIsInstance(service, dbtasks.DatabaseTasksService)
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_DatabaseTaskService,
            eventloop.loop.factories["database-tasks-master"]["factory"],
        )
        self.assertTrue(
            eventloop.loop.factories["database-tasks-master"]["only_on_master"]
        )

    def test_make_RegionControllerService(self):
        service = eventloop.make_RegionControllerService(
            sentinel.postgresListener, sentinel.dbtasks
        )
        self.assertIsInstance(
            service, region_controller.RegionControllerService
        )
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_RegionControllerService,
            eventloop.loop.factories["region-controller"]["factory"],
        )
        self.assertTrue(
            eventloop.loop.factories["region-controller"]["only_on_master"]
        )

    def test_make_RegionService(self):
        service = eventloop.make_RegionService(sentinel.ipcWorker)
        self.assertIsInstance(service, regionservice.RegionService)
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_RegionService,
            eventloop.loop.factories["rpc"]["factory"],
        )
        self.assertFalse(eventloop.loop.factories["rpc"]["only_on_master"])
        self.assertEqual(
            ["ipc-worker"], eventloop.loop.factories["rpc"]["requires"]
        )

    def test_make_NonceCleanupService(self):
        service = eventloop.make_NonceCleanupService()
        self.assertIsInstance(service, nonces_cleanup.NonceCleanupService)
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_NonceCleanupService,
            eventloop.loop.factories["nonce-cleanup"]["factory"],
        )
        self.assertTrue(
            eventloop.loop.factories["nonce-cleanup"]["only_on_master"]
        )

    def test_make_StatusMonitorService(self):
        service = eventloop.make_StatusMonitorService()
        self.assertIsInstance(service, status_monitor.StatusMonitorService)
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_StatusMonitorService,
            eventloop.loop.factories["status-monitor"]["factory"],
        )
        self.assertTrue(
            eventloop.loop.factories["status-monitor"]["only_on_master"]
        )

    def test_make_StatsService(self):
        service = eventloop.make_StatsService()
        self.assertIsInstance(service, stats.StatsService)
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_StatsService,
            eventloop.loop.factories["stats"]["factory"],
        )
        self.assertTrue(eventloop.loop.factories["stats"]["only_on_master"])

    def test_make_PrometheusService(self):
        service = eventloop.make_PrometheusService()
        self.assertIsInstance(service, PrometheusService)
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_PrometheusService,
            eventloop.loop.factories["prometheus"]["factory"],
        )
        self.assertTrue(
            eventloop.loop.factories["prometheus"]["only_on_master"]
        )

    def test_make_ImportResourcesService(self):
        service = eventloop.make_ImportResourcesService()
        self.assertIsInstance(service, bootresources.ImportResourcesService)
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_ImportResourcesService,
            eventloop.loop.factories["import-resources"]["factory"],
        )
        self.assertFalse(
            eventloop.loop.factories["import-resources"]["only_on_master"]
        )
        self.assertTrue(
            eventloop.loop.factories["import-resources"]["import_service"]
        )

    def test_make_ImportResourcesProgressService(self):
        service = eventloop.make_ImportResourcesProgressService()
        self.assertIsInstance(
            service, bootresources.ImportResourcesProgressService
        )
        # It is registered as a factory in RegionEventLoop.
        factories = eventloop.loop.factories
        self.assertIs(
            eventloop.make_ImportResourcesProgressService,
            factories["import-resources-progress"]["factory"],
        )
        self.assertFalse(
            factories["import-resources-progress"]["only_on_master"]
        )
        self.assertTrue(
            factories["import-resources-progress"]["import_service"]
        )

    def test_make_WebApplicationService(self):
        service = eventloop.make_WebApplicationService(
            FakePostgresListenerService(), sentinel.status_worker
        )
        self.assertIsInstance(service, webapp.WebApplicationService)
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_WebApplicationService,
            eventloop.loop.factories["web"]["factory"],
        )
        # Has a dependency of postgres-listener.
        self.assertEqual(
            ["postgres-listener-worker", "status-worker"],
            eventloop.loop.factories["web"]["requires"],
        )
        self.assertFalse(eventloop.loop.factories["web"]["only_on_master"])

    def test_make_VersionUpdateCheckService(self):
        service = eventloop.make_VersionUpdateCheckService()
        self.assertIsInstance(service, RegionVersionUpdateCheckService)
        self.assertIs(
            eventloop.loop.factories["version-check"]["factory"],
            eventloop.make_VersionUpdateCheckService,
        )

    def test_make_RackControllerService(self):
        service = eventloop.make_RackControllerService(
            FakePostgresListenerService(), sentinel.rpc_advertise
        )
        self.assertIsInstance(service, rack_controller.RackControllerService)
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_RackControllerService,
            eventloop.loop.factories["rack-controller"]["factory"],
        )
        # Has a dependency of ipc-worker and postgres-listener.
        self.assertEqual(
            ["ipc-worker", "postgres-listener-worker"],
            eventloop.loop.factories["rack-controller"]["requires"],
        )
        self.assertFalse(
            eventloop.loop.factories["rack-controller"]["only_on_master"]
        )

    def test_make_ServiceMonitorService(self):
        service = eventloop.make_ServiceMonitorService()
        self.assertIsInstance(
            service, service_monitor_service.ServiceMonitorService
        )
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_ServiceMonitorService,
            eventloop.loop.factories["service-monitor"]["factory"],
        )
        self.assertEqual(
            [], eventloop.loop.factories["service-monitor"]["requires"]
        )
        self.assertTrue(
            eventloop.loop.factories["service-monitor"]["only_on_master"]
        )

    def test_make_StatusWorkerService(self):
        service = eventloop.make_StatusWorkerService(sentinel.dbtasks)
        self.assertIsInstance(service, api_twisted.StatusWorkerService)
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_StatusWorkerService,
            eventloop.loop.factories["status-worker"]["factory"],
        )
        # Has a dependency of database-tasks.
        self.assertEqual(
            ["database-tasks"],
            eventloop.loop.factories["status-worker"]["requires"],
        )
        self.assertFalse(
            eventloop.loop.factories["status-worker"]["only_on_master"]
        )

    def test_make_NetworkTimeProtocolService(self):
        service = eventloop.make_NetworkTimeProtocolService()
        self.assertIsInstance(service, ntp.RegionNetworkTimeProtocolService)
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_NetworkTimeProtocolService,
            eventloop.loop.factories["ntp"]["factory"],
        )
        # Has a no dependencies.
        self.assertEqual([], eventloop.loop.factories["ntp"]["requires"])
        self.assertTrue(eventloop.loop.factories["ntp"]["only_on_master"])

    def test_make_SyslogService(self):
        service = eventloop.make_SyslogService()
        self.assertIsInstance(service, syslog.RegionSyslogService)
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_SyslogService,
            eventloop.loop.factories["syslog"]["factory"],
        )
        # Has a no dependencies.
        self.assertEqual([], eventloop.loop.factories["syslog"]["requires"])
        self.assertTrue(eventloop.loop.factories["syslog"]["only_on_master"])

    def test_make_WorkersService(self):
        service = eventloop.make_WorkersService()
        self.assertIsInstance(service, workers.WorkersService)
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_WorkersService,
            eventloop.loop.factories["workers"]["factory"],
        )
        # Has a no dependencies.
        self.assertEqual([], eventloop.loop.factories["workers"]["requires"])
        self.assertTrue(eventloop.loop.factories["workers"]["only_on_master"])
        self.assertTrue(eventloop.loop.factories["workers"]["not_all_in_one"])

    def test_make_IPCMasterService(self):
        service = eventloop.make_IPCMasterService()
        self.assertIsInstance(service, ipc.IPCMasterService)
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_IPCMasterService,
            eventloop.loop.factories["ipc-master"]["factory"],
        )
        # Has a no dependencies.
        self.assertEqual(
            [], eventloop.loop.factories["ipc-master"]["requires"]
        )
        # Has an optional dependency on workers.
        self.assertEqual(
            ["workers"], eventloop.loop.factories["ipc-master"]["optional"]
        )
        self.assertTrue(
            eventloop.loop.factories["ipc-master"]["only_on_master"]
        )

    def test_make_IPCWorkerService(self):
        service = eventloop.make_IPCWorkerService()
        self.assertIsInstance(service, ipc.IPCWorkerService)
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_IPCWorkerService,
            eventloop.loop.factories["ipc-worker"]["factory"],
        )
        # Has a no dependencies.
        self.assertEqual(
            [], eventloop.loop.factories["ipc-worker"]["requires"]
        )
        self.assertFalse(
            eventloop.loop.factories["ipc-worker"]["only_on_master"]
        )

    def test_make_PrometheusExporterService(self):
        service = eventloop.make_PrometheusExporterService()
        self.assertIsInstance(service, StreamServerEndpointService)
        self.assertEqual(service.endpoint._port, REGION_PROMETHEUS_PORT)
        # It is registered as a factory in RegionEventLoop.
        self.assertIs(
            eventloop.make_PrometheusExporterService,
            eventloop.loop.factories["prometheus-exporter"]["factory"],
        )
        self.assertTrue(
            eventloop.loop.factories["prometheus-exporter"]["only_on_master"]
        )

    def test_make_CertificateExpirationCheckService(self):
        service = eventloop.make_CertificateExpirationCheckService()
        self.assertIsInstance(service, CertificateExpirationCheckService)
        self.assertIs(
            eventloop.loop.factories["certificate-expiration-check"][
                "factory"
            ],
            eventloop.make_CertificateExpirationCheckService,
        )

    def test_make_VaultSecretsCleanupService(self):
        service = eventloop.make_VaultSecretsCleanupService()
        self.assertIsInstance(service, VaultSecretsCleanupService)
        self.assertIs(
            eventloop.loop.factories["vault-secrets-cleanup"]["factory"],
            eventloop.make_VaultSecretsCleanupService,
        )


class TestDisablingDatabaseConnections(MAASServerTestCase):
    @wait_for_reactor
    def test_connections_are_all_stubs_in_the_event_loop(self):
        self.assertTrue(isInIOThread())
        for alias in connections:
            connection = connections[alias]
            # isinstance() fails because it references __bases__, so
            # compare types here.
            self.assertEqual(DisabledDatabaseConnection, type(connection))

    @transactional
    def test_connections_are_all_usable_outside_the_event_loop(self):
        self.assertFalse(isInIOThread())
        for alias in connections:
            connection = connections[alias]
            self.assertTrue(connection.is_usable())
