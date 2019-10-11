# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the system controller service."""

__all__ = []

import random
from unittest.mock import call, create_autospec, Mock, sentinel

from crochet import wait_for
from maasserver import rack_controller
from maasserver.ipc import IPCWorkerService
from maasserver.rack_controller import RackControllerService
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maastesting.matchers import (
    MockAnyCall,
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from testtools import ExpectedException
from testtools.matchers import MatchesStructure
from twisted.internet import reactor
from twisted.internet.defer import Deferred, fail, inlineCallbacks, succeed


wait_for_reactor = wait_for(30)  # 30 seconds.


class TestRackControllerService(MAASTransactionServerTestCase):
    def test_init_sets_properties(self):
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        self.assertThat(
            service,
            MatchesStructure.byEquality(
                clock=reactor,
                starting=None,
                watching=set(),
                needsDHCPUpdate=set(),
                ipcWorker=sentinel.ipcWorker,
                postgresListener=sentinel.listener,
            ),
        )

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

        listener = Mock()
        service = RackControllerService(ipcWorker, listener)
        yield service.startService()
        self.assertThat(
            listener.register,
            MockCalledOnceWith(
                "sys_core_%d" % regionProcessId, service.coreHandler
            ),
        )
        self.assertEqual(regionProcessId, service.processId)

    @wait_for_reactor
    @inlineCallbacks
    def test_startService_clears_starting_once_complete(self):
        regionProcessId = random.randint(0, 100)

        ipcWorker = IPCWorkerService(sentinel.reactor)
        ipcWorker.processId.set(regionProcessId)

        listener = Mock()
        service = RackControllerService(ipcWorker, listener)
        yield service.startService()
        self.assertIsNone(service.starting)

    @wait_for_reactor
    def test_startService_handles_cancel(self):
        ipcWorker = IPCWorkerService(sentinel.reactor)

        listener = Mock()
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

        listener = Mock()
        service = RackControllerService(ipcWorker, listener)
        mock_coreHandler = self.patch(service, "coreHandler")
        yield service.startService()
        calls = [
            call("sys_core_%d" % process.id, "watch_%d" % rack.id)
            for rack in rack_controllers
        ]
        self.assertThat(mock_coreHandler, MockCallsMatch(*calls))

    @wait_for_reactor
    @inlineCallbacks
    def test_stopService_handles_canceling_startup(self):
        listener = Mock()
        service = RackControllerService(sentinel.ipcWorker, listener)
        service.processId = random.randint(0, 100)
        service.starting = Deferred()
        yield service.stopService()
        self.assertThat(
            listener.unregister,
            MockCalledOnceWith(
                "sys_core_%d" % service.processId, service.coreHandler
            ),
        )
        self.assertIsNone(service.starting)

    @wait_for_reactor
    @inlineCallbacks
    def test_stopService_calls_unregister_for_the_process(self):
        processId = random.randint(0, 100)
        listener = Mock()
        service = RackControllerService(sentinel.ipcWorker, listener)
        service.processId = processId
        yield service.stopService()
        self.assertThat(
            listener.unregister,
            MockCalledOnceWith("sys_core_%d" % processId, service.coreHandler),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_stopService_calls_unregister_for_all_watching(self):
        processId = random.randint(0, 100)
        watching = {random.randint(0, 100) for _ in range(3)}
        listener = Mock()
        service = RackControllerService(sentinel.ipcWorker, listener)
        service.processId = processId
        service.watching = watching
        yield service.stopService()
        self.assertThat(
            listener.unregister,
            MockAnyCall("sys_core_%d" % processId, service.coreHandler),
        )
        for watch_id in watching:
            self.assertThat(
                listener.unregister,
                MockAnyCall("sys_dhcp_%d" % watch_id, service.dhcpHandler),
            )

    def test_coreHandler_unwatch_calls_unregister(self):
        processId = random.randint(0, 100)
        rack_id = random.randint(0, 100)
        listener = Mock()
        service = RackControllerService(sentinel.ipcWorker, listener)
        service.processId = processId
        service.watching = {rack_id}
        service.needsDHCPUpdate = {rack_id}
        service.coreHandler("sys_core_%d" % processId, "unwatch_%d" % rack_id)
        self.assertThat(
            listener.unregister,
            MockCalledOnceWith("sys_dhcp_%d" % rack_id, service.dhcpHandler),
        )
        self.assertEquals(set(), service.watching)
        self.assertEquals(set(), service.needsDHCPUpdate)

    def test_coreHandler_unwatch_doesnt_call_unregister(self):
        processId = random.randint(0, 100)
        rack_id = random.randint(0, 100)
        listener = Mock()
        service = RackControllerService(sentinel.ipcWorker, listener)
        service.processId = processId
        service.coreHandler("sys_core_%d" % processId, "unwatch_%d" % rack_id)
        self.assertThat(listener.unregister, MockNotCalled())

    def test_coreHandler_watch_calls_register_and_startProcessing(self):
        processId = random.randint(0, 100)
        rack_id = random.randint(0, 100)
        listener = Mock()
        service = RackControllerService(sentinel.ipcWorker, listener)
        service.processId = processId
        mock_startProcessing = self.patch(service, "startProcessing")
        service.coreHandler("sys_core_%d" % processId, "watch_%d" % rack_id)
        self.assertThat(
            listener.register,
            MockCalledOnceWith("sys_dhcp_%d" % rack_id, service.dhcpHandler),
        )
        self.assertEquals(set([rack_id]), service.watching)
        self.assertEquals(set([rack_id]), service.needsDHCPUpdate)
        self.assertThat(mock_startProcessing, MockCalledOnceWith())

    def test_coreHandler_watch_doesnt_call_register(self):
        processId = random.randint(0, 100)
        rack_id = random.randint(0, 100)
        listener = Mock()
        service = RackControllerService(sentinel.ipcWorker, listener)
        service.processId = processId
        service.watching = set([rack_id])
        mock_startProcessing = self.patch(service, "startProcessing")
        service.coreHandler("sys_core_%d" % processId, "watch_%d" % rack_id)
        self.assertThat(listener.register, MockNotCalled())
        self.assertEquals(set([rack_id]), service.watching)
        self.assertEquals(set([rack_id]), service.needsDHCPUpdate)
        self.assertThat(mock_startProcessing, MockCalledOnceWith())

    def test_coreHandler_raises_ValueError_for_unknown_action(self):
        processId = random.randint(0, 100)
        rack_id = random.randint(0, 100)
        listener = Mock()
        service = RackControllerService(sentinel.ipcWorker, listener)
        service.processId = processId
        with ExpectedException(ValueError):
            service.coreHandler(
                "sys_core_%d" % processId, "invalid_%d" % rack_id
            )

    def test_dhcpHandler_adds_to_needsDHCPUpdate(self):
        rack_id = random.randint(0, 100)
        listener = Mock()
        service = RackControllerService(sentinel.ipcWorker, listener)
        service.watching = set([rack_id])
        mock_startProcessing = self.patch(service, "startProcessing")
        service.dhcpHandler("sys_dhcp_%d" % rack_id, "")
        self.assertEquals(set([rack_id]), service.needsDHCPUpdate)
        self.assertThat(mock_startProcessing, MockCalledOnceWith())

    def test_dhcpHandler_doesnt_add_to_needsDHCPUpdate(self):
        rack_id = random.randint(0, 100)
        listener = Mock()
        service = RackControllerService(sentinel.ipcWorker, listener)
        mock_startProcessing = self.patch(service, "startProcessing")
        service.dhcpHandler("sys_dhcp_%d" % rack_id, "")
        self.assertEquals(set(), service.needsDHCPUpdate)
        self.assertThat(mock_startProcessing, MockNotCalled())

    def test_startProcessing_doesnt_call_start_when_looping_call_running(self):
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        mock_start = self.patch(service.processing, "start")
        service.processing.running = True
        service.startProcessing()
        self.assertThat(mock_start, MockNotCalled())

    def test_startProcessing_calls_start_when_looping_call_not_running(self):
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        mock_start = self.patch(service.processing, "start")
        service.startProcessing()
        self.assertThat(mock_start, MockCalledOnceWith(0.1, now=False))

    @wait_for_reactor
    @inlineCallbacks
    def test_process_doesnt_call_processDHCP_when_not_running(self):
        rack_id = random.randint(0, 100)
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        service.watching = set([rack_id])
        service.needsDHCPUpdate = set([rack_id])
        service.running = False
        mock_processDHCP = self.patch(service, "processDHCP")
        service.startProcessing()
        yield service.processingDone
        self.assertThat(mock_processDHCP, MockNotCalled())

    @wait_for_reactor
    @inlineCallbacks
    def test_process_doesnt_call_processDHCP_when_nothing_to_process(self):
        rack_id = random.randint(0, 100)
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        service.watching = set([rack_id])
        service.needsDHCPUpdate = set()
        service.running = True
        mock_processDHCP = self.patch(service, "processDHCP")
        service.startProcessing()
        yield service.processingDone
        self.assertThat(mock_processDHCP, MockNotCalled())

    @wait_for_reactor
    @inlineCallbacks
    def test_process_calls_processDHCP_for_rack_controller(self):
        rack_id = random.randint(0, 100)
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        service.watching = set([rack_id])
        service.needsDHCPUpdate = set([rack_id])
        service.running = True
        mock_processDHCP = self.patch(service, "processDHCP")
        service.startProcessing()
        yield service.processingDone
        self.assertThat(mock_processDHCP, MockCalledOnceWith(rack_id))

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
        for _ in range(len(rack_ids)):
            yield service.processingDone
        for rack_id in rack_ids:
            self.assertThat(mock_processDHCP, MockAnyCall(rack_id))

    @wait_for_reactor
    @inlineCallbacks
    def test_process_calls_processDHCP_multiple_times_on_failure(self):
        rack_id = random.randint(0, 100)
        service = RackControllerService(sentinel.ipcWorker, sentinel.listener)
        service.watching = set([rack_id])
        service.needsDHCPUpdate = set([rack_id])
        service.running = True
        mock_processDHCP = self.patch(service, "processDHCP")
        mock_processDHCP.side_effect = [
            fail(factory.make_exception()),
            succeed(None),
        ]
        service.startProcessing()
        for _ in range(2):
            yield service.processingDone
        self.assertThat(
            mock_processDHCP, MockCallsMatch(call(rack_id), call(rack_id))
        )

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
        self.assertThat(mock_configure_dhcp, MockCalledOnceWith(rack))
