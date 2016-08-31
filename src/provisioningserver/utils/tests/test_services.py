# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for services."""

__all__ = []

import threading
from unittest.mock import (
    call,
    Mock,
    sentinel,
)

from maastesting.factory import factory
from maastesting.matchers import (
    DocTestMatches,
    HasLength,
    IsFiredDeferred,
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.utils import services
from provisioningserver.utils.services import (
    JSONPerLineProtocol,
    MDNSResolverService,
    NeighbourDiscoveryService,
    NeighbourObservationProtocol,
    NetworksMonitoringService,
    ProcessProtocolService,
)
from provisioningserver.utils.twisted import pause
from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    Is,
    IsInstance,
    Not,
)
from testtools.tests.twistedsupport.test_deferred import extract_result
from twisted.application.service import MultiService
from twisted.internet import reactor
from twisted.internet.defer import (
    DeferredQueue,
    inlineCallbacks,
    succeed,
)
from twisted.internet.error import (
    ProcessDone,
    ProcessExitedAlready,
    ProcessTerminated,
)
from twisted.python import threadable
from twisted.python.failure import Failure


class StubNetworksMonitoringService(NetworksMonitoringService):
    """Concrete subclass for testing."""

    def __init__(self):
        super().__init__(reactor)
        self.iterations = DeferredQueue()
        self.interfaces = []

    def updateInterfaces(self):
        d = super().updateInterfaces()
        d.addBoth(self.iterations.put)
        return d

    def recordInterfaces(self, interfaces):
        self.interfaces.append(interfaces)

    def reportNeighbours(self, neighbours):
        pass

    def reportMDNSEntries(self, neighbours):
        pass


