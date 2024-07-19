# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import os
from pathlib import Path
from subprocess import Popen

import crochet
from django.db import connections
from django.db.backends.base.base import BaseDatabaseWrapper
from fixtures import EnvironmentVariableFixture
from testtools import monkey
from twisted.application.service import MultiService
from twisted.internet import reactor

from maasserver import eventloop
from maasserver.plugin import (
    Options,
    RegionAllInOneServiceMaker,
    RegionMasterServiceMaker,
    RegionWorkerServiceMaker,
)
from maasserver.utils.orm import (
    disable_all_database_connections,
    DisabledDatabaseConnection,
    enable_all_database_connections,
)
from maastesting.fixtures import TempDirectory
from maastesting.testcase import MAASTestCase
from provisioningserver import logger
from provisioningserver.utils.twisted import asynchronous, ThreadPool


def import_websocket_handlers():
    # Import the websocket handlers for their side-effects: merely defining
    # DeviceHandler, e.g., causes a database access, which will crash if it
    # happens inside the reactor thread where database access is forbidden and
    # prevented. The most sensible solution to this might be to disallow
    # database access at import time.
    import maasserver.websockets.handlers  # noqa


class TestOptions(MAASTestCase):
    """Tests for `maasserver.plugin.Options`."""

    def test_defaults(self):
        options = Options()
        self.assertEqual({}, options.defaults)

    def test_parse_minimal_options(self):
        options = Options()
        # The minimal set of options that must be provided.
        arguments = []
        options.parseOptions(arguments)  # No error.


class TestServiceMaker(MAASTestCase):
    """Mixin with helpers for all the service marker tests."""

    def setUp(self):
        super().setUp()
        self.patch(eventloop.loop, "services", MultiService())
        # Prevent setting the pdeathsig in tests.
        self.patch_autospec(RegionWorkerServiceMaker, "_set_pdeathsig")
        self.patch_autospec(crochet, "no_setup")
        self.patch_autospec(logger, "configure")
        # Enable database access in the reactor just for these tests.
        asynchronous(enable_all_database_connections, timeout=5)()
        import_websocket_handlers()

    def tearDown(self):
        super().tearDown()
        # Disable database access in the reactor again.
        asynchronous(disable_all_database_connections, timeout=5)()

    def assertConnectionsEnabled(self):
        for alias in connections:
            self.assertIsInstance(connections[alias], BaseDatabaseWrapper)

    def assertConnectionsDisabled(self):
        for alias in connections:
            self.assertEqual(
                DisabledDatabaseConnection, type(connections[alias])
            )


class TestRegionWorkerServiceMaker(TestServiceMaker):
    """Tests for `maasserver.plugin.RegionWorkerServiceMaker`."""

    def test_init(self):
        service_maker = RegionWorkerServiceMaker("Harry", "Hill")
        self.assertEqual("Harry", service_maker.tapname)
        self.assertEqual("Hill", service_maker.description)

    @asynchronous(timeout=5)
    def test_makeService_configures_pserv_debug(self):
        options = Options()
        service_maker = RegionWorkerServiceMaker("Harry", "Hill")
        mock_pserv = self.patch(service_maker, "_configurePservSettings")
        # Disable _configureThreads() as it's too invasive right now.
        self.patch_autospec(service_maker, "_configureThreads")
        service_maker.makeService(options)
        mock_pserv.assert_called_once_with()

    @asynchronous(timeout=5)
    def test_makeService_without_import_services(self):
        options = Options()
        service_maker = RegionWorkerServiceMaker("Harry", "Hill")
        # Disable _configureThreads() as it's too invasive right now.
        self.patch_autospec(service_maker, "_configureThreads")
        service = service_maker.makeService(options)
        self.assertIsInstance(service, MultiService)
        expected_services = {
            "database-tasks",
            "postgres-listener-worker",
            "rack-controller",
            "rpc",
            "status-worker",
            "web",
            "ipc-worker",
        }
        self.assertEqual(expected_services, service.namedServices.keys())
        self.assertEqual(
            len(service.namedServices),
            len(service.services),
            "Not all services are named.",
        )
        logger.configure.assert_called_once_with(
            options["verbosity"], logger.LoggingMode.TWISTD
        )
        crochet.no_setup.assert_called_once_with()

    @asynchronous(timeout=5)
    def test_makeService_with_import_services(self):
        options = Options()
        service_maker = RegionWorkerServiceMaker("Harry", "Hill")
        # Disable _configureThreads() as it's too invasive right now.
        self.patch_autospec(service_maker, "_configureThreads")
        # Set the environment variable to create the import services.
        self.useFixture(
            EnvironmentVariableFixture(
                "MAAS_REGIOND_RUN_IMPORTER_SERVICE", "true"
            )
        )
        service = service_maker.makeService(options)
        self.assertIsInstance(service, MultiService)
        expected_services = {
            "database-tasks",
            "postgres-listener-worker",
            "rack-controller",
            "rpc",
            "status-worker",
            "web",
            "ipc-worker",
            "import-resources",
            "import-resources-progress",
            "active-discovery",
        }
        self.assertEqual(expected_services, service.namedServices.keys())
        self.assertEqual(
            len(service.namedServices),
            len(service.services),
            "Not all services are named.",
        )
        logger.configure.assert_called_once_with(
            options["verbosity"], logger.LoggingMode.TWISTD
        )

        crochet.no_setup.assert_called_once_with()

    @asynchronous(timeout=5)
    def test_configures_thread_pool(self):
        # Patch and restore where it's visible because patching a running
        # reactor is potentially fairly harmful.
        patcher = monkey.MonkeyPatcher()
        patcher.add_patch(reactor, "threadpool", None)
        patcher.add_patch(reactor, "threadpoolForDatabase", None)
        patcher.patch()
        try:
            service_maker = RegionWorkerServiceMaker("Harry", "Hill")
            service_maker.makeService(Options())
            threadpool = reactor.getThreadPool()
            self.assertIsInstance(threadpool, ThreadPool)
        finally:
            patcher.restore()

    @asynchronous(timeout=5)
    def test_disables_database_connections_in_reactor(self):
        self.assertConnectionsEnabled()
        service_maker = RegionWorkerServiceMaker("Harry", "Hill")
        # Disable _configureThreads() as it's too invasive right now.
        self.patch_autospec(service_maker, "_configureThreads")
        service_maker.makeService(Options())
        self.assertConnectionsDisabled()


