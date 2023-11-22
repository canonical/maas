# Copyright 2014-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the region's RPC implementation."""


from collections import defaultdict
from operator import attrgetter
import random
from unittest import skip
from unittest.mock import ANY, call, MagicMock, Mock, sentinel

from django.db import IntegrityError
from testtools import ExpectedException
from testtools.deferredruntest import assert_fails_with
from testtools.matchers import (
    AfterPreprocessing,
    AllMatch,
    Equals,
    HasLength,
    Is,
    IsInstance,
    MatchesAll,
    MatchesAny,
    MatchesListwise,
    MatchesSetwise,
)
from twisted.application.service import Service
from twisted.internet import reactor, tcp
from twisted.internet.address import IPv4Address
from twisted.internet.defer import (
    CancelledError,
    Deferred,
    DeferredList,
    fail,
    inlineCallbacks,
    succeed,
)
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.error import ConnectionClosed
from twisted.internet.interfaces import IStreamServerEndpoint
from twisted.internet.protocol import Factory
from twisted.protocols import amp
from twisted.python.failure import Failure
from twisted.python.reflect import fullyQualifiedName
from zope.interface.verify import verifyObject

from maasserver.models import RackController, RegionController
from maasserver.rpc import regionservice
from maasserver.rpc.regionservice import (
    RackClient,
    Region,
    RegionServer,
    RegionService,
)
from maasserver.rpc.testing.doubles import HandshakingRegionServer
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from maastesting.matchers import MockCalledOnceWith, MockCallsMatch, Provides
from maastesting.testcase import MAASTestCase
from maastesting.twisted import (
    always_fail_with,
    always_succeed_with,
    extract_result,
    TwistedLoggerFixture,
)
from metadataserver.builtin_scripts import load_builtin_scripts
from provisioningserver.prometheus.metrics import PROMETHEUS_METRICS
from provisioningserver.rpc import cluster, exceptions
from provisioningserver.rpc.exceptions import (
    CannotRegisterRackController,
    NoConnectionsAvailable,
)
from provisioningserver.rpc.interfaces import IConnection
from provisioningserver.rpc.region import RegisterRackController
from provisioningserver.rpc.testing import call_responder
from provisioningserver.rpc.testing.doubles import DummyConnection
from provisioningserver.utils import events
from provisioningserver.utils.version import get_running_version

wait_for_reactor = wait_for()