class TestNetworksMonitoringService(MAASTestCase):
    """Tests of `NetworksMonitoringService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def makeService(self):
        service = StubNetworksMonitoringService()
        self.addCleanup(service._releaseSoleResponsibility)
        return service

    def test_init(self):
        service = self.makeService()
        self.assertThat(service, IsInstance(MultiService))
        self.assertThat(
            service.interface_monitor.step,
            Equals(service.interval))
        self.assertThat(service.interface_monitor.call, Equals(
            (service.updateInterfaces, (), {})))

    @inlineCallbacks
    def test_get_all_interfaces_definition_is_called_in_thread(self):
        service = self.makeService()
        self.patch(
            services, "get_all_interfaces_definition",
            threading.current_thread)
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, HasLength(1))
        [thread] = service.interfaces
        self.assertThat(thread, IsInstance(threading.Thread))
        self.assertThat(thread, Not(Equals(threadable.ioThread)))

    @inlineCallbacks
    def test_getInterfaces_called_to_get_configuration(self):
        service = self.makeService()
        getInterfaces = self.patch(service, "getInterfaces")
        getInterfaces.return_value = succeed(sentinel.config)
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, Equals([sentinel.config]))

    @inlineCallbacks
    def test_logs_errors(self):
        service = self.makeService()
        with TwistedLoggerFixture() as logger:
            error_message = factory.make_string()
            get_interfaces = self.patch(
                services, "get_all_interfaces_definition")
            get_interfaces.side_effect = Exception(error_message)
            yield service.updateInterfaces()
        self.assertThat(logger.output, DocTestMatches(
            "Failed to update and/or record network interface configuration"
            "..."))

    @inlineCallbacks
    def test_recordInterfaces_called_when_nothing_previously_recorded(self):
        get_interfaces = self.patch(services, "get_all_interfaces_definition")
        get_interfaces.side_effect = [sentinel.config]

        service = self.makeService()
        self.assertThat(service.interfaces, Equals([]))
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, Equals([sentinel.config]))

        self.assertThat(get_interfaces, MockCalledOnceWith())

    @inlineCallbacks
    def test_recordInterfaces_called_when_interfaces_changed(self):
        get_interfaces = self.patch(services, "get_all_interfaces_definition")
        # Configuration changes between the first and second call.
        get_interfaces.side_effect = [sentinel.config1, sentinel.config2]

        service = self.makeService()
        self.assertThat(service.interfaces, HasLength(0))
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, Equals([sentinel.config1]))
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, Equals(
            [sentinel.config1, sentinel.config2]))

        self.assertThat(get_interfaces, MockCallsMatch(call(), call()))

    @inlineCallbacks
    def test_recordInterfaces_not_called_when_interfaces_not_changed(self):
        get_interfaces = self.patch(services, "get_all_interfaces_definition")
        # Configuration does NOT change between the first and second call.
        get_interfaces.side_effect = [sentinel.config1, sentinel.config1]

        service = self.makeService()
        self.assertThat(service.interfaces, HasLength(0))
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, Equals([sentinel.config1]))
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, Equals([sentinel.config1]))

        self.assertThat(get_interfaces, MockCallsMatch(call(), call()))

    @inlineCallbacks
    def test_recordInterfaces_called_after_failure(self):
        get_interfaces = self.patch(services, "get_all_interfaces_definition")
        get_interfaces.return_value = sentinel.config

        service = self.makeService()
        recordInterfaces = self.patch(service, "recordInterfaces")
        recordInterfaces.side_effect = [Exception, None, None]

        # Using the logger fixture prevents the test case from failing due
        # to the logged exception.
        with TwistedLoggerFixture():
            # recordInterfaces is called the first time, as expected.
            recordInterfaces.reset_mock()
            yield service.updateInterfaces()
            self.assertThat(recordInterfaces, MockCalledOnceWith(
                sentinel.config))

            # recordInterfaces is called the second time too; the service noted
            # that it crashed last time and knew to run it again.
            recordInterfaces.reset_mock()
            yield service.updateInterfaces()
            self.assertThat(recordInterfaces, MockCalledOnceWith(
                sentinel.config))

            # recordInterfaces is NOT called the third time; the service noted
            # that the configuration had not changed.
            recordInterfaces.reset_mock()
            yield service.updateInterfaces()
            self.assertThat(recordInterfaces, MockNotCalled())

    @inlineCallbacks
    def test_assumes_sole_responsibility_before_updating(self):
        # A filesystem lock is used to prevent multiple network monitors from
        # running on each host machine.
        lock = NetworksMonitoringService._lock

        # Not locked before creating the service.
        self.assertFalse(lock.is_locked())

        # Still not locked after instantiating the service.
        service = self.makeService()
        self.assertFalse(lock.is_locked())

        # It's locked when the service is started and has begun iterating.
        service.startService()
        try:
            # It's locked once the first iteration is done.
            yield service.iterations.get()
            self.assertTrue(lock.is_locked())

            # It remains locked as the service iterates.
            yield service.updateInterfaces()
            self.assertTrue(lock.is_locked())

        finally:
            yield service.stopService()

        # It's unlocked now that the service is stopped.
        self.assertFalse(lock.is_locked())

        # Interfaces were recorded.
        self.assertThat(service.interfaces, Not(Equals([])))

    @inlineCallbacks
    def test_does_not_update_if_cannot_assume_sole_responsibility(self):
        # A filesystem lock is used to prevent multiple network monitors from
        # running on each host machine.
        lock = NetworksMonitoringService._lock

        with lock:
            service = self.makeService()
            # Iterate a few times.
            yield service.updateInterfaces()
            yield service.updateInterfaces()
            yield service.updateInterfaces()

        # Interfaces were NOT recorded.
        self.assertThat(service.interfaces, Equals([]))

    @inlineCallbacks
    def test_attempts_to_assume_sole_responsibility_on_each_iteration(self):
        # A filesystem lock is used to prevent multiple network monitors from
        # running on each host machine.
        lock = NetworksMonitoringService._lock

        with lock:
            service = self.makeService()
            # Iterate one time.
            yield service.updateInterfaces()

        # Interfaces have not been recorded yet.
        self.assertThat(service.interfaces, Equals([]))
        # Iterate once more and ...
        yield service.updateInterfaces()
        # ... interfaces ARE recorded.
        self.assertThat(service.interfaces, Not(Equals([])))


class TestJSONPerLineProtocol(MAASTestCase):
    """Tests for `JSONPerLineProtocol`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    @inlineCallbacks
    def test__propagates_exit_errors(self):
        proto = JSONPerLineProtocol(callback=lambda json: None)
        reactor.spawnProcess(proto, b"false", (b"false",))
        with ExpectedException(ProcessTerminated, ".* exit code 1"):
            yield proto.done

    def test__parses_only_full_lines(self):
        callback = Mock()
        proto = JSONPerLineProtocol(callback=callback)
        proto.connectionMade()
        # Send an empty JSON dictionary using 3 separate writes.
        proto.outReceived(b"{")
        # No callback yet...
        self.expectThat(callback, MockCallsMatch())
        proto.outReceived(b"}")
        # Still no callback...
        self.expectThat(callback, MockCallsMatch())
        proto.outReceived(b"\n")
        # After a newline, we expect the JSON to be parsed and the callback
        # to receive an empty Python dictionary (which corresponds to the JSON
        # that was sent.)
        self.expectThat(callback, MockCallsMatch(call([{}])))

    def test__ignores_interspersed_zero_length_writes(self):
        callback = Mock()
        proto = JSONPerLineProtocol(callback=callback)
        proto.connectionMade()
        proto.outReceived(b"")
        self.expectThat(callback, MockCallsMatch())
        proto.outReceived(b"{}\n")
        self.expectThat(callback, MockCallsMatch(call([{}])))
        proto.outReceived(b"")
        self.expectThat(callback, MockCallsMatch(call([{}])))
        proto.outReceived(b"{}\n")
        self.expectThat(callback, MockCallsMatch(call([{}]), call([{}])))

    def test__logs_non_json_output(self):
        callback = Mock()
        proto = JSONPerLineProtocol(callback=callback)
        proto.connectionMade()
        with TwistedLoggerFixture() as logger:
            proto.outReceived(b"{\n")
        self.assertThat(
            logger.output, DocTestMatches("Failed to parse JSON: ..."))

    def test__logs_stderr(self):
        message = factory.make_name("message")
        callback = Mock()
        proto = JSONPerLineProtocol(callback=callback)
        proto.connectionMade()
        with TwistedLoggerFixture() as logger:
            proto.errReceived((message + "\n").encode("ascii"))
        self.assertThat(logger.output, Equals(message))

    def test__logs_only_full_lines_from_stderr(self):
        message = factory.make_name("message")
        callback = Mock()
        proto = JSONPerLineProtocol(callback=callback)
        proto.connectionMade()
        with TwistedLoggerFixture() as logger:
            proto.errReceived(message.encode("ascii"))
        self.assertThat(logger.output, Equals(""))

    def test__logs_stderr_at_process_end(self):
        message = factory.make_name("message")
        callback = Mock()
        proto = JSONPerLineProtocol(callback=callback)
        proto.connectionMade()
        with TwistedLoggerFixture() as logger:
            proto.errReceived(message.encode("ascii"))
            self.assertThat(logger.output, Equals(""))
            proto.processEnded(Failure(ProcessDone(0)))
        self.assertThat(logger.output, Equals(message))

    def test__propagates_errors_from_command(self):
        callback = Mock()
        proto = JSONPerLineProtocol(callback=callback)
        proto.connectionMade()
        reason = Failure(ProcessTerminated(1))
        proto.processEnded(reason)
        self.assertRaises(ProcessTerminated, extract_result, proto.done)


