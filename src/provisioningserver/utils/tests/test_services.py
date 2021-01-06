# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for services."""


from functools import partial
import random
import socket
import threading
from unittest.mock import ANY, call, Mock, sentinel
from uuid import uuid1

from testtools import ExpectedException
from testtools.matchers import Equals, Is, IsInstance, Not
from twisted.application.service import MultiService
from twisted.internet import reactor
from twisted.internet.defer import (
    Deferred,
    DeferredQueue,
    inlineCallbacks,
    succeed,
)
from twisted.internet.error import (
    ProcessDone,
    ProcessExitedAlready,
    ProcessTerminated,
)
from twisted.internet.task import Clock
from twisted.python import threadable
from twisted.python.failure import Failure

from maastesting.factory import factory
from maastesting.matchers import (
    DocTestMatches,
    HasLength,
    IsFiredDeferred,
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.tests.test_security import SharedSecretTestCase
from provisioningserver.utils import services
from provisioningserver.utils.beaconing import (
    BeaconPayload,
    create_beacon_payload,
    TopologyHint,
)
from provisioningserver.utils.services import (
    BeaconingService,
    BeaconingSocketProtocol,
    JSONPerLineProtocol,
    MDNSResolverService,
    NeighbourDiscoveryService,
    NetworksMonitoringLock,
    NetworksMonitoringService,
    ProcessProtocolService,
    ProtocolForObserveARP,
    ProtocolForObserveBeacons,
)


class StubNetworksMonitoringService(NetworksMonitoringService):
    """Concrete subclass for testing."""

    def __init__(
        self, enable_monitoring=False, enable_beaconing=False, *args, **kwargs
    ):
        super().__init__(
            *args,
            enable_monitoring=enable_monitoring,
            enable_beaconing=enable_beaconing,
            **kwargs
        )
        self.iterations = DeferredQueue()
        self.interfaces = []
        self.update_interface__calls = 0

    def getDiscoveryState(self):
        return {}

    def updateInterfaces(self):
        self.update_interface__calls += 1
        d = super().updateInterfaces()
        d.addBoth(self.iterations.put)
        return d

    def recordInterfaces(self, interfaces, hints=None):
        self.interfaces.append(interfaces)

    def reportNeighbours(self, neighbours):
        pass

    def reportMDNSEntries(self, neighbours):
        pass


class TestNetworksMonitoringService(MAASTestCase):
    """Tests of `NetworksMonitoringService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def setUp(self):
        super().setUp()
        self.patch(services, "get_all_interfaces_definition")

    def makeService(self, *args, **kwargs):
        service = StubNetworksMonitoringService(*args, **kwargs)
        self.addCleanup(service._releaseSoleResponsibility)
        return service

    def test_init(self):
        service = self.makeService()
        self.assertThat(service, IsInstance(MultiService))
        self.assertThat(
            service.interface_monitor.step, Equals(service.interval)
        )
        self.assertThat(
            service.interface_monitor.call,
            Equals((service.updateInterfaces, (), {})),
        )

    @inlineCallbacks
    def test_get_all_interfaces_definition_is_called_in_thread(self):
        service = self.makeService()
        self.patch(
            services, "get_all_interfaces_definition", threading.current_thread
        )
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
                services, "get_all_interfaces_definition"
            )
            get_interfaces.side_effect = Exception(error_message)
            yield service.updateInterfaces()
        self.assertThat(
            logger.output,
            DocTestMatches(
                "Failed to update and/or record network interface configuration"
                "..."
            ),
        )

    @inlineCallbacks
    def test_starting_service_triggers_interface_update(self):
        get_interfaces = self.patch(services, "get_all_interfaces_definition")
        get_interfaces.side_effect = [sentinel.config]
        clock = Clock()
        service = self.makeService(clock=clock)
        yield service.startService()
        self.assertThat(service.update_interface__calls, Equals(1))
        yield service.stopService()

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
        self.assertThat(
            service.interfaces, Equals([sentinel.config1, sentinel.config2])
        )

        self.assertThat(get_interfaces, MockCallsMatch(call(), call()))

    @inlineCallbacks
    def test_recordInterfaces_not_called_when_interfaces_not_changed(self):
        get_interfaces = self.patch(services, "get_all_interfaces_definition")
        # Configuration does NOT change between the first and second call.
        get_interfaces.side_effect = [{}, {}]

        service = self.makeService()
        self.assertThat(service.interfaces, HasLength(0))
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, Equals([{}]))
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, Equals([{}]))

        self.assertThat(get_interfaces, MockCallsMatch(call(), call()))

    @inlineCallbacks
    def test_recordInterfaces_called_after_failure(self):
        get_interfaces = self.patch(services, "get_all_interfaces_definition")
        get_interfaces.return_value = {}

        service = self.makeService()
        recordInterfaces = self.patch(service, "recordInterfaces")
        recordInterfaces.side_effect = [Exception, None, None]

        # Using the logger fixture prevents the test case from failing due
        # to the logged exception.
        with TwistedLoggerFixture():
            # recordInterfaces is called the first time, as expected.
            recordInterfaces.reset_mock()
            yield service.updateInterfaces()
            self.assertThat(recordInterfaces, MockCalledOnceWith({}, None))

            # recordInterfaces is called the second time too; the service noted
            # that it crashed last time and knew to run it again.
            recordInterfaces.reset_mock()
            yield service.updateInterfaces()
            self.assertThat(recordInterfaces, MockCalledOnceWith({}, None))

            # recordInterfaces is NOT called the third time; the service noted
            # that the configuration had not changed.
            recordInterfaces.reset_mock()
            yield service.updateInterfaces()
            self.assertThat(recordInterfaces, MockNotCalled())

    @inlineCallbacks
    def test_assumes_sole_responsibility_before_updating(self):
        # A filesystem lock is used to prevent multiple network monitors from
        # running on each host machine.
        service = self.makeService()

        # Not locked after instantiating the service.
        lock = service._lock
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
        lock = NetworksMonitoringLock()

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
        lock = NetworksMonitoringLock()

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
    def test_propagates_exit_errors(self):
        proto = JSONPerLineProtocol(callback=lambda json: None)
        reactor.spawnProcess(proto, b"false", (b"false",))
        with ExpectedException(ProcessTerminated, ".* exit code 1"):
            yield proto.done

    def test_parses_only_full_lines(self):
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

    def test_ignores_interspersed_zero_length_writes(self):
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

    def test_logs_non_json_output(self):
        callback = Mock()
        proto = JSONPerLineProtocol(callback=callback)
        proto.connectionMade()
        with TwistedLoggerFixture() as logger:
            proto.outReceived(b"{\n")
        self.assertThat(
            logger.output, DocTestMatches("Failed to parse JSON: ...")
        )

    def test_logs_stderr(self):
        message = factory.make_name("message")
        callback = Mock()
        proto = JSONPerLineProtocol(callback=callback)
        proto.connectionMade()
        with TwistedLoggerFixture() as logger:
            proto.errReceived((message + "\n").encode("ascii"))
        self.assertThat(logger.output, Equals(message))

    def test_logs_only_full_lines_from_stderr(self):
        message = factory.make_name("message")
        callback = Mock()
        proto = JSONPerLineProtocol(callback=callback)
        proto.connectionMade()
        with TwistedLoggerFixture() as logger:
            proto.errReceived(message.encode("ascii"))
        self.assertThat(logger.output, Equals(""))

    def test_logs_stderr_at_process_end(self):
        message = factory.make_name("message")
        callback = Mock()
        proto = JSONPerLineProtocol(callback=callback)
        proto.connectionMade()
        with TwistedLoggerFixture() as logger:
            proto.errReceived(message.encode("ascii"))
            self.assertThat(logger.output, Equals(""))
            proto.processEnded(Failure(ProcessDone(0)))
        self.assertThat(logger.output, Equals(message))

    @inlineCallbacks
    def test_propagates_errors_from_command(self):
        proto = JSONPerLineProtocol(callback=lambda obj: None)
        proto.connectionMade()
        reason = Failure(ProcessTerminated(1))
        proto.processEnded(reason)
        with ExpectedException(ProcessTerminated):
            yield proto.done


class TestProtocolForObserveARP(MAASTestCase):
    """Tests for `ProtocolForObserveARP`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_adds_interface(self):
        callback = Mock()
        ifname = factory.make_name("eth")
        proto = ProtocolForObserveARP(ifname, callback=callback)
        proto.makeConnection(Mock(pid=None))
        proto.outReceived(b"{}\n")
        self.expectThat(
            callback, MockCallsMatch(call([{"interface": ifname}]))
        )


class TestProtocolForObserveBeacons(MAASTestCase):
    """Tests for `ProtocolForObserveBeacons`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_adds_interface(self):
        callback = Mock()
        ifname = factory.make_name("eth")
        proto = ProtocolForObserveBeacons(ifname, callback=callback)
        proto.makeConnection(Mock(pid=None))
        proto.outReceived(b"{}\n")
        self.expectThat(
            callback, MockCallsMatch(call([{"interface": ifname}]))
        )


class MockProcessProtocolService(ProcessProtocolService):
    def __init__(self):
        super().__init__()
        self._callback = Mock()

    def getDescription(self):
        return self.__class__.__name__

    def createProcessProtocol(self):
        return JSONPerLineProtocol(callback=self._callback)


class TrueProcessProtocolService(MockProcessProtocolService):
    def getProcessParameters(self):
        return [b"/bin/true"]


class FalseProcessProtocolService(MockProcessProtocolService):
    def getProcessParameters(self):
        return [b"/bin/false"]


class SleepProcessProtocolService(MockProcessProtocolService):
    def getProcessParameters(self):
        return [b"/bin/sleep", b"7"]


class EchoProcessProtocolService(MockProcessProtocolService):
    def getProcessParameters(self):
        return [b"/bin/echo", b"{}\n"]


class MockJSONProtocol(JSONPerLineProtocol):
    pass


class TestProcessProtocolService(MAASTestCase):
    """Tests for `JSONPerLineProtocol`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=15)

    def setUp(self):
        super().setUp()
        # Alter timings of terminateProcess so we don't have to wait so long.
        self.patch(
            services,
            "terminateProcess",
            partial(services.terminateProcess, quit_after=0.2, kill_after=0.4),
        )

    def test_base_class_cannot_be_used(self):
        with ExpectedException(TypeError):
            ProcessProtocolService()

    @inlineCallbacks
    def test_starts_and_stops_process(self):
        service = SleepProcessProtocolService()
        with TwistedLoggerFixture() as logger:
            service.startService()
            self.assertThat(service._protocol.done, Not(IsFiredDeferred()))
            yield service.stopService()
            result = yield service._protocol.done
            self.assertThat(result, Is(None))
        self.assertThat(
            logger.output,
            DocTestMatches(
                "SleepProcessProtocolService started.\n"
                "-...-\n"
                "SleepProcessProtocolService ..."
            ),
        )
        with ExpectedException(ProcessExitedAlready):
            service._process.signalProcess("INT")

    @inlineCallbacks
    def test_handles_normal_process_exit(self):
        # If the spawned process exits with an exit code of zero this is
        # logged as "ended normally".
        service = TrueProcessProtocolService()
        with TwistedLoggerFixture() as logger:
            service.startService()
            yield service._protocol.done
            yield service.stopService()
        self.assertThat(
            logger.output,
            Equals(
                "TrueProcessProtocolService started.\n"
                "---\n"
                "TrueProcessProtocolService ended normally."
            ),
        )

    @inlineCallbacks
    def test_handles_terminated_process_exit(self):
        # During service stop the spawned process can be terminated with a
        # signal. This is logged with a slightly different error message.
        service = SleepProcessProtocolService()
        with TwistedLoggerFixture() as logger:
            service.startService()
            yield service.stopService()
        self.assertThat(
            logger.output,
            Equals(
                "SleepProcessProtocolService started.\n"
                "---\n"
                "SleepProcessProtocolService was terminated."
            ),
        )

    @inlineCallbacks
    def test_handles_abnormal_process_exit(self):
        # If the spawned process exits with a non-zero exit code this is
        # logged as "a probable error".
        service = FalseProcessProtocolService()
        with TwistedLoggerFixture() as logger:
            service.startService()
            result = yield service._protocol.done
            self.assertThat(result, Is(None))
            yield service.stopService()
        self.assertThat(
            logger.output,
            DocTestMatches(
                "FalseProcessProtocolService started.\n"
                "---\n"
                "FalseProcessProtocolService failed.\n"
                "Traceback (most recent call last):\n"
                "...: A process has ended with a probable error "
                "condition: process ended with exit code 1."
            ),
        )

    @inlineCallbacks
    def test_calls_protocol_callback(self):
        service = EchoProcessProtocolService()
        service.startService()
        # Wait for the protocol to finish. (the echo process will stop)
        result = yield service._protocol.done
        self.assertThat(service._callback, MockCalledOnceWith([{}]))
        yield service.stopService()
        self.assertThat(result, Is(None))


