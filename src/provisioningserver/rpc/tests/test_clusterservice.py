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
import os.path

from fixtures import EnvironmentVariable
from maastesting.factory import factory
from maastesting.matchers import Provides
from maastesting.testcase import MAASTestCase
from mock import (
    Mock,
    sentinel,
    )
from provisioningserver.config import Config
from provisioningserver.pxe import tftppath
from provisioningserver.rpc import clusterservice
from provisioningserver.rpc.cluster import ListBootImages
from provisioningserver.rpc.clusterservice import (
    Cluster,
    ClusterClientService,
    ClusterService,
    )
from provisioningserver.rpc.testing import call_responder
from testtools.deferredruntest import AsynchronousDeferredRunTest
from testtools.matchers import (
    Equals,
    GreaterThan,
    HasLength,
    Is,
    IsInstance,
    KeysEqual,
    LessThan,
    MatchesAll,
    MatchesAny,
    MatchesListwise,
    MatchesStructure,
    )
from twisted.application.internet import (
    StreamServerEndpointService,
    TimerService,
    )
from twisted.internet import reactor
from twisted.internet.address import HostnameAddress
from twisted.internet.defer import succeed
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.interfaces import IStreamServerEndpoint
from twisted.internet.protocol import Factory
from twisted.internet.task import Clock
from twisted.test.proto_helpers import StringTransportWithDisconnection