class TestRegionMasterServiceMaker(TestServiceMaker):
    """Tests for `maasserver.plugin.RegionMasterServiceMaker`."""

    def get_unused_pid(self):
        """Return a PID for a process that has just finished running."""
        proc = Popen(["/bin/true"])
        proc.wait()
        return proc.pid

    def test_init(self):
        service_maker = RegionMasterServiceMaker("Harry", "Hill")
        self.assertEqual("Harry", service_maker.tapname)
        self.assertEqual("Hill", service_maker.description)

    @asynchronous(timeout=5)
    def test_makeService_configures_pserv_debug(self):
        options = Options()
        service_maker = RegionMasterServiceMaker("Harry", "Hill")
        mock_pserv = self.patch(service_maker, "_configurePservSettings")
        # Disable _ensureConnection() its not allowed in the reactor.
        self.patch_autospec(service_maker, "_ensureConnection")
        # Disable _configureThreads() as it's too invasive right now.
        self.patch_autospec(service_maker, "_configureThreads")
        service_maker.makeService(options)
        mock_pserv.assert_called_once_with()

    @asynchronous(timeout=5)
    def test_makeService(self):
        options = Options()
        service_maker = RegionMasterServiceMaker("Harry", "Hill")
        # Disable _ensureConnection() its not allowed in the reactor.
        self.patch_autospec(service_maker, "_ensureConnection")
        # Disable _configureThreads() as it's too invasive right now.
        self.patch_autospec(service_maker, "_configureThreads")
        service = service_maker.makeService(options)
        self.assertIsInstance(service, MultiService)
        expected_services = {
            "database-tasks-master",
            "region-controller",
            "nonce-cleanup",
            "dns-publication-cleanup",
            "service-monitor",
            "status-monitor",
            "stats",
            "prometheus",
            "prometheus-exporter",
            "postgres-listener-master",
            "networks-monitor",
            "reverse-dns",
            "reverse-proxy",
            "certificate-expiration-check",
            "ntp",
            "syslog",
            "version-check",
            "workers",
            "ipc-master",
            "vault-secrets-cleanup",
            "temporal",
            "temporal-worker",
        }
        self.assertEqual(expected_services, service.namedServices.keys())
        self.assertEqual(
            len(service.namedServices),
            len(service.services),
            "Not all services are named.",
        )
        logger.configure.assert_called_once_with(
            options["verbosity"], logger.LoggingMode.TWISTD
        )
        crochet.no_setup.assert_called_once_with()

    @asynchronous(timeout=5)
    def test_makeService_cleanup_prometheus_dir(self):
        tmpdir = Path(self.useFixture(TempDirectory()).path)
        self.useFixture(
            EnvironmentVariableFixture("prometheus_multiproc_dir", str(tmpdir))
        )
        pid = os.getpid()
        file1 = tmpdir / f"histogram_{pid}.db"
        file1.touch()
        file2 = tmpdir / f"histogram_{self.get_unused_pid()}.db"
        file2.touch()

        service_maker = RegionMasterServiceMaker("Harry", "Hill")
        # Disable _ensureConnection() its not allowed in the reactor.
        self.patch_autospec(service_maker, "_ensureConnection")
        # Disable _configureThreads() as it's too invasive right now.
        self.patch_autospec(service_maker, "_configureThreads")
        service_maker.makeService(Options())
        self.assertTrue(file1.exists())
        self.assertFalse(file2.exists())

    @asynchronous(timeout=5)
    def test_configures_thread_pool(self):
        # Patch and restore where it's visible because patching a running
        # reactor is potentially fairly harmful.
        patcher = monkey.MonkeyPatcher()
        patcher.add_patch(reactor, "threadpool", None)
        patcher.add_patch(reactor, "threadpoolForDatabase", None)
        patcher.patch()
        try:
            service_maker = RegionMasterServiceMaker("Harry", "Hill")
            # Disable _ensureConnection() its not allowed in the reactor.
            self.patch_autospec(service_maker, "_ensureConnection")
            service_maker.makeService(Options())
            threadpool = reactor.getThreadPool()
            self.assertIsInstance(threadpool, ThreadPool)
        finally:
            patcher.restore()

    @asynchronous(timeout=5)
    def test_disables_database_connections_in_reactor(self):
        self.assertConnectionsEnabled()
        service_maker = RegionMasterServiceMaker("Harry", "Hill")
        # Disable _ensureConnection() its not allowed in the reactor.
        self.patch_autospec(service_maker, "_ensureConnection")
        # Disable _configureThreads() as it's too invasive right now.
        self.patch_autospec(service_maker, "_configureThreads")
        service_maker.makeService(Options())
        self.assertConnectionsDisabled()