class TestNeighbourDiscoveryService(MAASTestCase):
    """Tests for `NeighbourDiscoveryService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_returns_expected_arguments(self):
        ifname = factory.make_name("eth")
        service = NeighbourDiscoveryService(ifname, Mock())
        args = service.getProcessParameters()
        self.assertThat(args, HasLength(3))
        self.assertTrue(args[0].endswith(b"maas-common"))
        self.assertTrue(args[1], Equals(b"observe-arp"))
        self.assertTrue(args[2], Equals(ifname.encode("utf-8")))

    @inlineCallbacks
    def test_restarts_process_after_finishing(self):
        ifname = factory.make_name("eth")
        service = NeighbourDiscoveryService(ifname, Mock())
        mock_process_params = self.patch(service, "getProcessParameters")
        mock_process_params.return_value = [b"/bin/echo", b"{}"]
        service.clock = Clock()
        service.startService()
        # Wait for the protocol to finish
        service.clock.advance(0.0)
        yield service._protocol.done
        # Advance the clock (should start the service again)
        interval = service.step
        service.clock.advance(interval)
        # The Deferred should have been recreated.
        self.assertThat(service._protocol.done, Not(IsFiredDeferred()))
        yield service._protocol.done
        service.stopService()

    @inlineCallbacks
    def test_protocol_logs_stderr(self):
        logger = self.useFixture(TwistedLoggerFixture())
        ifname = factory.make_name("eth")
        service = NeighbourDiscoveryService(ifname, lambda _: None)
        protocol = service.createProcessProtocol()
        reactor.spawnProcess(protocol, b"sh", (b"sh", b"-c", b"exec cat >&2"))
        protocol.transport.write(
            b"Lines written to stderr are logged\n"
            b"with a prefix, with no exceptions.\n"
        )
        protocol.transport.closeStdin()
        yield protocol.done
        self.assertThat(
            logger.output,
            Equals(
                "observe-arp[%s]: Lines written to stderr are logged\n"
                "---\n"
                "observe-arp[%s]: with a prefix, with no exceptions."
                % (ifname, ifname)
            ),
        )


class TestBeaconingService(MAASTestCase):
    """Tests for `BeaconingService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_returns_expected_arguments(self):
        ifname = factory.make_name("eth")
        service = BeaconingService(ifname, Mock())
        args = service.getProcessParameters()
        self.assertThat(args, HasLength(3))
        self.assertTrue(args[0].endswith(b"maas-common"))
        self.assertTrue(args[1], Equals(b"observe-beacons"))
        self.assertTrue(args[2], Equals(ifname.encode("utf-8")))

    @inlineCallbacks
    def test_restarts_process_after_finishing(self):
        ifname = factory.make_name("eth")
        service = BeaconingService(ifname, Mock())
        mock_process_params = self.patch(service, "getProcessParameters")
        mock_process_params.return_value = [b"/bin/echo", b"{}"]
        service.clock = Clock()
        service.startService()
        # Wait for the protocol to finish
        service.clock.advance(0.0)
        yield service._protocol.done
        # Advance the clock (should start the service again)
        interval = service.step
        service.clock.advance(interval)
        # The Deferred should have been recreated.
        self.assertThat(service._protocol.done, Not(IsFiredDeferred()))
        yield service._protocol.done
        service.stopService()

    @inlineCallbacks
    def test_protocol_logs_stderr(self):
        logger = self.useFixture(TwistedLoggerFixture())
        ifname = factory.make_name("eth")
        service = BeaconingService(ifname, lambda _: None)
        protocol = service.createProcessProtocol()
        reactor.spawnProcess(protocol, b"sh", (b"sh", b"-c", b"exec cat >&2"))
        protocol.transport.write(
            b"Lines written to stderr are logged\n"
            b"with a prefix, with no exceptions.\n"
        )
        protocol.transport.closeStdin()
        yield protocol.done
        self.assertThat(
            logger.output,
            Equals(
                "observe-beacons[%s]: Lines written to stderr are logged\n"
                "---\n"
                "observe-beacons[%s]: with a prefix, with no exceptions."
                % (ifname, ifname)
            ),
        )


class TestMDNSResolverService(MAASTestCase):
    """Tests for `MDNSResolverService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_returns_expected_arguments(self):
        service = MDNSResolverService(Mock())
        args = service.getProcessParameters()
        self.assertThat(args, HasLength(2))
        self.assertTrue(args[0].endswith(b"maas-common"))
        self.assertTrue(args[1], Equals(b"observe-mdns"))

    @inlineCallbacks
    def test_protocol_selectively_logs_stderr(self):
        logger = self.useFixture(TwistedLoggerFixture())
        service = MDNSResolverService(lambda _: None)
        protocol = service.createProcessProtocol()
        reactor.spawnProcess(protocol, b"sh", (b"sh", b"-c", b"exec cat >&2"))
        protocol.transport.write(
            b"Lines written to stderr are logged\n"
            b"with a prefix, with one exception:\n"
            b"Got SIGFAKE, quitting.\n"
        )
        protocol.transport.closeStdin()
        yield protocol.done
        self.assertThat(
            logger.output,
            Equals(
                "observe-mdns: Lines written to stderr are logged\n"
                "---\n"
                "observe-mdns: with a prefix, with one exception:"
            ),
        )


