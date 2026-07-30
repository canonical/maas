# Copyright 2016-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the region controller service."""

from unittest import TestCase
from unittest.mock import ANY, call, MagicMock, sentinel

from twisted.internet import reactor
from twisted.internet.defer import fail, inlineCallbacks, succeed

from maasserver import eventloop, region_controller
from maasserver.region_controller import RegionControllerService
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.crochet import wait_for
from provisioningserver.utils.events import Event

wait_for_reactor = wait_for()


class TestRegionControllerService(MAASServerTestCase):
    assertRaises = TestCase.assertRaises

    def make_service(self, listener=MagicMock(), dbtasks=MagicMock()):  # noqa: B008
        # Don't retry on failure or the tests will loop forever.
        return RegionControllerService(listener, dbtasks, retryOnFailure=False)

    def test_init_sets_properties(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        self.assertEqual(service.clock, reactor)
        self.assertIsNone(service.processingDefer)
        self.assertTrue(service.needsDNSUpdate)
        self.assertEqual(service.postgresListener, sentinel.listener)
        self.assertEqual(service.dbtasks, sentinel.dbtasks)

    @wait_for_reactor
    @inlineCallbacks
    def test_startService_registers_with_postgres_listener(self):
        listener = MagicMock()
        service = self.make_service(listener)
        service.startService()
        yield service.processingDefer
        listener.register.assert_has_calls(
            [
                call("sys_proxy", service.markProxyForUpdate),
                call("sys_vault_migration", service.restartRegion),
            ]
        )

    def test_startService_markAllForUpdate_on_connect(self):
        listener = MagicMock()
        listener.events.connected = Event()
        service = self.make_service(listener)
        mock_mark_proxy_for_update = self.patch(service, "markProxyForUpdate")
        service.startService()
        service.postgresListener.events.connected.fire()
        mock_mark_proxy_for_update.assert_called_once()

    def test_stopService_calls_unregister_on_the_listener(self):
        listener = MagicMock()
        service = self.make_service(listener)
        service.stopService()
        listener.unregister.assert_has_calls(
            [
                call("sys_proxy", service.markProxyForUpdate),
                call("sys_vault_migration", service.restartRegion),
            ]
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_stopService_handles_canceling_processing(self):
        service = self.make_service()
        service.startProcessing()
        yield service.stopService()
        self.assertIsNone(service.processingDefer)

    def test_markProxyForUpdate_sets_needsProxyUpdate_and_starts_process(self):
        service = self.make_service()
        mock_startProcessing = self.patch(service, "startProcessing")
        service.markProxyForUpdate(None, None)
        self.assertTrue(service.needsProxyUpdate)
        mock_startProcessing.assert_called_once_with()

    def test_restart_region_restarts_eventloop(self):
        restart_mock = self.patch(eventloop, "restart")
        service = self.make_service()
        service.restartRegion("sys_vault_migration", "")
        restart_mock.assert_called_once()

    def test_startProcessing_doesnt_call_start_when_looping_call_running(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        mock_start = self.patch(service.processing, "start")
        service.processing.running = True
        service.startProcessing()
        mock_start.assert_not_called()

    def test_startProcessing_calls_start_when_looping_call_not_running(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        mock_start = self.patch(service.processing, "start")
        service.startProcessing()
        mock_start.assert_called_once_with(0.1, now=False)

    @wait_for_reactor
    @inlineCallbacks
    def test_process_doesnt_proxy_update_config_when_nothing_to_process(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        service.needsProxyUpdate = False
        mock_proxy_update_config = self.patch(
            region_controller, "proxy_update_config"
        )
        service.startProcessing()
        yield service.processingDefer
        mock_proxy_update_config.assert_not_called()

    @wait_for_reactor
    @inlineCallbacks
    @wait_for_reactor
    @inlineCallbacks
    def test_process_stops_processing(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        service.needsDNSUpdate = False
        service.startProcessing()
        yield service.processingDefer
        self.assertIsNone(service.processingDefer)

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_proxy(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        service.needsProxyUpdate = True
        mock_proxy_update_config = self.patch(
            region_controller, "proxy_update_config"
        )
        mock_proxy_update_config.return_value = succeed(None)
        mock_msg = self.patch(region_controller.log, "msg")
        service.startProcessing()
        yield service.processingDefer
        mock_proxy_update_config.assert_called_once_with(reload_proxy=True)
        mock_msg.assert_called_once_with("Successfully configured proxy.")

    @wait_for_reactor
    @inlineCallbacks
    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_proxy_logs_failure(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        service.needsProxyUpdate = True
        mock_proxy_update_config = self.patch(
            region_controller, "proxy_update_config"
        )
        mock_proxy_update_config.return_value = fail(factory.make_exception())
        mock_err = self.patch(region_controller.log, "err")
        service.startProcessing()
        yield service.processingDefer
        mock_proxy_update_config.assert_called_once_with(reload_proxy=True)
        mock_err.assert_called_once_with(ANY, "Failed configuring proxy.")
