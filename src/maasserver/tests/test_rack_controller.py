# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the system controller service."""

import random
from unittest.mock import call, create_autospec, sentinel

from twisted.internet import reactor
from twisted.internet.defer import Deferred, fail, inlineCallbacks, succeed
from twisted.python.failure import Failure

from maasserver import rack_controller
from maasserver.ipc import IPCWorkerService
from maasserver.rack_controller import RackControllerService
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.triggers.testing import TransactionalHelpersMixin
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for

wait_for_reactor = wait_for()


class TestRackControllerService(
    TransactionalHelpersMixin, MAASTransactionServerTestCase
):
    def setUp(self):
        super().setUp()
        self.patch(RackControllerService, "PROCESSING_DELAY", 0)

    def test_init_sets_properties(self):
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        self.assertEqual(service.clock, reactor)
        self.assertIsNone(service.starting)
        self.assertEqual(service.watching, set())
        self.assertEqual(service.needsDHCPUpdate, set())
        self.assertIs(service.ipcWorker, sentinel.ipcWorker)
        self.assertIs(service.postgresListener, sentinel.listener)

    def test_startService_sets_starting_to_result_of_processId_get(self):
        ipcWorker = create_autospec(
            IPCWorkerService(sentinel.reactor), spec_set=True
        )
        service = RackControllerService(ipcWorker, sentinel.listener)
        observed = service.startService()
        processId = ipcWorker.processId
        self.assertEqual(processId.get.return_value, observed)
        self.assertEqual(processId.get.return_value, service.starting)

    @wait_for_reactor
    @inlineCallbacks
    def test_startService_registers_with_postgres_listener(self):
        regionProcessId = random.randint(0, 100)

        ipcWorker = IPCWorkerService(sentinel.reactor)
        ipcWorker.processId.set(regionProcessId)

        listener = self.make_listener_without_delay()
        yield listener.startService()
        service = RackControllerService(ipcWorker, listener)
        yield service.startService()
        yield listener.channelRegistrarDone
        sys_channel = f"sys_core_{regionProcessId}"
        self.assertIn(sys_channel, listener.listeners)
        self.assertIn(sys_channel, listener.registeredChannels)
        self.assertIn(service.coreHandler, listener.listeners[sys_channel])
        self.assertEqual(regionProcessId, service.processId)
        yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_startService_waits_for_channel_registrar(self):
        def fake_run_channel_registrar():
            listener.channelRegistrarDone = deferred

        def fake_core_handler(channel, message):
            core_handler_calls.append((channel, message))

        regionProcessId = random.randint(0, 100)

        ipcWorker = IPCWorkerService(sentinel.reactor)
        ipcWorker.processId.set(regionProcessId)

        listener = self.make_listener_without_delay()
        yield listener.startService()
        deferred = Deferred()
        listener.runChannelRegistrar = fake_run_channel_registrar
        deferred.errback(Failure(RuntimeError("boom")))
        core_handler_calls = []
        listener.coreHandler = fake_core_handler
        service = RackControllerService(ipcWorker, listener)
        try:
            yield service.startService()
        except RuntimeError:
            pass
        else:
            raise AssertionError("Should have failed.")
        self.assertEqual([], core_handler_calls)
        self.assertIsNotNone(service.starting)

        yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_startService_clears_starting_once_complete(self):
        regionProcessId = random.randint(0, 100)

        ipcWorker = IPCWorkerService(sentinel.reactor)
        ipcWorker.processId.set(regionProcessId)

        listener = self.make_listener_without_delay()
        service = RackControllerService(ipcWorker, listener)
        yield service.startService()
        self.assertIsNone(service.starting)

    @wait_for_reactor
    def test_startService_handles_cancel(self):
        ipcWorker = IPCWorkerService(sentinel.reactor)

        listener = self.make_listener_without_delay()
        service = RackControllerService(ipcWorker, listener)
        starting = service.startService()
        self.assertIs(starting, service.starting)
        # Should not raise an exception and starting should be set to None.
        starting.cancel()
        self.assertIsNone(service.starting)

    @wait_for_reactor
    @inlineCallbacks
    def test_startService_calls_coreHandler_with_monitoring_processes(self):
        @transactional
        def create_process_and_racks():
            process = factory.make_RegionControllerProcess()
            rack_controllers = [
                factory.make_RackController(managing_process=process)
                for _ in range(3)
            ]
            return process, rack_controllers

        process, rack_controllers = yield deferToDatabase(
            create_process_and_racks
        )

        ipcWorker = IPCWorkerService(sentinel.reactor)
        ipcWorker.processId.set(process.id)

        listener = self.make_listener_without_delay()
        service = RackControllerService(ipcWorker, listener)
        mock_coreHandler = self.patch(service, "coreHandler")
        yield service.startService()
        calls = [
            call(f"sys_core_{process.id}", f"watch_{rack.id}")
            for rack in rack_controllers
        ]
        mock_coreHandler.assert_has_calls(calls)

    @wait_for_reactor
    @inlineCallbacks
    def test_stopService_handles_canceling_startup(self):
        listener = self.make_listener_without_delay()
        service = RackControllerService(sentinel.ipcWorker, listener)
        service.processId = random.randint(0, 100)
        service.starting = Deferred()
        listener.register(f"sys_core_{service.processId}", service.coreHandler)
        yield service.stopService()
        self.assertNotIn(f"sys_core_{service.processId}", listener.listeners)
        self.assertIsNone(service.starting)

    @wait_for_reactor
    @inlineCallbacks
    def test_stopService_calls_unregister_for_all_watching(self):
        processId = random.randint(0, 100)
        watching = {random.randint(0, 100) for _ in range(3)}
        listener = self.make_listener_without_delay()
        service = RackControllerService(sentinel.ipcWorker, listener)
        service.processId = processId
        service.watching = watching
        listener.register(f"sys_core_{processId}", service.coreHandler)
        for watch_id in watching:
            listener.register(f"sys_dhcp_{watch_id}", service.dhcpHandler)

        yield service.stopService()

        self.assertNotIn(f"sys_core_{processId}", listener.listeners)
        for watch_id in watching:
            self.assertNotIn(f"sys_dhcp_{watch_id}", listener.listeners)

    def test_coreHandler_unwatch_calls_unregister(self):
        processId = random.randint(0, 100)
        rack_id = random.randint(0, 100)
        listener = self.make_listener_without_delay()
        service = RackControllerService(sentinel.ipcWorker, listener)
        service.processId = processId
        service.watching = {rack_id}
        service.needsDHCPUpdate = {rack_id}
        listener.register(f"sys_dhcp_{rack_id}", service.dhcpHandler)
        service.coreHandler("sys_core_%d" % processId, "unwatch_%d" % rack_id)
        self.assertNotIn(f"sys_dhcp_{rack_id}", listener.listeners)
        self.assertEqual(set(), service.watching)
        self.assertEqual(set(), service.needsDHCPUpdate)

    def test_coreHandler_unwatch_doesnt_call_unregister(self):
        processId = random.randint(0, 100)
        rack_id = random.randint(0, 100)
        listener = self.make_listener_without_delay()
        service = RackControllerService(sentinel.ipcWorker, listener)
        self.assertNotIn(rack_id, service.watching)
        listener.register(f"sys_dhcp_{rack_id}", service.dhcpHandler)
        service.processId = processId
        service.coreHandler("sys_core_%d" % processId, "unwatch_%d" % rack_id)
        self.assertEqual(
            {f"sys_dhcp_{rack_id}": [service.dhcpHandler]}, listener.listeners
        )

    def test_coreHandler_watch_calls_register_and_startProcessing(self):
        processId = random.randint(0, 100)
        rack_id = random.randint(0, 100)
        listener = self.make_listener_without_delay()
        service = RackControllerService(sentinel.ipcWorker, listener)
        service.processId = processId
        mock_startProcessing = self.patch(service, "startProcessing")
        sys_channel = f"sys_core_{processId}"
        service.coreHandler(sys_channel, "watch_%d" % rack_id)
        dhcp_channel = f"sys_dhcp_{rack_id}"
        self.assertIn(dhcp_channel, listener.listeners)
        self.assertIn(service.dhcpHandler, listener.listeners[dhcp_channel])
        self.assertEqual({rack_id}, service.watching)
        self.assertEqual({rack_id}, service.needsDHCPUpdate)
        mock_startProcessing.assert_called_once_with()

    def test_coreHandler_watch_doesnt_call_register(self):
        processId = random.randint(0, 100)
        rack_id = random.randint(0, 100)
        listener = self.make_listener_without_delay()
        service = RackControllerService(sentinel.ipcWorker, listener)
        service.processId = processId
        service.watching = {rack_id}
        mock_startProcessing = self.patch(service, "startProcessing")
        sys_channel = f"sys_core_{processId}"
        service.coreHandler(sys_channel, "watch_%d" % rack_id)
        self.assertNotIn(sys_channel, listener.listeners)
        self.assertNotIn(sys_channel, listener.registeredChannels)
        self.assertEqual({rack_id}, service.watching)
        self.assertEqual({rack_id}, service.needsDHCPUpdate)
        mock_startProcessing.assert_called_once_with()

    def test_coreHandler_raises_ValueError_for_unknown_action(self):
        processId = random.randint(0, 100)
        rack_id = random.randint(0, 100)
        listener = self.make_listener_without_delay()
        service = RackControllerService(sentinel.ipcWorker, listener)
        service.processId = processId
        with self.assertRaisesRegex(ValueError, "Unknown action: invalid"):
            service.coreHandler(f"sys_core_{processId}", f"invalid_{rack_id}")

    def test_dhcpHandler_adds_to_needsDHCPUpdate(self):
        rack_id = random.randint(0, 100)
        listener = self.make_listener_without_delay()
        service = RackControllerService(sentinel.ipcWorker, listener)
        service.watching = {rack_id}
        mock_startProcessing = self.patch(service, "startProcessing")
        service.dhcpHandler("sys_dhcp_%d" % rack_id, "")
        self.assertEqual({rack_id}, service.needsDHCPUpdate)
        mock_startProcessing.assert_called_once_with()

    def test_dhcpHandler_doesnt_add_to_needsDHCPUpdate(self):
        rack_id = random.randint(0, 100)
        listener = self.make_listener_without_delay()
        service = RackControllerService(sentinel.ipcWorker, listener)
        mock_startProcessing = self.patch(service, "startProcessing")
        service.dhcpHandler("sys_dhcp_%d" % rack_id, "")
        self.assertEqual(set(), service.needsDHCPUpdate)
        mock_startProcessing.assert_not_called()

    def test_startProcessing_doesnt_call_start_when_looping_call_running(self):
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        mock_start = self.patch(service.processing, "start")
        service.processing.running = True
        service.startProcessing()
        mock_start.assert_not_called()

    def test_startProcessing_calls_start_when_looping_call_not_running(self):
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        mock_start = self.patch(service.processing, "start")
        service.startProcessing()
        mock_start.assert_called_once_with(0, now=False)

    @wait_for_reactor
    @inlineCallbacks
    def test_process_doesnt_call_processDHCP_when_not_running(self):
        rack_id = random.randint(0, 100)
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        service.watching = {rack_id}
        service.needsDHCPUpdate = {rack_id}
        service.running = False
        mock_processDHCP = self.patch(service, "processDHCP")
        service.startProcessing()
        yield service.processingDone
        mock_processDHCP.assert_not_called()

    @wait_for_reactor
    @inlineCallbacks
    def test_process_doesnt_call_processDHCP_when_nothing_to_process(self):
        rack_id = random.randint(0, 100)
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        service.watching = {rack_id}
        service.needsDHCPUpdate = set()
        service.running = True
        mock_processDHCP = self.patch(service, "processDHCP")
        service.startProcessing()
        yield service.processingDone
        mock_processDHCP.assert_not_called()

    @wait_for_reactor
    @inlineCallbacks
    def test_process_calls_processDHCP_for_rack_controller(self):
        rack_id = random.randint(0, 100)
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        service.watching = {rack_id}
        service.needsDHCPUpdate = {rack_id}
        service.running = True
        mock_processDHCP = self.patch(service, "processDHCP")
        service.startProcessing()
        yield service.processingDone
        mock_processDHCP.assert_called_once_with(rack_id)

    @wait_for_reactor
    @inlineCallbacks
    def test_process_calls_processDHCP_multiple_times(self):
        rack_ids = [random.randint(0, 100) for _ in range(3)]
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        service.watching = set(rack_ids)
        service.needsDHCPUpdate = set(rack_ids)
        service.running = True
        mock_processDHCP = self.patch(service, "processDHCP")
        service.startProcessing()
        for rack_id in rack_ids:
            yield service.processingDone
            mock_processDHCP.assert_any_call(rack_id)

    @wait_for_reactor
    @inlineCallbacks
    def test_process_calls_processDHCP_multiple_times_on_failure(self):
        rack_id = random.randint(0, 100)
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        service.watching = {rack_id}
        service.needsDHCPUpdate = {rack_id}
        service.running = True
        mock_processDHCP = self.patch(service, "processDHCP")
        mock_processDHCP.side_effect = [
            fail(factory.make_exception()),
            succeed(None),
        ]
        service.startProcessing()
        for _ in range(2):
            yield service.processingDone
        mock_processDHCP.assert_has_calls([call(rack_id), call(rack_id)])

    @wait_for_reactor
    @inlineCallbacks
    def test_processDHCP_calls_configure_dhcp(self):
        rack = yield deferToDatabase(
            transactional(factory.make_RackController)
        )
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        mock_configure_dhcp = self.patch(
            rack_controller.dhcp, "configure_dhcp"
        )
        mock_configure_dhcp.return_value = succeed(None)
        yield service.processDHCP(rack.id)
        mock_configure_dhcp.assert_called_once_with(rack)

    @wait_for_reactor
    @inlineCallbacks
    def test_processDHCP_unwatch_errback_unwatches_non_existent_watched_rackd(
        self,
    ):
        rack_id = random.randint(0, 100)
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        service.watching = {rack_id}
        service.needsDHCPUpdate = {rack_id}
        service.running = True
        yield service.processDHCP(rack_id)
        self.assertNotIn(rack_id, service.watching)

    @wait_for_reactor
    @inlineCallbacks
    def test_processDHCP_unwatch_errback_ignores_missing_nonwatched_rackd(
        self,
    ):
        rack_id = random.randint(0, 100)
        other_rack_id = rack_id + 3
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        service.watching = {other_rack_id}
        service.needsDHCPUpdate = {rack_id}
        service.running = True
        yield service.processDHCP(rack_id)
        self.assertNotIn(rack_id, service.watching)
        self.assertIn(other_rack_id, service.watching)

    @wait_for_reactor
    @inlineCallbacks
    def test_processDHCP_unwatch_errback_ignores_other_exceptions(self):
        rack = yield deferToDatabase(
            transactional(factory.make_RackController)
        )
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        service.running = True
        mock_configure_dhcp = self.patch(
            rack_controller.dhcp, "configure_dhcp"
        )
        exc = factory.make_exception()
        mock_configure_dhcp.return_value = fail(exc)
        try:
            yield service.processDHCP(rack.id)
        except Exception as thrown:
            self.assertEqual(exc, thrown)
        else:
            self.fail()