class TestRegionServer(MAASTransactionServerTestCase):
    def setUp(self):
        super().setUp()
        load_builtin_scripts()

    def test_interfaces(self):
        protocol = RegionServer()
        # transport.getHandle() is used by AMP._getPeerCertificate, which we
        # call indirectly via the peerCertificate attribute in IConnection.
        self.patch(protocol, "transport")
        verifyObject(IConnection, protocol)

    def test_connectionMade_does_not_update_services_connection_set(self):
        service = RegionService(sentinel.ipcWorker)
        service.running = True  # Pretend it's running.
        service.factory.protocol = HandshakingRegionServer
        protocol = service.factory.buildProtocol(addr=None)  # addr is unused.
        self.assertDictEqual({}, service.connections)
        protocol.connectionMade()
        self.assertDictEqual({}, service.connections)

    def test_connectionMade_drops_connection_if_service_not_running(self):
        service = RegionService(sentinel.ipcWorker)
        service.running = False  # Pretend it's not running.
        service.factory.protocol = HandshakingRegionServer
        protocol = service.factory.buildProtocol(addr=None)  # addr is unused.
        transport = self.patch(protocol, "transport")
        self.assertDictEqual({}, service.connections)
        protocol.connectionMade()
        # The protocol is not added to the connection set.
        self.assertDictEqual({}, service.connections)
        # The transport is instructed to lose the connection.
        self.assertThat(transport.loseConnection, MockCalledOnceWith())

    def test_connectionLost_updates_services_connection_set(self):
        service = RegionService(sentinel.ipcWorker)
        service.running = True  # Pretend it's running.
        service.factory.protocol = HandshakingRegionServer
        protocol = service.factory.buildProtocol(addr=None)  # addr is unused.
        protocol.ident = factory.make_name("node")
        connectionLost_up_call = self.patch(amp.AMP, "connectionLost")
        service.connections[protocol.ident] = {protocol}

        protocol.connectionLost(reason=None)
        # The connection is removed from the set, but the key remains.
        self.assertDictEqual({protocol.ident: set()}, service.connections)
        # connectionLost() is called on the superclass.
        self.assertThat(connectionLost_up_call, MockCalledOnceWith(None))

    def test_connectionLost_uses_ipcWorker_to_unregister(self):
        ipcWorker = MagicMock()
        service = RegionService(ipcWorker)
        service.running = True  # Pretend it's running.
        service.factory.protocol = HandshakingRegionServer
        protocol = service.factory.buildProtocol(addr=None)  # addr is unused.
        protocol.ident = factory.make_name("node")
        protocol.host = Mock()
        protocol.host.host = sentinel.host
        protocol.host.port = sentinel.port
        protocol.hostIsRemote = True
        connectionLost_up_call = self.patch(amp.AMP, "connectionLost")
        service.connections[protocol.ident] = {protocol}

        protocol.connectionLost(reason=None)
        self.assertThat(
            ipcWorker.rpcUnregisterConnection,
            MockCalledOnceWith(protocol.connid),
        )
        # The connection is removed from the set, but the key remains.
        self.assertDictEqual({protocol.ident: set()}, service.connections)
        # connectionLost() is called on the superclass.
        self.assertThat(connectionLost_up_call, MockCalledOnceWith(None))

    def patch_authenticate_for_failure(self, client):
        authenticate = self.patch_autospec(client, "authenticateCluster")
        authenticate.side_effect = always_succeed_with(False)

    def patch_authenticate_for_error(self, client, exception):
        authenticate = self.patch_autospec(client, "authenticateCluster")
        authenticate.side_effect = always_fail_with(exception)

    def test_connectionMade_drops_connections_if_authentication_fails(self):
        service = RegionService(sentinel.ipcWorker)
        service.running = True  # Pretend it's running.
        service.factory.protocol = HandshakingRegionServer
        protocol = service.factory.buildProtocol(addr=None)  # addr is unused.
        self.patch_authenticate_for_failure(protocol)
        transport = self.patch(protocol, "transport")
        self.assertDictEqual({}, service.connections)
        protocol.connectionMade()
        # The protocol is not added to the connection set.
        self.assertDictEqual({}, service.connections)
        # The transport is instructed to lose the connection.
        self.assertThat(transport.loseConnection, MockCalledOnceWith())

    def test_connectionMade_drops_connections_if_authentication_errors(self):
        logger = self.useFixture(TwistedLoggerFixture())

        service = RegionService(sentinel.ipcWorker)
        service.running = True  # Pretend it's running.
        service.factory.protocol = HandshakingRegionServer
        protocol = service.factory.buildProtocol(addr=None)  # addr is unused.
        protocol.transport = MagicMock()
        exception_type = factory.make_exception_type()
        self.patch_authenticate_for_error(protocol, exception_type())
        self.assertDictEqual({}, service.connections)

        connectionMade = wait_for_reactor(protocol.connectionMade)
        connectionMade()

        # The protocol is not added to the connection set.
        self.assertDictEqual({}, service.connections)
        # The transport is instructed to lose the connection.
        self.assertThat(
            protocol.transport.loseConnection, MockCalledOnceWith()
        )

        # The log was written to.
        self.assertDocTestMatches(
            """\
            Rack controller '...' could not be authenticated; dropping
            connection. Check that /var/lib/maas/secret...""",
            logger.dump(),
        )

    def test_handshakeFailed_does_not_log_when_connection_is_closed(self):
        server = RegionServer()
        with TwistedLoggerFixture() as logger:
            server.handshakeFailed(Failure(ConnectionClosed()))
        # Nothing was logged.
        self.assertEqual("", logger.output)

    def make_handshaking_server(self):
        service = RegionService(sentinel.ipcWorker)
        service.running = True  # Pretend it's running.
        service.factory.protocol = HandshakingRegionServer
        return service.factory.buildProtocol(addr=None)  # addr is unused.

    def make_running_server(self):
        service = RegionService(sentinel.ipcWorker)
        service.running = True  # Pretend it's running.
        # service.factory.protocol = RegionServer
        return service.factory.buildProtocol(addr=None)  # addr is unused.

    def test_authenticateCluster_accepts_matching_digests(self):
        server = self.make_running_server()

        def calculate_digest(_, message):
            # Use the region's own authentication responder.
            return Region().authenticate(message)

        callRemote = self.patch_autospec(server, "callRemote")
        callRemote.side_effect = calculate_digest

        d = server.authenticateCluster()
        self.assertTrue(extract_result(d))

    def test_authenticateCluster_rejects_non_matching_digests(self):
        server = self.make_running_server()

        def calculate_digest(_, message):
            # Return some nonsense.
            response = {
                "digest": factory.make_bytes(),
                "salt": factory.make_bytes(),
            }
            return succeed(response)

        callRemote = self.patch_autospec(server, "callRemote")
        callRemote.side_effect = calculate_digest

        d = server.authenticateCluster()
        self.assertFalse(extract_result(d))

    def test_authenticateCluster_propagates_errors(self):
        server = self.make_running_server()
        exception_type = factory.make_exception_type()

        callRemote = self.patch_autospec(server, "callRemote")
        callRemote.return_value = fail(exception_type())

        d = server.authenticateCluster()
        self.assertRaises(exception_type, extract_result, d)

    def make_Region(self, ipcWorker=None):
        if ipcWorker is None:
            ipcWorker = sentinel.ipcWorker
        patched_region = RegionServer()
        patched_region.factory = Factory.forProtocol(RegionServer)
        patched_region.factory.service = RegionService(ipcWorker)
        return patched_region

    def test_register_is_registered(self):
        protocol = RegionServer()
        responder = protocol.locateResponder(
            RegisterRackController.commandName
        )
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def installFakeRegion(self):
        region = yield deferToDatabase(
            transactional(factory.make_RegionController)
        )
        self.patch(
            RegionController.objects, "get_running_controller"
        ).return_value = region

    @wait_for_reactor
    @inlineCallbacks
    def test_register_returns_system_id_and_uuid(self):
        uuid = "a-b-c"
        self.patch(regionservice, "GLOBAL_LABELS", {"maas_uuid": uuid})

        yield self.installFakeRegion()
        rack_controller = yield deferToDatabase(factory.make_RackController)
        protocol = self.make_Region()
        protocol.transport = MagicMock()
        response = yield call_responder(
            protocol,
            RegisterRackController,
            {
                "system_id": rack_controller.system_id,
                "hostname": rack_controller.hostname,
                "interfaces": {},
            },
        )
        self.assertEqual(rack_controller.system_id, response["system_id"])
        self.assertEqual(uuid, response["uuid"])

    @wait_for_reactor
    @inlineCallbacks
    def test_register_acks_beacon_support(self):
        yield self.installFakeRegion()
        rack_controller = yield deferToDatabase(factory.make_RackController)
        protocol = self.make_Region()
        protocol.transport = MagicMock()
        response = yield call_responder(
            protocol,
            RegisterRackController,
            {
                "system_id": rack_controller.system_id,
                "hostname": rack_controller.hostname,
                "interfaces": {},
                "beacon_support": True,
            },
        )
        self.assertTrue(response["beacon_support"])

    @wait_for_reactor
    @inlineCallbacks
    def test_register_acks_version(self):
        yield self.installFakeRegion()
        rack_controller = yield deferToDatabase(factory.make_RackController)
        protocol = self.make_Region()
        protocol.transport = MagicMock()
        response = yield call_responder(
            protocol,
            RegisterRackController,
            {
                "system_id": rack_controller.system_id,
                "hostname": rack_controller.hostname,
                "interfaces": {},
                "version": "2.3.0",
            },
        )
        self.assertEqual(response["version"], str(get_running_version()))

    @wait_for_reactor
    @inlineCallbacks
    def test_register_sets_ident(self):
        yield self.installFakeRegion()
        rack_controller = yield deferToDatabase(factory.make_RackController)
        protocol = self.make_Region()
        protocol.transport = MagicMock()
        yield call_responder(
            protocol,
            RegisterRackController,
            {
                "system_id": rack_controller.system_id,
                "hostname": rack_controller.hostname,
                "interfaces": {},
            },
        )
        self.assertEqual(rack_controller.system_id, protocol.ident)

    @wait_for_reactor
    @inlineCallbacks
    def test_register_calls_addConnectionFor(self):
        yield self.installFakeRegion()
        rack_controller = yield deferToDatabase(factory.make_RackController)
        protocol = self.make_Region()
        protocol.transport = MagicMock()
        mock_addConnectionFor = self.patch(
            protocol.factory.service, "_addConnectionFor"
        )
        yield call_responder(
            protocol,
            RegisterRackController,
            {
                "system_id": rack_controller.system_id,
                "hostname": rack_controller.hostname,
                "interfaces": {},
            },
        )
        self.assertThat(
            mock_addConnectionFor,
            MockCalledOnceWith(rack_controller.system_id, protocol),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_register_sets_hosts(self):
        yield self.installFakeRegion()
        rack_controller = yield deferToDatabase(factory.make_RackController)
        protocol = self.make_Region()
        protocol.transport = MagicMock()
        protocol.transport.getHost.return_value = sentinel.host
        yield call_responder(
            protocol,
            RegisterRackController,
            {
                "system_id": rack_controller.system_id,
                "hostname": rack_controller.hostname,
                "interfaces": {},
            },
        )
        self.assertEqual(sentinel.host, protocol.host)

    @wait_for_reactor
    @inlineCallbacks
    def test_register_sets_hostIsRemote_calls_rpcRegisterConnection(self):
        yield self.installFakeRegion()
        rack_controller = yield deferToDatabase(factory.make_RackController)
        ipcWorker = MagicMock()
        protocol = self.make_Region(ipcWorker)
        protocol.transport = MagicMock()
        host = IPv4Address(
            type="TCP",
            host=factory.make_ipv4_address(),
            port=random.randint(1, 400),
        )
        protocol.transport.getHost.return_value = host
        mock_deferToDatabase = self.patch(regionservice, "deferToDatabase")
        mock_deferToDatabase.side_effect = [succeed(rack_controller)]
        yield call_responder(
            protocol,
            RegisterRackController,
            {
                "system_id": rack_controller.system_id,
                "hostname": rack_controller.hostname,
                "interfaces": {},
            },
        )
        self.assertTrue(sentinel.host, protocol.hostIsRemote)
        self.assertThat(
            ipcWorker.rpcRegisterConnection,
            MockCalledOnceWith(
                protocol.connid, protocol.ident, host.host, host.port
            ),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_register_creates_new_rack(self):
        yield self.installFakeRegion()
        protocol = self.make_Region()
        protocol.transport = MagicMock()
        hostname = factory.make_hostname()
        yield call_responder(
            protocol,
            RegisterRackController,
            {"system_id": None, "hostname": hostname, "interfaces": {}},
        )
        yield deferToDatabase(RackController.objects.get, hostname=hostname)

    @wait_for_reactor
    @inlineCallbacks
    def test_register_raises_CannotRegisterRackController_when_it_cant(self):
        yield self.installFakeRegion()
        patched_create = self.patch(RackController.objects, "create")
        patched_create.side_effect = IntegrityError()
        hostname = factory.make_name("hostname")
        error = yield assert_fails_with(
            call_responder(
                self.make_Region(),
                RegisterRackController,
                {"system_id": None, "hostname": hostname, "interfaces": {}},
            ),
            CannotRegisterRackController,
        )
        self.assertEqual(
            (
                "Failed to register rack controller 'None' with the master. "
                "Connection will be dropped.",
            ),
            error.args,
        )


class TestRackClient(MAASTestCase):
    def test_defined_cache_calls(self):
        self.assertEqual(
            [cluster.DescribePowerTypes],
            RackClient.cache_calls,
        )

    def test_getCallCache_adds_new_call_cache(self):
        conn = DummyConnection()
        cache = {}
        client = RackClient(conn, cache)
        call_cache = client._getCallCache()
        self.assertIs(call_cache, cache["call_cache"])

    def test_getCallCache_returns_existing(self):
        conn = DummyConnection()
        cache = {}
        client = RackClient(conn, cache)
        call_cache = client._getCallCache()
        call_cache2 = client._getCallCache()
        self.assertIs(call_cache, cache["call_cache"])
        self.assertIs(call_cache2, cache["call_cache"])
        self.assertIs(call_cache2, call_cache)

    @wait_for_reactor
    @inlineCallbacks
    def test_call__returns_cache_value(self):
        conn = DummyConnection()
        conn.ident = factory.make_name("ident")
        client = RackClient(conn, {})
        call_cache = client._getCallCache()
        power_types = {"power_types": [{"name": "ipmi"}, {"name": "wedge"}]}
        call_cache[cluster.DescribePowerTypes] = power_types
        result = yield client(cluster.DescribePowerTypes)
        # The result is a copy. It should equal the result but not be
        # the same object.
        self.assertEqual(power_types, result)
        self.assertIsNot(power_types, result)

    @wait_for_reactor
    @inlineCallbacks
    def test_call__adds_result_to_cache(self):
        conn = DummyConnection()
        conn.ident = factory.make_name("ident")
        self.patch(conn, "callRemote").return_value = succeed(
            sentinel.power_types
        )
        client = RackClient(conn, {})
        call_cache = client._getCallCache()
        result = yield client(cluster.DescribePowerTypes)
        self.assertIs(sentinel.power_types, result)
        self.assertIs(
            sentinel.power_types, call_cache[cluster.DescribePowerTypes]
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_call__doesnt_add_result_to_cache_for_not_cache_call(self):
        conn = DummyConnection()
        conn.ident = factory.make_name("ident")
        self.patch(conn, "callRemote").return_value = succeed(
            sentinel.boot_images
        )
        client = RackClient(conn, {})
        call_cache = client._getCallCache()
        result = yield client(cluster.ListBootImages)
        self.assertIs(sentinel.boot_images, result)
        self.assertNotIn(cluster.ListBootImages, call_cache)

    @wait_for_reactor
    @inlineCallbacks
    def test_call__records_latency_metric(self):
        mock_metrics = self.patch(PROMETHEUS_METRICS, "update")
        conn = DummyConnection()
        conn.ident = factory.make_name("ident")
        self.patch(conn, "callRemote").return_value = succeed(
            sentinel.boot_images
        )
        client = RackClient(conn, {})
        yield client(cluster.ListBootImages)
        mock_metrics.assert_called_with(
            "maas_region_rack_rpc_call_latency",
            "observe",
            labels={"call": "ListBootImages"},
            value=ANY,
        )


class TestRegionService(MAASTestCase):
    def test_init_sets_appropriate_instance_attributes(self):
        service = RegionService(sentinel.ipcWorker)
        self.assertIsInstance(service, Service)
        self.assertIsInstance(service.connections, defaultdict)
        self.assertIs(service.connections.default_factory, set)
        self.assertThat(
            service.endpoints,
            AllMatch(AllMatch(Provides(IStreamServerEndpoint))),
        )
        self.assertIsInstance(service.factory, Factory)
        self.assertEqual(RegionServer, service.factory.protocol)
        self.assertIsInstance(service.events.connected, events.Event)
        self.assertIsInstance(service.events.disconnected, events.Event)

    @wait_for_reactor
    def test_starting_and_stopping_the_service(self):
        service = RegionService(sentinel.ipcWorker)
        self.assertIsNone(service.starting)
        service.startService()
        self.assertIsInstance(service.starting, Deferred)

        def check_started(_):
            # Ports are saved as private instance vars.
            self.assertThat(service.ports, HasLength(1))
            [port] = service.ports
            self.assertIsInstance(port, tcp.Port)
            self.assertIsInstance(port.factory, Factory)
            self.assertEqual(RegionServer, port.factory.protocol)
            return service.stopService()

        service.starting.addCallback(check_started)

        def check_stopped(ignore, service=service):
            self.assertEqual([], service.ports)

        service.starting.addCallback(check_stopped)

        return service.starting

    @wait_for_reactor
    def test_startService_returns_Deferred(self):
        service = RegionService(sentinel.ipcWorker)

        # Don't configure any endpoints.
        self.patch(service, "endpoints", [])

        d = service.startService()
        self.assertIsInstance(d, Deferred)
        # It's actually the `starting` Deferred.
        self.assertIs(service.starting, d)

        def started(_):
            return service.stopService()

        return d.addCallback(started)

    @wait_for_reactor
    def test_start_up_can_be_cancelled(self):
        service = RegionService(sentinel.ipcWorker)

        # Return an inert Deferred from the listen() call.
        endpoints = self.patch(service, "endpoints", [[Mock()]])
        endpoints[0][0].listen.return_value = Deferred()

        service.startService()
        self.assertIsInstance(service.starting, Deferred)

        service.starting.cancel()

        def check(port):
            self.assertIsNone(port)
            self.assertThat(service.ports, HasLength(0))
            return service.stopService()

        return service.starting.addCallback(check)

    @wait_for_reactor
    @inlineCallbacks
    def test_start_up_errors_are_logged(self):
        ipcWorker = MagicMock()
        service = RegionService(ipcWorker)

        # Ensure that endpoint.listen fails with a obvious error.
        exception = ValueError("This is not the messiah.")
        endpoints = self.patch(service, "endpoints", [[Mock()]])
        endpoints[0][0].listen.return_value = fail(exception)

        logged_failures_expected = [
            AfterPreprocessing((lambda failure: failure.value), Is(exception))
        ]

        with TwistedLoggerFixture() as logger:
            yield service.startService()

        self.assertThat(
            logger.failures, MatchesListwise(logged_failures_expected)
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_start_up_binds_first_of_endpoint_options(self):
        service = RegionService(sentinel.ipcWorker)

        endpoint_1 = Mock()
        endpoint_1.listen.return_value = succeed(sentinel.port1)
        endpoint_2 = Mock()
        endpoint_2.listen.return_value = succeed(sentinel.port2)
        service.endpoints = [[endpoint_1, endpoint_2]]

        yield service.startService()

        self.assertEqual([sentinel.port1], service.ports)

    @wait_for_reactor
    @inlineCallbacks
    def test_start_up_binds_first_of_real_endpoint_options(self):
        service = RegionService(sentinel.ipcWorker)

        # endpoint_1.listen(...) will bind to a random high-numbered port.
        endpoint_1 = TCP4ServerEndpoint(reactor, 0)
        # endpoint_2.listen(...), if attempted, will crash because only root
        # (or a user with explicit capabilities) can do stuff like that. It's
        # a reasonable assumption that the user running these tests is not
        # root, but we'll check the port number later too to be sure.
        endpoint_2 = TCP4ServerEndpoint(reactor, 1)

        service.endpoints = [[endpoint_1, endpoint_2]]

        yield service.startService()
        self.addCleanup(wait_for_reactor(service.stopService))

        # A single port has been bound.
        self.assertThat(
            service.ports,
            MatchesAll(HasLength(1), AllMatch(IsInstance(tcp.Port))),
        )

        # The port is not listening on port 1; i.e. a belt-n-braces check that
        # endpoint_2 was not used.
        [port] = service.ports
        self.assertNotEqual(1, port.getHost().port)

    @wait_for_reactor
    @inlineCallbacks
    def test_start_up_binds_first_successful_of_endpoint_options(self):
        service = RegionService(sentinel.ipcWorker)

        endpoint_broken = Mock()
        endpoint_broken.listen.return_value = fail(factory.make_exception())
        endpoint_okay = Mock()
        endpoint_okay.listen.return_value = succeed(sentinel.port)
        service.endpoints = [[endpoint_broken, endpoint_okay]]

        yield service.startService()

        self.assertEqual([sentinel.port], service.ports)

    @skip("XXX test fails far too often; bug #1582944")
    @wait_for_reactor
    @inlineCallbacks
    def test_start_up_logs_failure_if_all_endpoint_options_fail(self):
        service = RegionService(sentinel.ipcWorker)

        error_1 = factory.make_exception_type()
        error_2 = factory.make_exception_type()

        endpoint_1 = Mock()
        endpoint_1.listen.return_value = fail(error_1())
        endpoint_2 = Mock()
        endpoint_2.listen.return_value = fail(error_2())
        service.endpoints = [[endpoint_1, endpoint_2]]

        with TwistedLoggerFixture() as logger:
            yield service.startService()

        self.assertDocTestMatches(
            """\
            RegionServer endpoint failed to listen.
            Traceback (most recent call last):
            ...
            %s:
            """
            % fullyQualifiedName(error_2),
            logger.output,
        )

    @wait_for_reactor
    def test_stopping_cancels_startup(self):
        service = RegionService(sentinel.ipcWorker)

        # Return an inert Deferred from the listen() call.
        endpoints = self.patch(service, "endpoints", [[Mock()]])
        endpoints[0][0].listen.return_value = Deferred()

        service.startService()
        service.stopService()

        def check(_):
            # The CancelledError is suppressed.
            self.assertThat(service.ports, HasLength(0))

        return service.starting.addCallback(check)

    @wait_for_reactor
    @inlineCallbacks
    def test_stopping_closes_connections_cleanly(self):
        service = RegionService(sentinel.ipcWorker)
        service.starting = Deferred()
        service.starting.addErrback(
            lambda failure: failure.trap(CancelledError)
        )
        service.factory.protocol = HandshakingRegionServer
        connections = {
            service.factory.buildProtocol(None),
            service.factory.buildProtocol(None),
        }
        for conn in connections:
            # Pretend it's already connected.
            service.connections[conn.ident].add(conn)
        transports = {self.patch(conn, "transport") for conn in connections}
        yield service.stopService()
        self.assertThat(
            transports,
            AllMatch(
                AfterPreprocessing(
                    attrgetter("loseConnection"), MockCalledOnceWith()
                )
            ),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_stopping_logs_errors_when_closing_connections(self):
        service = RegionService(sentinel.ipcWorker)
        service.starting = Deferred()
        service.starting.addErrback(
            lambda failure: failure.trap(CancelledError)
        )
        service.factory.protocol = HandshakingRegionServer
        connections = {
            service.factory.buildProtocol(None),
            service.factory.buildProtocol(None),
        }
        for conn in connections:
            transport = self.patch(conn, "transport")
            transport.loseConnection.side_effect = OSError("broken")
            # Pretend it's already connected.
            service.connections[conn.ident].add(conn)
        logger = self.useFixture(TwistedLoggerFixture())
        # stopService() completes without returning an error.
        yield service.stopService()
        # Connection-specific errors are logged.
        self.assertDocTestMatches(
            """\
            Failure when closing RPC connection.
            Traceback (most recent call last):
            ...
            builtins.OSError: broken
            ...
            Failure when closing RPC connection.
            Traceback (most recent call last):
            ...
            builtins.OSError: broken
            """,
            logger.dump(),
        )

    @wait_for_reactor
    def test_stopping_when_start_up_failed(self):
        service = RegionService(sentinel.ipcWorker)

        # Ensure that endpoint.listen fails with a obvious error.
        exception = ValueError("This is a very naughty boy.")
        endpoints = self.patch(service, "endpoints", [[Mock()]])
        endpoints[0][0].listen.return_value = fail(exception)

        service.startService()
        # The test is that stopService() succeeds.
        return service.stopService()

    @wait_for_reactor
    def test_getClientFor_errors_when_no_connections(self):
        service = RegionService(sentinel.ipcWorker)
        service.connections.clear()
        return assert_fails_with(
            service.getClientFor(factory.make_UUID(), timeout=0),
            exceptions.NoConnectionsAvailable,
        )

    @wait_for_reactor
    def test_getClientFor_errors_when_no_connections_for_cluster(self):
        service = RegionService(sentinel.ipcWorker)
        uuid = factory.make_UUID()
        service.connections[uuid].clear()
        return assert_fails_with(
            service.getClientFor(uuid, timeout=0),
            exceptions.NoConnectionsAvailable,
        )

    @wait_for_reactor
    def test_getClientFor_returns_random_connection(self):
        c1 = DummyConnection()
        c2 = DummyConnection()
        chosen = DummyConnection()

        service = RegionService(sentinel.ipcWorker)
        uuid = factory.make_UUID()
        conns_for_uuid = service.connections[uuid]
        conns_for_uuid.update({c1, c2})

        def check_choice(choices):
            self.assertCountEqual(choices, conns_for_uuid)
            return chosen

        self.patch(random, "choice", check_choice)

        def check(client):
            self.assertEqual(RackClient(chosen, {}), client)
            self.assertIs(client.cache, service.connectionsCache[client._conn])

        return service.getClientFor(uuid).addCallback(check)

    @wait_for_reactor
    def test_getAllClients_empty(self):
        service = RegionService(sentinel.ipcWorker)
        service.connections.clear()
        self.assertEqual([], service.getAllClients())

    @wait_for_reactor
    def test_getAllClients_empty_connections(self):
        service = RegionService(sentinel.ipcWorker)
        service.connections.clear()
        uuid1 = factory.make_UUID()
        service.connections[uuid1] = set()
        self.assertEqual([], service.getAllClients())

    @wait_for_reactor
    def test_getRandomClient_empty_raises_NoConnectionsAvailable(self):
        service = RegionService(sentinel.ipcWorker)
        service.connections.clear()
        with ExpectedException(NoConnectionsAvailable):
            service.getRandomClient()

    @wait_for_reactor
    def test_getAllClients(self):
        service = RegionService(sentinel.ipcWorker)
        uuid1 = factory.make_UUID()
        c1 = DummyConnection()
        c2 = DummyConnection()
        service.connections[uuid1].update({c1, c2})
        uuid2 = factory.make_UUID()
        c3 = DummyConnection()
        c4 = DummyConnection()
        service.connections[uuid2].update({c3, c4})
        clients = service.getAllClients()
        self.assertThat(
            list(clients),
            MatchesAny(
                MatchesSetwise(
                    Equals(RackClient(c1, {})), Equals(RackClient(c3, {}))
                ),
                MatchesSetwise(
                    Equals(RackClient(c1, {})), Equals(RackClient(c4, {}))
                ),
                MatchesSetwise(
                    Equals(RackClient(c2, {})), Equals(RackClient(c3, {}))
                ),
                MatchesSetwise(
                    Equals(RackClient(c2, {})), Equals(RackClient(c4, {}))
                ),
            ),
        )

    def test_rack_controller_is_disconnected_returns_True_with_no_connections(
        self,
    ):
        service = RegionService(sentinel.ipcWorker)
        rack_ident = factory.make_UUID()
        self.assertTrue(service.rack_controller_is_disconnected(rack_ident))

    def test_rack_controller_is_disconnected_returns_False_with_connections(
        self,
    ):
        service = RegionService(sentinel.ipcWorker)
        rack_ident = factory.make_UUID()
        c1 = DummyConnection()
        c2 = DummyConnection()
        service.connections[rack_ident].update({c1, c2})
        self.assertFalse(service.rack_controller_is_disconnected(rack_ident))

    def test_addConnectionFor_adds_connection(self):
        service = RegionService(sentinel.ipcWorker)
        uuid = factory.make_UUID()
        c1 = DummyConnection()
        c2 = DummyConnection()

        service._addConnectionFor(uuid, c1)
        service._addConnectionFor(uuid, c2)

        self.assertEqual({uuid: {c1, c2}}, service.connections)

    def test_addConnectionFor_notifies_waiters(self):
        service = RegionService(sentinel.ipcWorker)
        uuid = factory.make_UUID()
        c1 = DummyConnection()
        c2 = DummyConnection()

        waiter1 = Mock()
        waiter2 = Mock()
        service.waiters[uuid].add(waiter1)
        service.waiters[uuid].add(waiter2)

        service._addConnectionFor(uuid, c1)
        service._addConnectionFor(uuid, c2)

        self.assertEqual({uuid: {c1, c2}}, service.connections)
        # Both mock waiters are called twice. A real waiter would only be
        # called once because it immediately unregisters itself once called.
        self.assertThat(waiter1.callback, MockCallsMatch(call(c1), call(c2)))
        self.assertThat(waiter2.callback, MockCallsMatch(call(c1), call(c2)))

    def test_addConnectionFor_fires_connected_event(self):
        service = RegionService(sentinel.ipcWorker)
        uuid = factory.make_UUID()
        c1 = DummyConnection()

        mock_fire = self.patch(service.events.connected, "fire")
        service._addConnectionFor(uuid, c1)

        self.assertThat(mock_fire, MockCalledOnceWith(uuid))

    def test_removeConnectionFor_removes_connection(self):
        service = RegionService(sentinel.ipcWorker)
        uuid = factory.make_UUID()
        c1 = DummyConnection()
        c2 = DummyConnection()

        service._addConnectionFor(uuid, c1)
        service._addConnectionFor(uuid, c2)
        service._removeConnectionFor(uuid, c1)

        self.assertEqual({uuid: {c2}}, service.connections)

    def test_removeConnectionFor_is_okay_if_connection_is_not_there(self):
        service = RegionService(sentinel.ipcWorker)
        uuid = factory.make_UUID()

        service._removeConnectionFor(uuid, DummyConnection())

        self.assertEqual({uuid: set()}, service.connections)

    def test_removeConnectionFor_fires_disconnected_event(self):
        service = RegionService(sentinel.ipcWorker)
        uuid = factory.make_UUID()
        c1 = DummyConnection()

        mock_fire = self.patch(service.events.disconnected, "fire")
        service._removeConnectionFor(uuid, c1)

        self.assertThat(mock_fire, MockCalledOnceWith(uuid))

    @wait_for_reactor
    def test_getConnectionFor_returns_existing_connection(self):
        service = RegionService(sentinel.ipcWorker)
        uuid = factory.make_UUID()
        conn = DummyConnection()

        service._addConnectionFor(uuid, conn)

        d = service._getConnectionFor(uuid, 1)
        # No waiter is added because a connection is available.
        self.assertEqual({uuid: set()}, service.waiters)

        def check(conn_returned):
            self.assertEqual(conn, conn_returned)

        return d.addCallback(check)

    @wait_for_reactor
    def test_getConnectionFor_waits_for_connection(self):
        service = RegionService(sentinel.ipcWorker)
        uuid = factory.make_UUID()
        conn = DummyConnection()

        # Add the connection later (we're in the reactor thread right
        # now so this won't happen until after we return).
        reactor.callLater(0, service._addConnectionFor, uuid, conn)

        d = service._getConnectionFor(uuid, 1)
        # A waiter is added for the connection we're interested in.
        self.assertEqual({uuid: {d}}, service.waiters)

        def check(conn_returned):
            self.assertEqual(conn, conn_returned)
            # The waiter has been unregistered.
            self.assertEqual({uuid: set()}, service.waiters)

        return d.addCallback(check)

    @wait_for_reactor
    def test_getConnectionFor_with_concurrent_waiters(self):
        service = RegionService(sentinel.ipcWorker)
        uuid = factory.make_UUID()
        conn = DummyConnection()

        # Add the connection later (we're in the reactor thread right
        # now so this won't happen until after we return).
        reactor.callLater(0, service._addConnectionFor, uuid, conn)

        d1 = service._getConnectionFor(uuid, 1)
        d2 = service._getConnectionFor(uuid, 1)
        # A waiter is added for each call to _getConnectionFor().
        self.assertEqual({uuid: {d1, d2}}, service.waiters)

        d = DeferredList((d1, d2))

        def check(results):
            self.assertEqual([(True, conn), (True, conn)], results)
            # The waiters have both been unregistered.
            self.assertEqual({uuid: set()}, service.waiters)

        return d.addCallback(check)

    @wait_for_reactor
    def test_getConnectionFor_cancels_waiter_when_it_times_out(self):
        service = RegionService(sentinel.ipcWorker)
        uuid = factory.make_UUID()

        d = service._getConnectionFor(uuid, 1)
        # A waiter is added for the connection we're interested in.
        self.assertEqual({uuid: {d}}, service.waiters)
        d = assert_fails_with(d, CancelledError)

        def check(_):
            # The waiter has been unregistered.
            self.assertEqual({uuid: set()}, service.waiters)

        return d.addCallback(check)
