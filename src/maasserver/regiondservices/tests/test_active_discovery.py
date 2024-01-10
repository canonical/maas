# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for service monitoring in the regiond."""


import random
from unittest.mock import Mock

from netaddr import IPNetwork
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import Clock

from maasserver.models import Config
from maasserver.regiondservices import active_discovery
from maasserver.regiondservices.active_discovery import ActiveDiscoveryService
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from maastesting.twisted import TwistedLoggerFixture

wait_for_reactor = wait_for()


class TestActiveDiscoveryService(MAASTransactionServerTestCase):
    def test_registers_and_unregisters_listener(self):
        mock_listener = Mock()
        register = mock_listener.register = Mock()
        unregister = mock_listener.unregister = Mock()
        clock = Clock()
        run = self.patch(ActiveDiscoveryService, "run")
        service = ActiveDiscoveryService(clock, mock_listener)
        # Make sure the service doesn't actually do anything.
        service.startService()
        self.assertEqual(service.call, (run, (), {}))
        self.assertEqual(service.step, active_discovery.CHECK_INTERVAL)
        self.assertEqual(service.clock, clock)
        register.assert_called_once_with(
            "config", service.refreshDiscoveryConfig
        )
        unregister.assert_not_called()
        service.stopService()
        unregister.assert_called_once_with(
            "config", service.refreshDiscoveryConfig
        )

    def test_run_calls_refreshDiscoveryConfig(self):
        clock = Clock()
        service = ActiveDiscoveryService(clock)
        refreshDiscoveryConfig = self.patch(service, "refreshDiscoveryConfig")
        service.startService()
        refreshDiscoveryConfig.assert_called_once_with()

    def test_run_calls_scanIfNeeded_if_discovery_enabled(self):
        clock = Clock()
        service = ActiveDiscoveryService(clock)
        self.patch(service, "refreshDiscoveryConfig")
        scanIfNeeded = self.patch(service, "scanIfNeeded")
        service.startService()
        # Pretend the call to refreshDiscoveryConfig enabled discovery,
        # as expected.
        service.discovery_enabled = True
        clock.advance(300)
        scanIfNeeded.assert_called_once_with()

    def test_run_handles_refresh_failure(self):
        clock = Clock()
        service = ActiveDiscoveryService(clock)
        refreshDiscoveryConfig = self.patch(service, "refreshDiscoveryConfig")
        refreshDiscoveryConfig.side_effect = Exception
        with TwistedLoggerFixture() as logger:
            service.startService()
        self.assertIn(
            ": error refreshing discovery configuration.\nTraceback (most recent call last):",
            logger.output,
        )

    def test_monitorServices_handles_scan_failure(self):
        clock = Clock()
        service = ActiveDiscoveryService(clock)
        self.patch(service, "refreshDiscoveryConfig")
        scanIfNeeded = self.patch(service, "scanIfNeeded")
        scanIfNeeded.side_effect = Exception
        # Pretend the call to refreshDiscoveryConfig enabled discovery,
        # as expected.
        service.discovery_enabled = True
        with TwistedLoggerFixture() as logger:
            service.run()
        self.assertIn(
            ": periodic scan failed.\nTraceback (most recent call last):",
            logger.output,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_scanIfNeeded_logs_success(self):
        service = ActiveDiscoveryService(Clock())
        try_lock_and_scan = self.patch(service, "try_lock_and_scan")
        try_lock_and_scan.return_value = "happy"
        service.discovery_enabled = True
        service.discovery_last_scan = 0
        service.discovery_interval = 1
        service.startService()
        with TwistedLoggerFixture() as logger:
            yield service.run()
        self.assertIn("Active network discovery: happy", logger.output)


class TestRefreshDiscoveryConfig(MAASTransactionServerTestCase):
    @transactional
    def set_last_scan(self, last_scan):
        Config.objects.set_config("active_discovery_last_scan", last_scan)

    @transactional
    def set_interval(self, interval):
        Config.objects.set_config("active_discovery_interval", interval)

    @wait_for_reactor
    @inlineCallbacks
    def test_stores_correct_values_and_fires_timer(self):
        expected_last_scan = random.randint(1, 1000)
        expected_interval = random.randint(1, 1000)
        yield deferToDatabase(self.set_interval, expected_interval)
        yield deferToDatabase(self.set_last_scan, expected_last_scan)
        service = ActiveDiscoveryService(Clock())
        run = self.patch(service, "run")
        with TwistedLoggerFixture() as logger:
            yield service.refreshDiscoveryConfig()
        self.assertIn("Discovery interval set to", logger.output)
        self.assertTrue(service.discovery_enabled)
        self.assertEqual(expected_interval, service.discovery_interval)
        self.assertEqual(expected_last_scan, service.discovery_last_scan)
        run.assert_called_once_with()

    @wait_for_reactor
    @inlineCallbacks
    def test_disables_discovery_if_interval_is_zero(self):
        expected_last_scan = random.randint(1, 1000)
        expected_interval = random.randint(1, 1000)
        yield deferToDatabase(self.set_interval, expected_interval)
        yield deferToDatabase(self.set_last_scan, expected_last_scan)
        service = ActiveDiscoveryService(Clock())
        self.patch(service, "run")
        yield service.refreshDiscoveryConfig()
        yield deferToDatabase(self.set_interval, 0)
        with TwistedLoggerFixture() as logger:
            yield service.refreshDiscoveryConfig()
        self.assertIn("discovery is disabled", logger.output)
        self.assertFalse(service.discovery_enabled)
        self.assertEqual(0, service.discovery_interval)
        self.assertEqual(expected_last_scan, service.discovery_last_scan)


class TestGetActiveDiscoveryConfig(MAASTransactionServerTestCase):
    def test_returns_expected_interval(self):
        expected_interval = random.randint(1, 1000)
        Config.objects.set_config(
            "active_discovery_interval", expected_interval
        )
        service = ActiveDiscoveryService(Clock())
        enabled, interval, last_scan = service.get_active_discovery_config()
        self.assertEqual(expected_interval, interval)
        # Enabled is True if interval is > 0
        self.assertTrue(enabled)

    def test_returns_expected_last_scan(self):
        expected_last_scan = random.randint(1, 1000)
        Config.objects.set_config(
            "active_discovery_last_scan", expected_last_scan
        )
        service = ActiveDiscoveryService(Clock())
        enabled, interval, last_scan = service.get_active_discovery_config()
        self.assertEqual(expected_last_scan, last_scan)

    def test_returns_disabled_if_interval_is_zero(self):
        expected_interval = 0
        expected_last_scan = 0
        Config.objects.set_config(
            "active_discovery_last_scan", expected_last_scan
        )
        Config.objects.set_config(
            "active_discovery_interval", expected_interval
        )
        service = ActiveDiscoveryService(Clock())
        enabled, interval, last_scan = service.get_active_discovery_config()
        self.assertFalse(enabled)

    def test_returns_disabled_if_interval_is_invalid(self):
        expected_interval = factory.make_name()
        expected_last_scan = factory.make_name()
        Config.objects.set_config(
            "active_discovery_last_scan", expected_last_scan
        )
        Config.objects.set_config(
            "active_discovery_interval", expected_interval
        )
        service = ActiveDiscoveryService(Clock())
        enabled, interval, last_scan = service.get_active_discovery_config()
        self.assertFalse(enabled)
        self.assertEqual(0, interval)
        self.assertEqual(0, last_scan)


class TestTryLockAndScan(MAASTransactionServerTestCase):
    """ActiveDiscoveryService.check_settings_and_scan_rack_networks tests."""

    def setUp(self):
        super().setUp()
        self.service = ActiveDiscoveryService(Clock())
        self.get_active_discovery_config = self.patch(
            self.service, "get_active_discovery_config"
        )
        self.getCurrentTimestamp = self.patch(
            self.service, "getCurrentTimestamp"
        )
        self.get_network_discovery_config = self.patch(
            active_discovery.Config.objects, "get_network_discovery_config"
        )
        self.get_cidr_list = self.patch(
            active_discovery.Subnet.objects,
            "get_cidr_list_for_periodic_active_scan",
        )
        self.mock_discovery_config = Mock()
        self.get_network_discovery_config.return_value = (
            self.mock_discovery_config
        )

    def test_aborts_if_passive_discovery_is_disabled(self):
        self.mock_discovery_config.passive = False
        result = self.service.try_lock_and_scan()
        self.assertIn("discovery is disabled. Skipping", result)

    def test_aborts_if_periodic_discovery_is_disabled(self):
        self.mock_discovery_config.passive = True
        self.get_active_discovery_config.return_value = (False, 0, 0)
        result = self.service.try_lock_and_scan()
        self.assertIn(
            "Skipping active scan. Periodic discovery is now disabled.",
            result,
        )

    def test_aborts_if_periodic_discovery_if_last_scan_too_recent(self):
        self.mock_discovery_config.passive = True
        self.get_active_discovery_config.return_value = (True, 10, 91)
        self.getCurrentTimestamp.return_value = 100
        result = self.service.try_lock_and_scan()
        self.assertIn("Another region controller is already scanning", result)

    def test_aborts_if_periodic_discovery_if_no_subnets_enabled(self):
        self.mock_discovery_config.passive = True
        self.get_active_discovery_config.return_value = (True, 10, 90)
        self.getCurrentTimestamp.return_value = 100
        self.get_cidr_list.return_value = []
        result = self.service.try_lock_and_scan()
        self.assertIn("Active scanning is not enabled on any subnet", result)

    def test_calls_scan_all_rack_networks_if_everything_is_okay(self):
        self.mock_discovery_config.passive = True
        self.get_active_discovery_config.return_value = (True, 10, 90)
        self.getCurrentTimestamp.return_value = 100
        cidrs = [IPNetwork(factory.make_ipv4_network())]
        self.get_cidr_list.return_value = cidrs
        scan_all_rack_networks = self.patch(
            active_discovery, "scan_all_rack_networks"
        )
        rpc_results = Mock()
        rpc_results.available = ["rack1"]
        scan_all_rack_networks.return_value = rpc_results
        get_result_string = self.patch(
            active_discovery, "get_scan_result_string_for_humans"
        )
        get_result_string.return_value = "sensational"
        result = self.service.try_lock_and_scan()
        self.assertEqual("sensational", result)
        scan_all_rack_networks.assert_called_once_with(cidrs=cidrs)
