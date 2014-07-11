# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the cluster's RPC implementation."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from itertools import product
import json
import os.path
from random import randint

from fixtures import EnvironmentVariable
from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCalledWith,
    MockCallsMatch,
    MockNotCalled,
    Provides,
    )
from maastesting.testcase import MAASTestCase
from mock import (
    call,
    Mock,
    sentinel,
    )
from provisioningserver.boot import tftppath
from provisioningserver.boot.tests.test_tftppath import make_osystem
from provisioningserver.power_schema import JSON_POWER_TYPE_PARAMETERS
from provisioningserver.rpc import (
    cluster,
    clusterservice,
    common,
    exceptions,
    osystems as osystems_rpc_module,
    region,
    )
from provisioningserver.rpc.clusterservice import (
    Cluster,
    ClusterClient,
    ClusterClientService,
    ClusterService,
    )
from provisioningserver.rpc.interfaces import IConnection
from provisioningserver.rpc.osystems import gen_operating_systems
from provisioningserver.rpc.testing import (
    are_valid_tls_parameters,
    call_responder,
    TwistedLoggerFixture,
    )
from provisioningserver.rpc.testing.doubles import (
    DummyConnection,
    StubOS,
    )
from provisioningserver.testing.config import set_tftp_root
from testtools.deferredruntest import AsynchronousDeferredRunTest
from testtools.matchers import (
    Equals,
    HasLength,
    Is,
    IsInstance,
    KeysEqual,
    MatchesAll,
    MatchesListwise,
    MatchesStructure,
    )
from twisted.application.internet import (
    StreamServerEndpointService,
    TimerService,
    )
from twisted.internet import (
    error,
    reactor,
    )
from twisted.internet.defer import (
    inlineCallbacks,
    succeed,
    )
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.interfaces import IStreamServerEndpoint
from twisted.internet.protocol import Factory
from twisted.internet.task import Clock
from twisted.protocols import amp
from twisted.test.proto_helpers import StringTransportWithDisconnection
from zope.interface.verify import verifyObject