def wait_for_rx_packets(beacon_protocol, count, deferred=None):
    """Waits for a BeaconingSocketProtocol to transmit `count` packets."""
    if deferred is None:
        deferred = Deferred()
    if len(beacon_protocol.rx_queue) >= count:
        deferred.callback(None)
    else:
        reactor.callLater(
            0.001,
            wait_for_rx_packets,
            beacon_protocol,
            count,
            deferred=deferred,
        )
    return deferred


class FakeBeaconPayload(BeaconPayload):
    def __new__(
        cls,
        uuid,
        payload=None,
        ifname="eth0",
        mac=None,
        vid=None,
        version=1,
        beacon_type="solicitation",
    ):
        if payload is None:
            remote = {"name": ifname}
            if mac is not None:
                remote["mac_address"] = mac
            if vid is not None:
                remote["vid"] = vid
            payload = {"uuid": uuid, "remote": remote}
        return super().__new__(cls, b"", version, beacon_type, payload)


class TestBeaconingSocketProtocol(SharedSecretTestCase):
    """Tests for `BeaconingSocketProtocol`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=15)

    @inlineCallbacks
    def test_creates_listen_port_when_run_with_IReactorMulticast(self):
        # Note: Always use a random port for testing. (port=0)
        protocol = BeaconingSocketProtocol(reactor, port=0)
        self.assertThat(protocol.listen_port, Not(Is(None)))
        # This tests that the post gets closed properly; otherwise the test
        # suite will complain about things left in the reactor.
        yield protocol.stopProtocol()

    def test_skips_creating_listen_port_when_run_with_fake_reactor(self):
        # Note: Always use a random port for testing. (port=0)
        protocol = BeaconingSocketProtocol(Clock(), port=0)
        self.assertThat(protocol.listen_port, Is(None))
        # No listen port, so stopProtocol() shouldn't return a Deferred.
        result = protocol.stopProtocol()
        self.assertThat(result, Is(None))

    @inlineCallbacks
    def test_sends_and_receives_unicast_beacons(self):
        # Note: Always use a random port for testing. (port=0)
        logger = self.useFixture(TwistedLoggerFixture())
        protocol = BeaconingSocketProtocol(
            reactor,
            port=0,
            process_incoming=True,
            loopback=True,
            interface="::",
            debug=True,
        )
        self.assertThat(protocol.listen_port, Not(Is(None)))
        listen_port = protocol.listen_port._realPortNumber
        self.write_secret()
        beacon = create_beacon_payload("solicitation", {})
        rx_uuid = beacon.payload["uuid"]
        destination = random.choice(["::ffff:127.0.0.1", "::1"])
        protocol.send_beacon(beacon, (destination, listen_port))
        # Pretend we didn't send this packet. Otherwise we won't reply to it.
        # We have to do this now, before the reactor runs again.
        transmitted = protocol.tx_queue.pop(rx_uuid, None)
        # Since we've instructed the protocol to loop back packets for testing,
        # it should have sent a multicast solicitation, received it back, sent
        # an advertisement, then received it back. So we'll wait for two
        # packets to be sent.
        yield wait_for_rx_packets(protocol, 2)
        # Grab the beacon we know we transmitted and then received.
        received = protocol.rx_queue.pop(rx_uuid, None)
        self.assertThat(transmitted, Equals(beacon))
        self.assertThat(received[0].json["payload"]["uuid"], Equals(rx_uuid))
        # Grab the subsequent packets from the queues.
        transmitted = protocol.tx_queue.popitem()[1]
        received = protocol.rx_queue.popitem()[1]
        # We should have received a second packet to ack the first beacon.
        self.assertThat(received[0].json["payload"]["acks"], Equals(rx_uuid))
        # We should have transmitted an advertisement in response to the
        # solicitation.
        self.assertThat(transmitted.type, Equals("advertisement"))
        # This tests that the post gets closed properly; otherwise the test
        # suite will complain about things left in the reactor.
        yield protocol.stopProtocol()
        # In debug mode, the logger should have printed each packet.
        self.assertThat(
            logger.output,
            DocTestMatches("...Beacon received:...Own beacon received:..."),
        )

    @inlineCallbacks
    def test_send_multicast_beacon_sets_ipv4_source(self):
        # Note: Always use a random port for testing. (port=0)
        protocol = BeaconingSocketProtocol(
            reactor,
            port=0,
            process_incoming=True,
            loopback=True,
            interface="::",
            debug=False,
        )
        self.assertThat(protocol.listen_port, Not(Is(None)))
        listen_port = protocol.listen_port._realPortNumber
        self.write_secret()
        beacon = create_beacon_payload("advertisement", {})
        protocol.send_multicast_beacon("127.0.0.1", beacon, port=listen_port)
        # Verify that we received the packet.
        yield wait_for_rx_packets(protocol, 1)
        yield protocol.stopProtocol()

    @inlineCallbacks
    def test_send_multicast_beacon_sets_ipv6_source(self):
        # Due to issues beyond my control, this test doesn't do what I expected
        # it to do. But it's still useful for code coverage (to make sure no
        # blatant exceptions occur in the IPv6 path).
        # self.skipTest(
        #    "IPv6 loopback multicast isn't working, for whatever reason.")
        # Since we can't test IPv6 multicast on the loopback interface, another
        # method can be used to verify that it's working:
        # (1) sudo tcpdump -i <physical-interface> 'udp and port == 5240'
        # (2) bin/maas-rack send-beacons -p 5240
        # Verifying IPv6 (and IPv4) multicast group join behavior can be
        # validated by doing something like:
        # (1) bin/maas-rack send-beacons -t 600
        #     (the high timeout will cause it to wait for 10 minutes)
        # (2) ip maddr show | egrep 'ff02::15a|224.0.0.118|$'
        # The expected result from command (2) will be that 'egrep' will
        # highlight the MAAS multicast groups in red text. Any Ethernet
        # interface with an assigned IPv4 address should have joined the
        # 224.0.0.118 group. All Ethernet interfaces should have joined the
        # 'ff02::15a' group.
        # Note: Always use a random port for testing. (port=0)
        protocol = BeaconingSocketProtocol(
            reactor,
            port=0,
            process_incoming=True,
            loopback=True,
            interface="::",
            debug=False,
        )
        self.assertThat(protocol.listen_port, Not(Is(None)))
        listen_port = protocol.listen_port._realPortNumber
        self.write_secret()
        beacon = create_beacon_payload("advertisement", {})
        # The loopback interface ifindex should always be 1; this is saying
        # to send an IPv6 multicast on ifIndex == 1.
        protocol.send_multicast_beacon(1, beacon, port=listen_port)
        # Instead of skipping the test, just don't expect to receive anything.
        # yield wait_for_rx_packets(protocol, 1)
        yield protocol.stopProtocol()

    @inlineCallbacks
    def test_hints_for_own_beacon_received_on_another_interface(self):
        # Note: Always use a random port for testing. (port=0)
        protocol = BeaconingSocketProtocol(
            reactor,
            port=0,
            process_incoming=False,
            loopback=True,
            interface="::",
            debug=True,
        )
        # Need to generate a real UUID with the current time, so it doesn't
        # get aged out.
        uuid = str(uuid1())
        # Make the protocol think we sent a beacon with this UUID already.
        fake_tx_beacon = FakeBeaconPayload(uuid, ifname="eth0")
        protocol.tx_queue[uuid] = fake_tx_beacon
        fake_rx_beacon = {
            "source_ip": "127.0.0.1",
            "source_port": 5240,
            "destination_ip": "224.0.0.118",
            # Note the different receive interface.
            "interface": "eth1",
            "type": "solicitation",
            "payload": fake_tx_beacon.payload,
        }
        protocol.beaconReceived(fake_rx_beacon)
        # Should only have created one hint.
        hint = protocol.topology_hints[uuid].pop()
        self.assertThat(hint.hint, Equals("rx_own_beacon_on_other_interface"))
        yield protocol.stopProtocol()

    @inlineCallbacks
    def test_hints_for_own_beacon_received_on_same_interface(self):
        # Note: Always use a random port for testing. (port=0)
        protocol = BeaconingSocketProtocol(
            reactor,
            port=0,
            process_incoming=False,
            loopback=True,
            interface="::",
            debug=True,
        )
        # Need to generate a real UUID with the current time, so it doesn't
        # get aged out.
        uuid = str(uuid1())
        # Make the protocol think we sent a beacon with this UUID already.
        fake_tx_beacon = FakeBeaconPayload(uuid, ifname="eth0")
        protocol.tx_queue[uuid] = fake_tx_beacon
        fake_rx_beacon = {
            "source_ip": "127.0.0.1",
            "source_port": 5240,
            "destination_ip": "224.0.0.118",
            "interface": "eth0",
            "type": "solicitation",
            "payload": fake_tx_beacon.payload,
        }
        protocol.beaconReceived(fake_rx_beacon)
        # Should only have created one hint.
        hint = protocol.topology_hints[uuid].pop()
        self.assertThat(hint.hint, Equals("rx_own_beacon_on_tx_interface"))
        yield protocol.stopProtocol()

    @inlineCallbacks
    def test_hints_for_same_beacon_seen_on_multiple_interfaces(self):
        # Note: Always use a random port for testing. (port=0)
        protocol = BeaconingSocketProtocol(
            reactor,
            port=0,
            process_incoming=False,
            loopback=True,
            interface="::",
            debug=True,
        )
        # Don't try to send out any replies.
        self.patch(services, "create_beacon_payload")
        self.patch(protocol, "send_beacon")
        # Need to generate a real UUID with the current time, so it doesn't
        # get aged out.
        uuid = str(uuid1())
        # Make the protocol think we sent a beacon with this UUID already.
        fake_tx_beacon = FakeBeaconPayload(uuid, ifname="eth0")
        fake_rx_beacon_eth0 = {
            "source_ip": "127.0.0.1",
            "source_port": 5240,
            "destination_ip": "224.0.0.118",
            "interface": "eth0",
            "type": "solicitation",
            "payload": fake_tx_beacon.payload,
        }
        fake_rx_beacon_eth1 = {
            "source_ip": "127.0.0.1",
            "source_port": 5240,
            "destination_ip": "224.0.0.118",
            "interface": "eth1",
            "vid": 100,
            "type": "solicitation",
            "payload": fake_tx_beacon.payload,
        }
        protocol.beaconReceived(fake_rx_beacon_eth0)
        protocol.beaconReceived(fake_rx_beacon_eth1)
        hints = protocol.topology_hints[uuid]
        expected_hints = {
            TopologyHint(
                ifname="eth0",
                vid=None,
                hint="same_local_fabric_as",
                related_ifname="eth1",
                related_vid=100,
                related_mac=None,
            ),
            TopologyHint(
                ifname="eth1",
                vid=100,
                hint="same_local_fabric_as",
                related_ifname="eth0",
                related_vid=None,
                related_mac=None,
            ),
        }
        self.assertThat(hints, Equals(expected_hints))
        yield protocol.stopProtocol()

    @inlineCallbacks
    def test_hints_for_remote_unicast(self):
        # Note: Always use a random port for testing. (port=0)
        protocol = BeaconingSocketProtocol(
            reactor,
            port=0,
            process_incoming=False,
            loopback=True,
            interface="::",
            debug=True,
        )
        # Don't try to send out any replies.
        self.patch(services, "create_beacon_payload")
        self.patch(protocol, "send_beacon")
        # Need to generate a real UUID with the current time, so it doesn't
        # get aged out.
        uuid = str(uuid1())
        # Make the protocol think we sent a beacon with this UUID already.
        tx_mac = factory.make_mac_address()
        fake_tx_beacon = FakeBeaconPayload(
            uuid, ifname="eth1", mac=tx_mac, vid=100
        )
        fake_rx_beacon = {
            "source_ip": "127.0.0.1",
            "source_port": 5240,
            "destination_ip": "127.0.0.1",
            "interface": "eth0",
            "type": "solicitation",
            "payload": fake_tx_beacon.payload,
        }
        protocol.beaconReceived(fake_rx_beacon)
        hints = protocol.topology_hints[uuid]
        expected_hints = {
            TopologyHint(
                ifname="eth0",
                vid=None,
                hint="routable_to",
                related_ifname="eth1",
                related_vid=100,
                related_mac=tx_mac,
            )
        }
        self.assertThat(hints, Equals(expected_hints))
        yield protocol.stopProtocol()

    @inlineCallbacks
    def test_hints_for_remote_multicast(self):
        # Note: Always use a random port for testing. (port=0)
        protocol = BeaconingSocketProtocol(
            reactor,
            port=0,
            process_incoming=False,
            loopback=True,
            interface="::",
            debug=True,
        )
        # Don't try to send out any replies.
        self.patch(services, "create_beacon_payload")
        self.patch(protocol, "send_beacon")
        # Need to generate a real UUID with the current time, so it doesn't
        # get aged out.
        uuid = str(uuid1())
        # Make the protocol think we sent a beacon with this UUID already.
        tx_mac = factory.make_mac_address()
        fake_tx_beacon = FakeBeaconPayload(
            uuid, ifname="eth1", mac=tx_mac, vid=100
        )
        fake_rx_beacon = {
            "source_ip": "127.0.0.1",
            "source_port": 5240,
            "destination_ip": "224.0.0.118",
            "interface": "eth0",
            "vid": 200,
            "type": "solicitation",
            "payload": fake_tx_beacon.payload,
        }
        protocol.beaconReceived(fake_rx_beacon)
        hints = protocol.topology_hints[uuid]
        expected_hints = {
            TopologyHint(
                ifname="eth0",
                vid=200,
                hint="on_remote_network",
                related_ifname="eth1",
                related_vid=100,
                related_mac=tx_mac,
            )
        }
        self.assertThat(hints, Equals(expected_hints))
        yield protocol.stopProtocol()

    @inlineCallbacks
    def test_getJSONTopologyHints_converts_hints_to_dictionary(self):
        # Note: Always use a random port for testing. (port=0)
        protocol = BeaconingSocketProtocol(
            reactor,
            port=0,
            process_incoming=False,
            loopback=True,
            interface="::",
            debug=True,
        )
        # Don't try to send out any replies.
        self.patch(services, "create_beacon_payload")
        self.patch(protocol, "send_beacon")
        # Need to generate a real UUID with the current time, so it doesn't
        # get aged out.
        uuid = str(uuid1())
        # Make the protocol think we sent a beacon with this UUID already.
        tx_mac = factory.make_mac_address()
        fake_tx_beacon = FakeBeaconPayload(
            uuid, ifname="eth1", mac=tx_mac, vid=100
        )
        fake_rx_beacon = {
            "source_ip": "127.0.0.1",
            "source_port": 5240,
            "destination_ip": "224.0.0.118",
            "interface": "eth0",
            "type": "solicitation",
            "payload": fake_tx_beacon.payload,
        }
        protocol.beaconReceived(fake_rx_beacon)
        all_hints = protocol.getJSONTopologyHints()
        expected_hints = [
            # Note: since vid=None on the received beacon, we expect that
            # the hint won't have a 'vid' field.
            dict(
                ifname="eth0",
                hint="on_remote_network",
                related_ifname="eth1",
                related_vid=100,
                related_mac=tx_mac,
            )
        ]
        self.assertThat(all_hints, Equals(expected_hints))
        yield protocol.stopProtocol()

    @inlineCallbacks
    def test_queues_multicast_beacon_soliciations_upon_request(self):
        # Note: Always use a random port for testing. (port=0)
        clock = Clock()
        protocol = BeaconingSocketProtocol(
            clock,
            port=0,
            process_incoming=False,
            loopback=True,
            interface="::",
            debug=True,
        )
        # Don't try to send out any replies.
        self.patch(services, "create_beacon_payload")
        send_mcast_mock = self.patch(protocol, "send_multicast_beacons")
        self.patch(protocol, "send_beacon")
        yield protocol.queueMulticastBeaconing(solicitation=True)
        clock.advance(0)
        self.assertThat(
            send_mcast_mock, MockCalledOnceWith({}, "solicitation")
        )

    @inlineCallbacks
    def test_multicasts_at_most_once_per_five_seconds(self):
        # Note: Always use a random port for testing. (port=0)
        clock = Clock()
        protocol = BeaconingSocketProtocol(
            clock,
            port=0,
            process_incoming=False,
            loopback=True,
            interface="::",
            debug=True,
        )
        # Don't try to send out any replies.
        self.patch(services, "create_beacon_payload")
        monotonic_mock = self.patch(services.time, "monotonic")
        send_mcast_mock = self.patch(protocol, "send_multicast_beacons")
        self.patch(protocol, "send_beacon")
        monotonic_mock.side_effect = [
            # Initial queue
            6,
            # Initial dequeue
            6,
            # Second queue (hasn't yet been 5 seconds)
            10,
            # Third queue
            11,
            # Second dequeue
            11,
        ]
        yield protocol.queueMulticastBeaconing()
        clock.advance(0)
        self.assertThat(
            send_mcast_mock, MockCalledOnceWith({}, "advertisement")
        )
        send_mcast_mock.reset_mock()
        yield protocol.queueMulticastBeaconing()
        yield protocol.queueMulticastBeaconing(solicitation=True)
        clock.advance(4.9)
        self.assertThat(send_mcast_mock, MockNotCalled())
        clock.advance(0.1)
        self.assertThat(
            send_mcast_mock, MockCalledOnceWith({}, "solicitation")
        )

    @inlineCallbacks
    def test_multiple_beacon_requests_coalesced(self):
        # Note: Always use a random port for testing. (port=0)
        clock = Clock()
        protocol = BeaconingSocketProtocol(
            clock,
            port=0,
            process_incoming=False,
            loopback=True,
            interface="::",
            debug=True,
        )
        # Don't try to send out any replies.
        self.patch(services, "create_beacon_payload")
        send_mcast_mock = self.patch(protocol, "send_multicast_beacons")
        self.patch(protocol, "send_beacon")
        yield protocol.queueMulticastBeaconing()
        yield protocol.queueMulticastBeaconing()
        clock.advance(5)
        self.assertThat(
            send_mcast_mock, MockCalledOnceWith({}, "advertisement")
        )

    @inlineCallbacks
    def test_solicitation_wins_when_multiple_requests_queued(self):
        # Note: Always use a random port for testing. (port=0)
        clock = Clock()
        protocol = BeaconingSocketProtocol(
            clock,
            port=0,
            process_incoming=False,
            loopback=True,
            interface="::",
            debug=True,
        )
        # Don't try to send out any replies.
        self.patch(services, "create_beacon_payload")
        send_mcast_mock = self.patch(protocol, "send_multicast_beacons")
        self.patch(protocol, "send_beacon")
        yield protocol.queueMulticastBeaconing()
        yield protocol.queueMulticastBeaconing(solicitation=True)
        clock.advance(5)
        self.assertThat(
            send_mcast_mock, MockCalledOnceWith({}, "solicitation")
        )

    def test_send_multicast_beacons(self):
        interfaces = {
            "eth0": {"enabled": True, "links": []},
            "eth1": {"enabled": True, "links": []},
            "eth2": {"enabled": True, "links": []},
        }
        self.patch(socket, "if_nametoindex", lambda name: int(name[3:]))
        protocol = BeaconingSocketProtocol(
            Clock(),
            port=0,
            process_incoming=False,
            loopback=True,
            interface="::",
            debug=True,
        )
        self.patch(services, "create_beacon_payload")
        send_mcast_mock = self.patch(protocol, "send_multicast_beacon")
        protocol.send_multicast_beacons(interfaces)
        # beaconing is sent for each interface ID
        self.assertEqual(
            send_mcast_mock.mock_calls,
            [call(0, ANY), call(1, ANY), call(2, ANY)],
        )