class TestRegionAllInOneServiceMaker(TestServiceMaker):
    """Tests for `maasserver.plugin.RegionAllInOneServiceMaker`."""

    def test_init(self):
        service_maker = RegionAllInOneServiceMaker("Harry", "Hill")
        self.assertEqual("Harry", service_maker.tapname)
        self.assertEqual("Hill", service_maker.description)

    @asynchronous(timeout=5)
    def test_makeService_configures_pserv_debug(self):
        options = Options()
        service_maker = RegionAllInOneServiceMaker("Harry", "Hill")
        mock_pserv = self.patch(service_maker, "_configurePservSettings")
        # Disable _ensureConnection() its not allowed in the reactor.
        self.patch_autospec(service_maker, "_ensureConnection")
        # Disable _configureThreads() as it's too invasive right now.
        self.patch_autospec(service_maker, "_configureThreads")
        service_maker.makeService(options)
        mock_pserv.assert_called_once_with()

    @asynchronous(timeout=5)
    def test_makeService(self):
        options = Options()
        service_maker = RegionAllInOneServiceMaker("Harry", "Hill")
        # Disable _ensureConnection() its not allowed in the reactor.
        self.patch_autospec(service_maker, "_ensureConnection")
        # Disable _configureThreads() as it's too invasive right now.
        self.patch_autospec(service_maker, "_configureThreads")
        service = service_maker.makeService(options)
        self.assertIsInstance(service, MultiService)
        expected_services = {
            # Worker services.
            "database-tasks",
            "postgres-listener-worker",
            "rack-controller",
            "rpc",
            "service-monitor",
            "status-worker",
            "version-check",
            "web",
            "ipc-worker",
            # Master services.
            "database-tasks-master",
            "region-controller",
            "nonce-cleanup",
            "dns-publication-cleanup",
            "status-monitor",
            "stats",
            "prometheus",
            "prometheus-exporter",
            "import-resources",
            "import-resources-progress",
            "postgres-listener-master",
            "networks-monitor",
            "active-discovery",
            "reverse-dns",
            "reverse-proxy",
            "vault-secrets-cleanup",
            "certificate-expiration-check",
            "ntp",
            "syslog",
            # "workers",  Prevented in all-in-one.
            "ipc-master",
            "temporal",
            "temporal-worker",
        }
        self.assertEqual(expected_services, service.namedServices.keys())
        self.assertEqual(
            len(service.namedServices),
            len(service.services),
            "Not all services are named.",
        )
        logger.configure.assert_called_once_with(
            options["verbosity"], logger.LoggingMode.TWISTD
        )
        crochet.no_setup.assert_called_once_with()

    @asynchronous(timeout=5)
    def test_configures_thread_pool(self):
        # Patch and restore where it's visible because patching a running
        # reactor is potentially fairly harmful.
        patcher = monkey.MonkeyPatcher()
        patcher.add_patch(reactor, "threadpool", None)
        patcher.add_patch(reactor, "threadpoolForDatabase", None)
        patcher.patch()
        try:
            service_maker = RegionAllInOneServiceMaker("Harry", "Hill")
            # Disable _ensureConnection() its not allowed in the reactor.
            self.patch_autospec(service_maker, "_ensureConnection")
            service_maker.makeService(Options())
            threadpool = reactor.getThreadPool()
            self.assertIsInstance(threadpool, ThreadPool)
        finally:
            patcher.restore()

    @asynchronous(timeout=5)
    def test_disables_database_connections_in_reactor(self):
        self.assertConnectionsEnabled()
        service_maker = RegionAllInOneServiceMaker("Harry", "Hill")
        # Disable _ensureConnection() its not allowed in the reactor.
        self.patch_autospec(service_maker, "_ensureConnection")
        # Disable _configureThreads() as it's too invasive right now.
        self.patch_autospec(service_maker, "_configureThreads")
        service_maker.makeService(Options())
        self.assertConnectionsDisabled()