class TestClusterProtocol(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def test_list_boot_images_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(ListBootImages.commandName)
        self.assertIsNot(responder, None)

    def test_list_boot_images_can_be_called(self):
        list_boot_images = self.patch(tftppath, "list_boot_images")
        list_boot_images.return_value = []

        d = call_responder(Cluster(), ListBootImages, {})

        def check(response):
            self.assertEqual({"images": []}, response)

        return d.addCallback(check)

    def test_list_boot_images_with_things_to_report(self):
        # tftppath.list_boot_images()'s return value matches the
        # response schema that ListBootImages declares, and is
        # serialised correctly.

        # Example boot image definitions.
        archs = "i386", "amd64"
        subarchs = "generic", "special"
        releases = "precise", "trusty"
        purposes = "commission", "install"

        # Create a TFTP file tree with a variety of subdirectories.
        tftpdir = self.make_dir()
        for options in product(archs, subarchs, releases, purposes):
            os.makedirs(os.path.join(tftpdir, *options))

        # Ensure that list_boot_images() uses the above TFTP file tree.
        load_from_cache = self.patch(Config, "load_from_cache")
        load_from_cache.return_value = {"tftp": {"root": tftpdir}}

        expected_images = [
            {"architecture": arch, "subarchitecture": subarch,
             "release": release, "purpose": purpose}
            for arch, subarch, release, purpose in product(
                archs, subarchs, releases, purposes)
        ]

        d = call_responder(Cluster(), ListBootImages, {})

        def check(response):
            self.assertThat(response, KeysEqual("images"))
            self.assertItemsEqual(expected_images, response["images"])

        return d.addCallback(check)


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

    def test_init_sets_appropriate_instance_attributes(self):
        service = ClusterClientService(sentinel.reactor)
        self.assertThat(service, IsInstance(TimerService))
        self.assertThat(service.clock, Is(sentinel.reactor))

    def test__get_rpc_info_url(self):
        maas_url = "http://%s/%s/" % (
            factory.make_hostname(), factory.make_name("path"))
        self.useFixture(EnvironmentVariable("MAAS_URL", maas_url))
        expected_rpc_info_url = maas_url + "rpc"
        observed_rpc_info_url = ClusterClientService._get_rpc_info_url()
        self.assertThat(observed_rpc_info_url, Equals(expected_rpc_info_url))

    def test__get_random_interval(self):
        # _get_random_interval() returns a random number between 30 and
        # 90 inclusive.
        is_between_30_and_90_inclusive = MatchesAll(
            MatchesAny(GreaterThan(30), Equals(30)),
            MatchesAny(LessThan(90), Equals(90)))
        for _ in range(100):
            self.assertThat(
                ClusterClientService._get_random_interval(),
                is_between_30_and_90_inclusive)

    def test__get_random_interval_calls_into_standard_library(self):
        # _get_random_interval() depends entirely on the standard library.
        random = self.patch(clusterservice, "random")
        random.randint.return_value = sentinel.randint
        self.assertIs(
            sentinel.randint,
            ClusterClientService._get_random_interval())
        random.randint.assert_called_once_with(30, 90)

    def test__update_interval(self):
        service = ClusterClientService(Clock())
        # ClusterClientService's superclass, TimerService, creates a
        # LoopingCall with now=True. We neuter it here because we only
        # want to observe the behaviour of _update_interval().
        service.call = (lambda: None, (), {})
        service.startService()
        self.assertThat(service.step, MatchesAll(
            Equals(service._loop.interval), IsInstance(int)))
        service.step = service._loop.interval = sentinel.undefined
        service._update_interval()
        self.assertThat(service.step, MatchesAll(
            Equals(service._loop.interval), IsInstance(int)))

    def test_update_calls__update_connections(self):
        maas_url = "http://%s/%s/" % (
            factory.make_hostname(), factory.make_name("path"))
        self.useFixture(EnvironmentVariable("MAAS_URL", maas_url))
        getPage = self.patch(clusterservice, "getPage")
        getPage.return_value = succeed(
            '{"endpoints": [["example.com", 54321]]}')
        service = ClusterClientService(Clock())
        _update_connections = self.patch(service, "_update_connections")
        service.startService()
        _update_connections.assert_called_once_with([["example.com", 54321]])

    def test__update_connections_initially(self):
        service = ClusterClientService(Clock())
        make_connections = self.patch(service, "_make_connections")
        drop_connections = self.patch(service, "_drop_connections")

        service._update_connections(
            [("a.example.com", 1111), ("b.example.com", 2222)])
        make_connections.assert_called_with(
            {HostnameAddress("a.example.com", 1111),
             HostnameAddress("b.example.com", 2222)})
        drop_connections.assert_called_with(set())

    def test__update_connections_when_there_are_existing_connections(self):
        service = ClusterClientService(Clock())
        make_connections = self.patch(service, "_make_connections")
        drop_connections = self.patch(service, "_drop_connections")

        # Fake some connections.
        service.connections = {
            HostnameAddress("a.example.com", 1111): None,
            HostnameAddress("b.example.com", 2222): None,
        }

        service._update_connections(
            [("a.example.com", 1111), ("c.example.com", 3333)])

        make_connections.assert_called_with(
            {HostnameAddress("c.example.com", 3333)})
        drop_connections.assert_called_with(
            {HostnameAddress("b.example.com", 2222)})

    def test__make_connections(self):
        service = ClusterClientService(Clock())
        connectProtocol = self.patch(clusterservice, "connectProtocol")
        service._make_connections({HostnameAddress("a.example.com", 1111)})
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
                        address=HostnameAddress("a.example.com", 1111),
                        service=service,
                    ),
                ),
            )))

    def test__drop_connections(self):
        address = HostnameAddress("a.example.com", 1111)
        connection = Mock()
        service = ClusterClientService(Clock())
        service.connections[address] = connection
        service._drop_connections({address})
        connection.loseConnection.assert_called_once_with()
        # The connection is *not* removed from the connection map;
        # that's the responsibility of the protocol.
        self.assertEqual({address: connection}, service.connections)


class TestClusterClient(MAASTestCase):

    def make_running_client(self):
        client = clusterservice.ClusterClient()
        client.address = HostnameAddress("example.com", 1234)
        client.service = ClusterClientService(Clock())
        client.service.running = True
        return client

    def test_connecting(self):
        client = self.make_running_client()
        self.assertEqual(client.service.connections, {})
        client.connectionMade()
        self.assertEqual(
            client.service.connections,
            {client.address: client})

    def test_disconnects_when_there_is_an_existing_connection(self):
        client = self.make_running_client()

        # Pretend that a connection already exists for this address.
        client.service.connections[client.address] = sentinel.connection

        # Connect via an in-memory transport.
        transport = StringTransportWithDisconnection()
        transport.protocol = client
        client.makeConnection(transport)

        # The connections list is unchanged because the new connection
        # immediately disconnects.
        self.assertEqual(
            client.service.connections,
            {client.address: sentinel.connection})
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