class TestNeighbourObservationProtocol(MAASTestCase):
    """Tests for `NeighbourObservationProtocol`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_adds_interface(self):
        callback = Mock()
        ifname = factory.make_name('eth')
        proto = NeighbourObservationProtocol(ifname, callback=callback)
        proto.connectionMade()
        proto.outReceived(b"{}\n")
        self.expectThat(
            callback, MockCallsMatch(call([{"interface": ifname}])))


class TrueProcessProtocolService(ProcessProtocolService):

    def getProcessParameters(self):
        return ["/bin/true"]


class FalseProcessProtocolService(ProcessProtocolService):

    def getProcessParameters(self):
        return ["/bin/false"]


class CatProcessProtocolService(ProcessProtocolService):

    def getProcessParameters(self):
        return ["/bin/cat"]


class EchoProcessProtocolService(ProcessProtocolService):

    def getProcessParameters(self):
        return ["/bin/echo", "{}\n"]


class MockJSONProtocol(JSONPerLineProtocol):
    pass


class TestProcessProtocolService(MAASTestCase):
    """Tests for `JSONPerLineProtocol`."""

    run_tests_with = MAASTwistedRunTest.make_factory(debug=True, timeout=5)

    def test__base_class_cannot_be_used(self):
        with ExpectedException(TypeError):
            ProcessProtocolService(
                description="Mock process", protocol=Mock())

    @inlineCallbacks
    def test__starts_and_stops_process(self):
        protocol = MockJSONProtocol()
        service = CatProcessProtocolService(
            description="Unit test process", protocol=protocol)
        mock_callback = Mock()
        protocol.done.addCallback(mock_callback)
        service.startService()
        yield service.stopService()
        self.assertTrue(mock_callback.called)
        yield pause(0.0)
        self.assertThat(protocol.done, IsFiredDeferred())
        self.assertThat(extract_result(protocol.done), Is(None))
        with ExpectedException(ProcessExitedAlready):
            service.process.signalProcess("INT")

    @inlineCallbacks
    def test__handles_normal_process_exit(self):
        protocol = MockJSONProtocol()
        service = TrueProcessProtocolService(
            description="Unit test process", protocol=protocol)
        mock_callback = Mock()
        protocol.done.addCallback(mock_callback)
        service.startService()
        yield service.stopService()
        self.assertTrue(mock_callback.called)
        yield pause(0.0)
        self.assertThat(protocol.done, IsFiredDeferred())
        self.assertThat(extract_result(protocol.done), Is(None))

    @inlineCallbacks
    def test__handles_abnormal_process_exit(self):
        protocol = MockJSONProtocol()
        service = FalseProcessProtocolService(
            description="Unit test process", protocol=protocol)
        mock_errback = Mock()
        mock_callback = Mock()
        protocol.done.addCallback(mock_callback)
        protocol.done.addErrback(mock_errback)
        service.startService()
        yield service.stopService()
        self.assertTrue(mock_errback.called)
        self.assertFalse(mock_callback.called)
        yield pause(0.0)
        self.assertThat(protocol.done, IsFiredDeferred())
        self.assertThat(extract_result(protocol.done), Equals(None))

    @inlineCallbacks
    def test__calls_protocol_callback(self):
        callback = Mock()
        protocol = MockJSONProtocol(callback=callback)
        service = EchoProcessProtocolService(
            description="Unit test process", protocol=protocol)
        service.startService()
        # Wait for the protocol to finish. (the echo process will stop)
        yield protocol.done
        self.assertThat(callback, MockCalledOnceWith([{}]))
        yield service.stopService()
        yield pause(0.0)
        self.assertThat(protocol.done, IsFiredDeferred())
        self.assertThat(extract_result(protocol.done), Equals(None))


class TestNeighbourDiscoveryService(MAASTestCase):
    """Tests for `NeighbourDiscoveryService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test__returns_expected_arguments(self):
        ifname = factory.make_name('eth')
        service = NeighbourDiscoveryService(ifname, Mock())
        args = service.getProcessParameters()
        self.assertThat(args, HasLength(3))
        self.assertTrue(args[0].endswith(b'maas-rack'))
        self.assertTrue(args[1], Equals(b"observe-arp"))
        self.assertTrue(args[2], Equals(ifname.encode('utf-8')))


class TestMDNSResolverService(MAASTestCase):
    """Tests for `MDNSResolverService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test__returns_expected_arguments(self):
        service = MDNSResolverService(Mock())
        args = service.getProcessParameters()
        self.assertThat(args, HasLength(2))
        self.assertTrue(args[0].endswith(b"maas-rack"))
        self.assertTrue(args[1], Equals(b"observe-mdns"))