class TestClusterProtocol_Identify(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def test_identify_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(cluster.Identify.commandName)
        self.assertIsNot(responder, None)

    def test_identify_reports_cluster_uuid(self):
        example_uuid = factory.getRandomUUID()

        get_cluster_uuid = self.patch(clusterservice, "get_cluster_uuid")
        get_cluster_uuid.return_value = example_uuid

        d = call_responder(Cluster(), cluster.Identify, {})

        def check(response):
            self.assertEqual({"ident": example_uuid}, response)
        return d.addCallback(check)


class TestClusterProtocol_StartTLS(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def test_StartTLS_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(amp.StartTLS.commandName)
        self.assertIsNot(responder, None)

    def test_get_tls_parameters_returns_parameters(self):
        # get_tls_parameters() is the underlying responder function.
        # However, locateResponder() returns a closure, so we have to
        # side-step it.
        protocol = Cluster()
        cls, func = protocol._commandDispatch[amp.StartTLS.commandName]
        self.assertThat(func(protocol), are_valid_tls_parameters)

    def test_StartTLS_returns_nothing(self):
        # The StartTLS command does some funky things - see _TLSBox and
        # _LocalArgument for an idea - so the parameters returned from
        # get_tls_parameters() - the registered responder - don't end up
        # travelling over the wire as part of an AMP message. However,
        # the responder is not aware of this, and is called just like
        # any other.
        d = call_responder(Cluster(), amp.StartTLS, {})

        def check(response):
            self.assertEqual({}, response)

        return d.addCallback(check)


class TestClusterProtocol_ListBootImages(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def test_list_boot_images_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.ListBootImages.commandName)
        self.assertIsNot(responder, None)

    @inlineCallbacks
    def test_list_boot_images_can_be_called(self):
        list_boot_images = self.patch(tftppath, "list_boot_images")
        list_boot_images.return_value = []

        response = yield call_responder(Cluster(), cluster.ListBootImages, {})

        self.assertEqual({"images": []}, response)

    @inlineCallbacks
    def test_list_boot_images_with_things_to_report(self):
        # tftppath.list_boot_images()'s return value matches the
        # response schema that ListBootImages declares, and is
        # serialised correctly.

        # Example boot image definitions.
        osystems = "ubuntu", "centos"
        archs = "i386", "amd64"
        subarchs = "generic", "special"
        releases = "precise", "trusty"
        labels = "beta-1", "release"
        purposes = "commissioning", "install", "xinstall"

        # Create a TFTP file tree with a variety of subdirectories.
        tftpdir = self.make_dir()
        for options in product(osystems, archs, subarchs, releases, labels):
            os.makedirs(os.path.join(tftpdir, *options))
            make_osystem(self, options[0], purposes)

        # Ensure that list_boot_images() uses the above TFTP file tree.
        self.useFixture(set_tftp_root(tftpdir))

        expected_images = [
            {
                "osystem": osystem,
                "architecture": arch,
                "subarchitecture": subarch,
                "release": release,
                "label": label,
                "purpose": purpose,
            }
            for osystem, arch, subarch, release, label, purpose in product(
                osystems, archs, subarchs, releases, labels, purposes)
            ]

        response = yield call_responder(Cluster(), cluster.ListBootImages, {})

        self.assertThat(response, KeysEqual("images"))
        self.assertItemsEqual(expected_images, response["images"])


class TestClusterProtocol_DescribePowerTypes(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def test_describe_power_types_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.DescribePowerTypes.commandName)
        self.assertIsNot(responder, None)

    @inlineCallbacks
    def test_describe_power_types_returns_jsonized_power_parameters(self):

        response = yield call_responder(
            Cluster(), cluster.DescribePowerTypes, {})

        self.assertThat(response, KeysEqual("power_types"))
        self.assertItemsEqual(
            JSON_POWER_TYPE_PARAMETERS, response["power_types"])


class TestClusterService(MAASTestCase):

    def test_init_sets_appropriate_instance_attributes(self):
        # ClusterService is a convenience wrapper around
        # StreamServerEndpointService. There's not much to demonstrate
        # other than it has been initialised correctly.
        service = ClusterService(reactor, 0)
        self.assertThat(service, IsInstance(StreamServerEndpointService))
        self.assertThat(service.endpoint, Provides(IStreamServerEndpoint))
        self.assertThat(service.factory, IsInstance(Factory))
        self.assertThat(service.factory.protocol, Equals(Cluster))


class TestClusterClientService(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def test_init_sets_appropriate_instance_attributes(self):
        service = ClusterClientService(sentinel.reactor)
        self.assertThat(service, IsInstance(TimerService))
        self.assertThat(service.clock, Is(sentinel.reactor))

    def test__get_rpc_info_url(self):
        maas_url = "http://%s/%s/" % (
            factory.make_hostname(), factory.make_name("path"))
        self.useFixture(EnvironmentVariable("MAAS_URL", maas_url))
        expected_rpc_info_url = maas_url + "rpc/"
        observed_rpc_info_url = ClusterClientService._get_rpc_info_url()
        self.assertThat(observed_rpc_info_url, Equals(expected_rpc_info_url))

    def test_update_connect_error_is_logged_tersely(self):
        getPage = self.patch(clusterservice, "getPage")
        getPage.side_effect = error.ConnectionRefusedError()

        logger = self.useFixture(TwistedLoggerFixture())

        service = ClusterClientService(Clock())
        _get_rpc_info_url = self.patch(service, "_get_rpc_info_url")
        _get_rpc_info_url.return_value = sentinel.rpc_info_url

        # Starting the service causes the first update to be performed.
        service.startService()

        self.assertThat(getPage, MockCalledOnceWith(sentinel.rpc_info_url))
        self.assertEqual(
            "Region not available: Connection was refused by other side.",
            logger.dump())

    # The following represents an example response from the RPC info
    # view in maasserver. Event-loops listen on ephemeral ports, and
    # it's up to the RPC info view to direct clients to them.
    example_rpc_info_view_response = json.dumps({
        "eventloops": {
            # An event-loop in pid 1001 on host1. This host has two
            # configured IP addresses, 1.1.1.1 and 1.1.1.2.
            "host1:pid=1001": [
                ("1.1.1.1", 1111),
                ("1.1.1.2", 2222),
            ],
            # An event-loop in pid 2002 on host1. This host has two
            # configured IP addresses, 1.1.1.1 and 1.1.1.2.
            "host1:pid=2002": [
                ("1.1.1.1", 3333),
                ("1.1.1.2", 4444),
            ],
            # An event-loop in pid 3003 on host2. This host has one
            # configured IP address, 2.2.2.2.
            "host2:pid=3003": [
                ("2.2.2.2", 5555),
            ],
        },
    })

    def test_update_calls__update_connections(self):
        maas_url = "http://%s/%s/" % (
            factory.make_hostname(), factory.make_name("path"))
        self.useFixture(EnvironmentVariable("MAAS_URL", maas_url))
        getPage = self.patch(clusterservice, "getPage")
        getPage.return_value = succeed(self.example_rpc_info_view_response)
        service = ClusterClientService(Clock())
        _update_connections = self.patch(service, "_update_connections")
        service.startService()
        self.assertThat(_update_connections, MockCalledOnceWith({
            "host2:pid=3003": [
                ["2.2.2.2", 5555],
            ],
            "host1:pid=2002": [
                ["1.1.1.1", 3333],
                ["1.1.1.2", 4444],
            ],
            "host1:pid=1001": [
                ["1.1.1.1", 1111],
                ["1.1.1.2", 2222],
            ],
        }))

    @inlineCallbacks
    def test__update_connections_initially(self):
        service = ClusterClientService(Clock())
        _make_connection = self.patch(service, "_make_connection")
        _drop_connection = self.patch(service, "_drop_connection")

        info = json.loads(self.example_rpc_info_view_response)
        yield service._update_connections(info["eventloops"])

        _make_connection_expected = [
            call("host1:pid=1001", ("1.1.1.1", 1111)),
            call("host1:pid=2002", ("1.1.1.1", 3333)),
            call("host2:pid=3003", ("2.2.2.2", 5555)),
        ]
        self.assertItemsEqual(
            _make_connection_expected,
            _make_connection.call_args_list)

        self.assertEqual([], _drop_connection.mock_calls)

    @inlineCallbacks
    def test__update_connections_connect_error_is_logged_tersely(self):
        service = ClusterClientService(Clock())
        _make_connection = self.patch(service, "_make_connection")
        _make_connection.side_effect = error.ConnectionRefusedError()

        logger = self.useFixture(TwistedLoggerFixture())

        eventloops = {"an-event-loop": [("hostname", 1234)]}
        yield service._update_connections(eventloops)

        self.assertThat(
            _make_connection,
            MockCalledOnceWith("an-event-loop", ("hostname", 1234)))

        self.assertEqual(
            "Event-loop an-event-loop (hostname:1234): Connection "
            "was refused by other side.", logger.dump())

    @inlineCallbacks
    def test__update_connections_unknown_error_is_logged_with_stack(self):
        service = ClusterClientService(Clock())
        _make_connection = self.patch(service, "_make_connection")
        _make_connection.side_effect = RuntimeError("Something went wrong.")

        logger = self.useFixture(TwistedLoggerFixture())

        eventloops = {"an-event-loop": [("hostname", 1234)]}
        yield service._update_connections(eventloops)

        self.assertThat(
            _make_connection,
            MockCalledOnceWith("an-event-loop", ("hostname", 1234)))

        self.assertDocTestMatches(
            """\
            Unhandled Error
            Traceback (most recent call last):
            ...
            exceptions.RuntimeError: Something went wrong.
            """,
            logger.dump())

    def test__update_connections_when_there_are_existing_connections(self):
        service = ClusterClientService(Clock())
        _make_connection = self.patch(service, "_make_connection")
        _drop_connection = self.patch(service, "_drop_connection")

        host1client = ClusterClient(
            ("1.1.1.1", 1111), "host1:pid=1", service)
        host2client = ClusterClient(
            ("2.2.2.2", 2222), "host2:pid=2", service)
        host3client = ClusterClient(
            ("3.3.3.3", 3333), "host3:pid=3", service)

        # Fake some connections.
        service.connections = {
            host1client.eventloop: host1client,
            host2client.eventloop: host2client,
        }

        # Request a new set of connections that overlaps with the
        # existing connections.
        service._update_connections({
            host1client.eventloop: [
                host1client.address,
            ],
            host3client.eventloop: [
                host3client.address,
            ],
        })

        # A connection is made for host3's event-loop, and the
        # connection to host2's event-loop is dropped.
        self.assertThat(
            _make_connection,
            MockCalledOnceWith(host3client.eventloop, host3client.address))
        self.assertThat(_drop_connection, MockCalledWith(host2client))

    def test__make_connection(self):
        service = ClusterClientService(Clock())
        connectProtocol = self.patch(clusterservice, "connectProtocol")
        service._make_connection("an-event-loop", ("a.example.com", 1111))
        self.assertThat(connectProtocol.call_args_list, HasLength(1))
        self.assertThat(
            connectProtocol.call_args_list[0][0],
            MatchesListwise((
                # First argument is an IPv4 TCP client endpoint
                # specification.
                MatchesAll(
                    IsInstance(TCP4ClientEndpoint),
                    MatchesStructure.byEquality(
                        _reactor=service.clock,
                        _host="a.example.com",
                        _port=1111,
                    ),
                ),
                # Second argument is a ClusterClient instance, the
                # protocol to use for the connection.
                MatchesAll(
                    IsInstance(clusterservice.ClusterClient),
                    MatchesStructure.byEquality(
                        address=("a.example.com", 1111),
                        eventloop="an-event-loop",
                        service=service,
                    ),
                ),
            )))

    def test__drop_connection(self):
        connection = Mock()
        service = ClusterClientService(Clock())
        service._drop_connection(connection)
        self.assertThat(
            connection.transport.loseConnection,
            MockCalledOnceWith())

    def test_getClient(self):
        service = ClusterClientService(Clock())
        service.connections = {
            sentinel.eventloop01: DummyConnection(),
            sentinel.eventloop02: DummyConnection(),
            sentinel.eventloop03: DummyConnection(),
        }
        self.assertIn(
            service.getClient(), {
                common.Client(conn)
                for conn in service.connections.viewvalues()
            })

    def test_getClient_when_there_are_no_connections(self):
        service = ClusterClientService(Clock())
        service.connections = {}
        self.assertRaises(
            exceptions.NoConnectionsAvailable,
            service.getClient)


class TestClusterClientServiceIntervals(MAASTestCase):

    scenarios = (
        ("initial", {
            "num_eventloops": None,
            "num_connections": None,
            "expected": ClusterClientService.INTERVAL_LOW,
        }),
        ("no-event-loops", {
            "num_eventloops": 0,
            "num_connections": sentinel.undefined,
            "expected": ClusterClientService.INTERVAL_LOW,
        }),
        ("no-connections", {
            "num_eventloops": 1,  # anything > 1.
            "num_connections": 0,
            "expected": ClusterClientService.INTERVAL_LOW,
        }),
        ("fewer-connections-than-event-loops", {
            "num_eventloops": 2,  # anything > num_connections.
            "num_connections": 1,  # anything > 0.
            "expected": ClusterClientService.INTERVAL_MID,
        }),
        ("default", {
            "num_eventloops": 3,  # same as num_connections.
            "num_connections": 3,  # same as num_eventloops.
            "expected": ClusterClientService.INTERVAL_HIGH,
        }),
    )

    def make_inert_client_service(self):
        service = ClusterClientService(Clock())
        # ClusterClientService's superclass, TimerService, creates a
        # LoopingCall with now=True. We neuter it here to allow
        # observation of the behaviour of _update_interval() for
        # example.
        service.call = (lambda: None, (), {})
        return service

    def test__calculate_interval(self):
        service = self.make_inert_client_service()
        service.startService()
        self.assertEqual(
            self.expected, service._calculate_interval(
                self.num_eventloops, self.num_connections))


class TestClusterClient(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def make_running_client(self):
        client = clusterservice.ClusterClient(
            address=("example.com", 1234), eventloop="eventloop:pid=12345",
            service=ClusterClientService(Clock()))
        client.service.running = True
        return client

    def test_interfaces(self):
        client = self.make_running_client()
        verifyObject(IConnection, client)

    def test_ident(self):
        client = self.make_running_client()
        client.eventloop = self.getUniqueString()
        self.assertThat(client.ident, Equals(client.eventloop))

    def test_connecting(self):
        client = self.make_running_client()
        self.assertEqual(client.service.connections, {})
        client.connectionMade()
        self.assertEqual(
            client.service.connections,
            {client.eventloop: client})

    def test_disconnects_when_there_is_an_existing_connection(self):
        client = self.make_running_client()

        # Pretend that a connection already exists for this address.
        client.service.connections[client.eventloop] = sentinel.connection

        # Connect via an in-memory transport.
        transport = StringTransportWithDisconnection()
        transport.protocol = client
        client.makeConnection(transport)

        # The connections list is unchanged because the new connection
        # immediately disconnects.
        self.assertEqual(
            client.service.connections,
            {client.eventloop: sentinel.connection})
        self.assertFalse(client.connected)
        self.assertIsNone(client.transport)

    def test_disconnects_when_service_is_not_running(self):
        client = self.make_running_client()
        client.service.running = False

        # Connect via an in-memory transport.
        transport = StringTransportWithDisconnection()
        transport.protocol = client
        client.makeConnection(transport)

        # The connections list is unchanged because the new connection
        # immediately disconnects.
        self.assertEqual(client.service.connections, {})
        self.assertFalse(client.connected)

    @inlineCallbacks
    def test_secureConnection_calls_StartTLS_and_Identify(self):
        client = self.make_running_client()

        callRemote = self.patch(client, "callRemote")
        callRemote_return_values = [
            {},  # In response to a StartTLS call.
            {"name": client.eventloop},  # Identify.
        ]
        callRemote.side_effect = lambda cmd, **kwargs: (
            callRemote_return_values.pop(0))

        transport = self.patch(client, "transport")
        logger = self.useFixture(TwistedLoggerFixture())

        yield client.secureConnection()

        self.assertThat(
            callRemote, MockCallsMatch(
                call(amp.StartTLS, **client.get_tls_parameters()),
                call(region.Identify),
            ))

        # The connection is not dropped.
        self.assertThat(transport.loseConnection, MockNotCalled())

        # The certificates used are echoed to the log.
        self.assertDocTestMatches(
            """\
            Host certificate: ...
            ---
            Peer certificate: ...
            """,
            logger.dump())

    @inlineCallbacks
    def test_secureConnection_disconnects_if_ident_does_not_match(self):
        client = self.make_running_client()

        callRemote = self.patch(client, "callRemote")
        callRemote_return_values = [
            {},  # In response to a StartTLS call.
            {"name": "bogus-name"},  # Identify.
        ]
        callRemote.side_effect = lambda cmd, **kwargs: (
            callRemote_return_values.pop(0))

        transport = self.patch(client, "transport")
        logger = self.useFixture(TwistedLoggerFixture())

        yield client.secureConnection()

        # The connection is dropped.
        self.assertThat(
            transport.loseConnection, MockCalledOnceWith())

        # The log explains why.
        self.assertDocTestMatches(
            """\
            The remote event-loop identifies itself as bogus-name, but
            eventloop:pid=12345 was expected.
            """,
            logger.dump())


class TestClusterProtocol_ListSupportedArchitectures(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.ListSupportedArchitectures.commandName)
        self.assertIsNot(responder, None)

    @inlineCallbacks
    def test_returns_architectures(self):
        architectures = yield call_responder(
            Cluster(), cluster.ListSupportedArchitectures, {})
        # Assert that one of the built-in architectures is in the data
        # returned by ListSupportedArchitectures.
        self.assertIn(
            {
                'name': 'i386/generic',
                'description': 'i386',
            },
            architectures['architectures'])


class TestClusterProtocol_ListOperatingSystems(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.ListOperatingSystems.commandName)
        self.assertIsNot(responder, None)

    @inlineCallbacks
    def test_returns_oses(self):
        # Patch in some operating systems with some randomised data. See
        # StubOS for details of the rules that are used to populate the
        # non-random elements.
        operating_systems = [
            StubOS(factory.make_name("os"), releases=[
                (factory.make_name("name"), factory.make_name("title"))
                for _ in range(randint(2, 5))
            ])
            for _ in range(randint(2, 5))
        ]
        self.patch(
            osystems_rpc_module, "OperatingSystemRegistry",
            [(os.name, os) for os in operating_systems])
        osystems = yield call_responder(
            Cluster(), cluster.ListOperatingSystems, {})
        # The fully-populated output from gen_operating_systems() sent
        # back over the wire.
        expected_osystems = list(gen_operating_systems())
        for expected_osystem in expected_osystems:
            expected_osystem["releases"] = list(expected_osystem["releases"])
        expected = {"osystems": expected_osystems}
        self.assertEqual(expected, osystems)
