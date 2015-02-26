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

from datetime import (
    datetime,
    timedelta,
    )
from hashlib import sha256
from hmac import HMAC
from itertools import product
import json
import os.path
import random
from random import randint
from unittest import skip
from urlparse import urlparse

from apiclient.creds import convert_tuple_to_string
from fixtures import EnvironmentVariable
from maastesting.factory import factory
from maastesting.matchers import (
    IsUnfiredDeferred,
    MockAnyCall,
    MockCalledOnceWith,
    MockCalledWith,
    MockCallsMatch,
    MockNotCalled,
    )
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
    )
from mock import (
    ANY,
    call,
    Mock,
    sentinel,
    )
from provisioningserver import concurrency
from provisioningserver.boot import tftppath
from provisioningserver.boot.tests.test_tftppath import make_osystem
from provisioningserver.cluster_config import (
    get_cluster_uuid,
    get_maas_url,
    )
from provisioningserver.dhcp.testing.config import make_subnet_config
from provisioningserver.drivers.osystem import (
    OperatingSystem,
    OperatingSystemRegistry,
    )
from provisioningserver.network import discover_networks
from provisioningserver.power.poweraction import (
    PowerActionFail,
    UnknownPowerType,
    )
from provisioningserver.power_schema import JSON_POWER_TYPE_PARAMETERS
from provisioningserver.rpc import (
    boot_images,
    cluster,
    clusterservice,
    common,
    dhcp,
    exceptions,
    getRegionClient,
    osystems as osystems_rpc_module,
    power as power_module,
    region,
    tags,
    )
from provisioningserver.rpc.clusterservice import (
    Cluster,
    ClusterClient,
    ClusterClientService,
    PatchedURI,
    )
from provisioningserver.rpc.interfaces import IConnection
from provisioningserver.rpc.monitors import (
    cancel_monitor,
    running_monitors,
    )
from provisioningserver.rpc.osystems import gen_operating_systems
from provisioningserver.rpc.power import QUERY_POWER_TYPES
from provisioningserver.rpc.testing import (
    always_fail_with,
    always_succeed_with,
    are_valid_tls_parameters,
    call_responder,
    MockLiveClusterToRegionRPCFixture,
    TwistedLoggerFixture,
    )
from provisioningserver.rpc.testing.doubles import (
    DummyConnection,
    StubOS,
    )
from provisioningserver.security import set_shared_secret_on_filesystem
from testtools import ExpectedException
from testtools.deferredruntest import extract_result
from testtools.matchers import (
    Contains,
    Equals,
    HasLength,
    Is,
    IsInstance,
    KeysEqual,
    MatchesAll,
    MatchesListwise,
    MatchesStructure,
    Not,
    )
from twisted.application.internet import TimerService
from twisted.internet import (
    error,
    reactor,
    )
from twisted.internet.defer import (
    fail,
    inlineCallbacks,
    succeed,
    )
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.error import ConnectionClosed
from twisted.internet.task import Clock
from twisted.protocols import amp
from twisted.python.failure import Failure
from twisted.python.threadable import isInIOThread
from twisted.test.proto_helpers import StringTransportWithDisconnection
from zope.interface.verify import verifyObject


class TestClusterProtocol_Identify(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_identify_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(cluster.Identify.commandName)
        self.assertIsNotNone(responder)

    def test_identify_reports_cluster_uuid(self):
        example_uuid = factory.make_UUID()

        get_cluster_uuid = self.patch(clusterservice, "get_cluster_uuid")
        get_cluster_uuid.return_value = example_uuid

        d = call_responder(Cluster(), cluster.Identify, {})

        def check(response):
            self.assertEqual({"ident": example_uuid}, response)
        return d.addCallback(check)


class TestClusterProtocol_Authenticate(MAASTestCase):

    def test_authenticate_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(cluster.Authenticate.commandName)
        self.assertIsNotNone(responder)

    def test_authenticate_calculates_digest_with_salt(self):
        message = factory.make_bytes()
        secret = factory.make_bytes()
        set_shared_secret_on_filesystem(secret)

        args = {b"message": message}
        d = call_responder(Cluster(), cluster.Authenticate, args)
        response = extract_result(d)
        digest = response["digest"]
        salt = response["salt"]

        self.assertThat(salt, HasLength(16))
        expected_digest = HMAC(secret, message + salt, sha256).digest()
        self.assertEqual(expected_digest, digest)


class TestClusterProtocol_StartTLS(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_StartTLS_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(amp.StartTLS.commandName)
        self.assertIsNotNone(responder)

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

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_list_boot_images_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.ListBootImages.commandName)
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_list_boot_images_can_be_called(self):
        self.patch(boot_images, 'CACHED_BOOT_IMAGES', None)
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
        current_dir = os.path.join(tftpdir, 'current')
        os.makedirs(current_dir)
        for options in product(osystems, archs, subarchs, releases, labels):
            os.makedirs(os.path.join(current_dir, *options))
            make_osystem(self, options[0], purposes)
        self.patch(boot_images, 'BOOT_RESOURCES_STORAGE', tftpdir)
        self.patch(boot_images, 'CACHED_BOOT_IMAGES', None)

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
        for expected_image in expected_images:
            if expected_image['purpose'] == 'xinstall':
                expected_image['xinstall_path'] = 'root-tgz'
                expected_image['xinstall_type'] = 'tgz'
            else:
                expected_image['xinstall_path'] = ''
                expected_image['xinstall_type'] = ''

        response = yield call_responder(Cluster(), cluster.ListBootImages, {})

        self.assertThat(response, KeysEqual("images"))
        self.assertItemsEqual(expected_images, response["images"])


class TestClusterProtocol_ImportBootImages(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_import_boot_images_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.ImportBootImages.commandName)
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_import_boot_images_can_be_called(self):
        self.patch(clusterservice, "import_boot_images")
        response = yield call_responder(
            Cluster(), cluster.ImportBootImages, {'sources': []})
        self.assertEqual({}, response)

    @inlineCallbacks
    def test_import_boot_images_calls_import_boot_images_with_sources(self):
        import_boot_images = self.patch(clusterservice, "import_boot_images")

        sources = [
            {
                'url': factory.make_url(),
                'keyring_data': b'',
                'selections': [
                    {
                        'os': 'ubuntu',
                        'release': "trusty",
                        'arches': ["amd64"],
                        'subarches': ["generic"],
                        'labels': ["release"],
                    },
                ],
            },
        ]

        yield call_responder(
            Cluster(), cluster.ImportBootImages, {'sources': sources})

        self.assertThat(
            import_boot_images,
            MockCalledOnceWith(sources, http_proxy=None, https_proxy=None))

    @inlineCallbacks
    def test_import_boot_images_calls_import_boot_images_with_proxies(self):
        import_boot_images = self.patch(clusterservice, "import_boot_images")

        proxy = 'http://%s.example.com' % factory.make_name('proxy')
        parsed_proxy = urlparse(proxy)

        yield call_responder(
            Cluster(), cluster.ImportBootImages, {
                'sources': [],
                'http_proxy': parsed_proxy,
                'https_proxy': parsed_proxy,
                })

        self.assertThat(
            import_boot_images,
            MockCalledOnceWith(
                [], http_proxy=proxy, https_proxy=proxy))


class TestClusterProtocol_IsImportBootImagesRunning(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_is_import_boot_images_running_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.IsImportBootImagesRunning.commandName)
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_is_import_boot_images_running_returns_False(self):
        mock_is_running = self.patch(
            clusterservice, "is_import_boot_images_running")
        mock_is_running.return_value = False
        response = yield call_responder(
            Cluster(), cluster.IsImportBootImagesRunning, {})
        self.assertEqual({"running": False}, response)

    @inlineCallbacks
    def test_is_import_boot_images_running_returns_True(self):
        mock_is_running = self.patch(
            clusterservice, "is_import_boot_images_running")
        mock_is_running.return_value = True
        response = yield call_responder(
            Cluster(), cluster.IsImportBootImagesRunning, {})
        self.assertEqual({"running": True}, response)


class TestClusterProtocol_DescribePowerTypes(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_describe_power_types_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.DescribePowerTypes.commandName)
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_describe_power_types_returns_jsonized_power_parameters(self):

        response = yield call_responder(
            Cluster(), cluster.DescribePowerTypes, {})

        self.assertThat(response, KeysEqual("power_types"))
        self.assertItemsEqual(
            JSON_POWER_TYPE_PARAMETERS, response["power_types"])


class TestPatchedURI(MAASTestCase):

    def test__parses_URL_with_hostname(self):
        hostname = factory.make_name('host').encode('ascii')
        path = factory.make_name('path').encode('ascii')
        uri = PatchedURI.fromBytes(b'http://%s/%s' % (hostname, path))
        self.expectThat(uri.host, Equals(hostname))
        self.expectThat(uri.path, Equals('/%s' % path))
        self.expectThat(uri.port, Equals(80))

    def test__parses_URL_with_hostname_and_port(self):
        hostname = factory.make_name('host').encode('ascii')
        port = factory.pick_port()
        path = factory.make_name('path').encode('ascii')
        uri = PatchedURI.fromBytes(b'http://%s:%d/%s' % (hostname, port, path))
        self.expectThat(uri.host, Equals(hostname))
        self.expectThat(uri.path, Equals('/%s' % path))
        self.expectThat(uri.port, Equals(port))

    def test__parses_URL_with_IPv4_address(self):
        ip = factory.make_ipv4_address().encode('ascii')
        path = factory.make_name('path').encode('ascii')
        uri = PatchedURI.fromBytes(b'http://%s/%s' % (ip, path))
        self.expectThat(uri.host, Equals(ip.encode('ascii')))
        self.expectThat(uri.path, Equals('/%s' % path))
        self.expectThat(uri.port, Equals(80))

    def test__parses_URL_with_IPv4_address_and_port(self):
        ip = factory.make_ipv4_address().encode('ascii')
        port = factory.pick_port()
        path = factory.make_name('path').encode('ascii')
        uri = PatchedURI.fromBytes(b'http://%s:%d/%s' % (ip, port, path))
        self.expectThat(uri.host, Equals(ip))
        self.expectThat(uri.path, Equals('/%s' % path))
        self.expectThat(uri.port, Equals(port))

    def test__parses_URL_with_IPv6_address(self):
        ip = factory.make_ipv6_address().encode('ascii')
        path = factory.make_name('path').encode('ascii')
        uri = PatchedURI.fromBytes(b'http://[%s]/%s' % (ip, path))
        self.expectThat(uri.host, Equals(b'%s' % ip))
        self.expectThat(uri.path, Equals(b'/%s' % path))
        self.expectThat(uri.port, Equals(80))

    def test__parses_URL_with_IPv6_address_and_port(self):
        ip = factory.make_ipv6_address().encode('ascii')
        port = factory.pick_port()
        path = factory.make_name('path').encode('ascii')
        uri = PatchedURI.fromBytes(b'http://[%s]:%d/%s' % (ip, port, path))
        self.expectThat(uri.host, Equals(b'%s' % ip))
        self.expectThat(uri.path, Equals(b'/%s' % path))
        self.expectThat(uri.port, Equals(port))


class TestClusterClientService(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

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
        dump = logger.dump()
        self.assertIn(
            "Region not available: Connection was refused by other side.",
            dump)
        self.assertIn(
            "While requesting RPC info at %s" % sentinel.rpc_info_url, dump)

    def test__get_rpc_info_accepts_IPv6_url(self):
        connect_tcp = self.patch_autospec(reactor, 'connectTCP')
        url = factory.make_url(
            scheme='http', netloc='[%s]' % factory.make_ipv6_address())
        ClusterClientService(Clock())._fetch_rpc_info(url.encode('ascii'))
        self.assertThat(connect_tcp, MockCalledOnceWith(ANY, ANY, ANY))

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

    @inlineCallbacks
    def test__update_only_updates_interval_when_eventloops_are_unknown(self):
        service = ClusterClientService(Clock())
        self.patch_autospec(service, "_get_rpc_info_url")
        self.patch_autospec(service, "_fetch_rpc_info")
        self.patch_autospec(service, "_update_connections")
        # Return a token from _get_rpc_info_url.
        service._get_rpc_info_url.return_value = sentinel.info_url
        # Return None instead of a list of event-loop endpoints. This is the
        # response that the region will give when the advertising service is
        # not running.
        service._fetch_rpc_info.return_value = {"eventloops": None}
        # Set the step to a bogus value so we can see it change.
        service.step = sentinel.unset

        logger = self.useFixture(TwistedLoggerFixture())

        yield service.startService()

        self.assertThat(service._update_connections, MockNotCalled())
        self.assertThat(service.step, Equals(service.INTERVAL_LOW))
        self.assertEqual(
            "Region is not advertising RPC endpoints.", logger.dump())

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
            "time_running": 0,
            "num_eventloops": None,
            "num_connections": None,
            "expected": ClusterClientService.INTERVAL_LOW,
        }),
        ("shortly-after-start", {
            "time_running": 10,
            "num_eventloops": 1,  # same as num_connections.
            "num_connections": 1,  # same as num_eventloops.
            "expected": ClusterClientService.INTERVAL_LOW,
        }),
        ("no-event-loops", {
            "time_running": 1000,
            "num_eventloops": 0,
            "num_connections": sentinel.undefined,
            "expected": ClusterClientService.INTERVAL_LOW,
        }),
        ("no-connections", {
            "time_running": 1000,
            "num_eventloops": 1,  # anything > 1.
            "num_connections": 0,
            "expected": ClusterClientService.INTERVAL_LOW,
        }),
        ("fewer-connections-than-event-loops", {
            "time_running": 1000,
            "num_eventloops": 2,  # anything > num_connections.
            "num_connections": 1,  # anything > 0.
            "expected": ClusterClientService.INTERVAL_MID,
        }),
        ("default", {
            "time_running": 1000,
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
        service.clock.advance(self.time_running)
        self.assertEqual(
            self.expected, service._calculate_interval(
                self.num_eventloops, self.num_connections))


class TestClusterClient(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def setUp(self):
        super(TestClusterClient, self).setUp()
        self.useFixture(EnvironmentVariable(
            "MAAS_URL", factory.make_simple_http_url()))
        self.useFixture(EnvironmentVariable(
            "CLUSTER_UUID", factory.make_UUID().encode("ascii")))

    def make_running_client(self):
        client = clusterservice.ClusterClient(
            address=("example.com", 1234), eventloop="eventloop:pid=12345",
            service=ClusterClientService(Clock()))
        client.service.running = True
        return client

    def patch_authenticate_for_success(self, client):
        authenticate = self.patch_autospec(client, "authenticateRegion")
        authenticate.side_effect = always_succeed_with(True)

    def patch_authenticate_for_failure(self, client):
        authenticate = self.patch_autospec(client, "authenticateRegion")
        authenticate.side_effect = always_succeed_with(False)

    def patch_authenticate_for_error(self, client, exception):
        authenticate = self.patch_autospec(client, "authenticateRegion")
        authenticate.side_effect = always_fail_with(exception)

    def patch_register_for_success(self, client):
        register = self.patch_autospec(client, "registerWithRegion")
        register.side_effect = always_succeed_with(True)

    def patch_register_for_failure(self, client):
        register = self.patch_autospec(client, "registerWithRegion")
        register.side_effect = always_succeed_with(False)

    def patch_register_for_error(self, client, exception):
        register = self.patch_autospec(client, "registerWithRegion")
        register.side_effect = always_fail_with(exception)

    def test_interfaces(self):
        client = self.make_running_client()
        # transport.getHandle() is used by AMP._getPeerCertificate, which we
        # call indirectly via the peerCertificate attribute in IConnection.
        self.patch(client, "transport")
        verifyObject(IConnection, client)

    def test_ident(self):
        client = self.make_running_client()
        client.eventloop = self.getUniqueString()
        self.assertThat(client.ident, Equals(client.eventloop))

    def test_connecting(self):
        client = self.make_running_client()
        self.patch_authenticate_for_success(client)
        self.patch_register_for_success(client)
        self.assertEqual(client.service.connections, {})
        wait_for_authenticated = client.authenticated.get()
        self.assertThat(wait_for_authenticated, IsUnfiredDeferred())
        wait_for_ready = client.ready.get()
        self.assertThat(wait_for_ready, IsUnfiredDeferred())
        client.connectionMade()
        # authenticated has been set to True, denoting a successfully
        # authenticated region.
        self.assertTrue(extract_result(wait_for_authenticated))
        # ready has been set with the name of the event-loop.
        self.assertEqual(client.eventloop, extract_result(wait_for_ready))
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

        # authenticated was set to None to signify that authentication was not
        # attempted.
        self.assertIsNone(extract_result(client.authenticated.get()))
        # ready was set with KeyError to signify that a connection to the
        # same event-loop already existed.
        self.assertRaises(KeyError, extract_result, client.ready.get())

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

        # authenticated was set to None to signify that authentication was not
        # attempted.
        self.assertIsNone(extract_result(client.authenticated.get()))
        # ready was set with RuntimeError to signify that the client
        # service was not running.
        self.assertRaises(RuntimeError, extract_result, client.ready.get())

        # The connections list is unchanged because the new connection
        # immediately disconnects.
        self.assertEqual(client.service.connections, {})
        self.assertFalse(client.connected)

    def test_disconnects_when_authentication_fails(self):
        client = self.make_running_client()
        self.patch_authenticate_for_failure(client)
        self.patch_register_for_success(client)

        # Connect via an in-memory transport.
        transport = StringTransportWithDisconnection()
        transport.protocol = client
        client.makeConnection(transport)

        # authenticated was set to False.
        self.assertIs(False, extract_result(client.authenticated.get()))
        # ready was set with AuthenticationFailed.
        self.assertRaises(
            exceptions.AuthenticationFailed, extract_result,
            client.ready.get())

        # The connections list is unchanged because the new connection
        # immediately disconnects.
        self.assertEqual(client.service.connections, {})
        self.assertFalse(client.connected)

    def test_disconnects_when_authentication_errors(self):
        client = self.make_running_client()
        exception_type = factory.make_exception_type()
        self.patch_authenticate_for_error(client, exception_type())
        self.patch_register_for_success(client)

        logger = self.useFixture(TwistedLoggerFixture())

        # Connect via an in-memory transport.
        transport = StringTransportWithDisconnection()
        transport.protocol = client
        client.makeConnection(transport)

        # authenticated errbacks with the error.
        self.assertRaises(
            exception_type, extract_result, client.authenticated.get())
        # ready also errbacks with the same error.
        self.assertRaises(
            exception_type, extract_result, client.ready.get())

        # The log was written to.
        self.assertDocTestMatches(
            """...
            Event-loop 'eventloop:pid=12345' handshake failed;
            dropping connection.
            Traceback (most recent call last):...
            """,
            logger.dump())

        # The connections list is unchanged because the new connection
        # immediately disconnects.
        self.assertEqual(client.service.connections, {})
        self.assertFalse(client.connected)

    def test_disconnects_when_registration_fails(self):
        client = self.make_running_client()
        self.patch_authenticate_for_success(client)
        self.patch_register_for_failure(client)

        # Connect via an in-memory transport.
        transport = StringTransportWithDisconnection()
        transport.protocol = client
        client.makeConnection(transport)

        # authenticated was set to True because it succeeded.
        self.assertIs(True, extract_result(client.authenticated.get()))
        # ready was set with AuthenticationFailed.
        self.assertRaises(
            exceptions.RegistrationFailed, extract_result,
            client.ready.get())

        # The connections list is unchanged because the new connection
        # immediately disconnects.
        self.assertEqual(client.service.connections, {})
        self.assertFalse(client.connected)

    def test_disconnects_when_registration_errors(self):
        client = self.make_running_client()
        exception_type = factory.make_exception_type()
        self.patch_authenticate_for_success(client)
        self.patch_register_for_error(client, exception_type())

        logger = self.useFixture(TwistedLoggerFixture())

        # Connect via an in-memory transport.
        transport = StringTransportWithDisconnection()
        transport.protocol = client
        client.makeConnection(transport)

        # authenticated was set to True because it succeeded.
        self.assertIs(True, extract_result(client.authenticated.get()))
        # ready was set with the exception we made.
        self.assertRaises(exception_type, extract_result, client.ready.get())

        # The log was written to.
        self.assertDocTestMatches(
            """...
            Event-loop 'eventloop:pid=12345' handshake failed;
            dropping connection.
            Traceback (most recent call last):...
            """,
            logger.dump())

        # The connections list is unchanged because the new connection
        # immediately disconnects.
        self.assertEqual(client.service.connections, {})
        self.assertFalse(client.connected)

    def test_handshakeFailed_does_not_log_when_connection_is_closed(self):
        client = self.make_running_client()
        with TwistedLoggerFixture() as logger:
            client.handshakeFailed(Failure(ConnectionClosed()))
        # ready was set with ConnectionClosed.
        self.assertRaises(
            ConnectionClosed, extract_result,
            client.ready.get())
        # Nothing was logged.
        self.assertEqual("", logger.output)

    @inlineCallbacks
    def test_secureConnection_calls_StartTLS_and_Identify(self):
        client = self.make_running_client()

        callRemote = self.patch(client, "callRemote")
        callRemote_return_values = [
            {},  # In response to a StartTLS call.
            {"ident": client.eventloop},  # Identify.
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
        callRemote.side_effect = [
            {},  # In response to a StartTLS call.
            {"ident": "bogus-name"},  # Identify.
        ]

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

    @skip(
        "XXX: blake_r 2015-02-26 bug=1426089: Failing because of an "
        "unknown reason.")
    @inlineCallbacks
    def test_secureConnection_end_to_end(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop()
        self.addCleanup((yield connecting))
        client = yield getRegionClient()
        # XXX: Expose secureConnection() in the client.
        yield client._conn.secureConnection()
        self.assertTrue(client.isSecure())

    def test_authenticateRegion_accepts_matching_digests(self):
        client = self.make_running_client()

        def calculate_digest(_, message):
            # Use the cluster's own authentication responder.
            response = Cluster().authenticate(message)
            return succeed(response)

        callRemote = self.patch_autospec(client, "callRemote")
        callRemote.side_effect = calculate_digest

        d = client.authenticateRegion()
        self.assertTrue(extract_result(d))

    def test_authenticateRegion_rejects_non_matching_digests(self):
        client = self.make_running_client()

        def calculate_digest(_, message):
            # Return some nonsense.
            response = {
                "digest": factory.make_bytes(),
                "salt": factory.make_bytes(),
            }
            return succeed(response)

        callRemote = self.patch_autospec(client, "callRemote")
        callRemote.side_effect = calculate_digest

        d = client.authenticateRegion()
        self.assertFalse(extract_result(d))

    def test_authenticateRegion_propagates_errors(self):
        client = self.make_running_client()
        exception_type = factory.make_exception_type()

        callRemote = self.patch_autospec(client, "callRemote")
        callRemote.return_value = fail(exception_type())

        d = client.authenticateRegion()
        self.assertRaises(exception_type, extract_result, d)

    @inlineCallbacks
    def test_authenticateRegion_end_to_end(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop()
        self.addCleanup((yield connecting))
        yield getRegionClient()
        self.assertThat(
            protocol.Authenticate,
            MockCalledOnceWith(protocol, message=ANY))

    def test_registerWithRegion_returns_True_when_accepted(self):
        client = self.make_running_client()

        callRemote = self.patch_autospec(client, "callRemote")
        callRemote.side_effect = always_succeed_with({})

        logger = self.useFixture(TwistedLoggerFixture())

        d = client.registerWithRegion()
        self.assertTrue(extract_result(d))

        self.assertDocTestMatches(
            "Cluster '...' registered (via ...).",
            logger.output)

    def test_registerWithRegion_returns_False_when_rejected(self):
        client = self.make_running_client()

        callRemote = self.patch_autospec(client, "callRemote")
        callRemote.return_value = fail(exceptions.CannotRegisterCluster())

        logger = self.useFixture(TwistedLoggerFixture())

        d = client.registerWithRegion()
        self.assertFalse(extract_result(d))

        self.assertDocTestMatches(
            "Cluster '...' REJECTED by the region (via ...).",
            logger.output)

    def test_registerWithRegion_propagates_errors(self):
        client = self.make_running_client()
        exception_type = factory.make_exception_type()

        callRemote = self.patch_autospec(client, "callRemote")
        callRemote.return_value = fail(exception_type())

        d = client.registerWithRegion()
        self.assertRaises(exception_type, extract_result, d)

    @inlineCallbacks
    def test_registerWithRegion_end_to_end(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop()
        self.addCleanup((yield connecting))
        yield getRegionClient()
        self.assertThat(
            protocol.Register, MockCalledOnceWith(
                protocol, uuid=get_cluster_uuid(),
                networks=discover_networks(),
                url=urlparse(get_maas_url())))


class TestClusterProtocol_ListSupportedArchitectures(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.ListSupportedArchitectures.commandName)
        self.assertIsNotNone(responder)

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

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.ListOperatingSystems.commandName)
        self.assertIsNotNone(responder)

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


class TestClusterProtocol_GetOSReleaseTitle(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.GetOSReleaseTitle.commandName)
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_calls_get_os_release_title(self):
        title = factory.make_name('title')
        get_os_release_title = self.patch(
            clusterservice, "get_os_release_title")
        get_os_release_title.return_value = title
        arguments = {
            "osystem": factory.make_name("osystem"),
            "release": factory.make_name("release"),
        }
        observed = yield call_responder(
            Cluster(), cluster.GetOSReleaseTitle, arguments)
        expected = {"title": title}
        self.assertEqual(expected, observed)
        # The arguments are passed to the responder positionally.
        self.assertThat(get_os_release_title, MockCalledOnceWith(
            arguments["osystem"], arguments["release"]))

    @inlineCallbacks
    def test_exception_when_os_does_not_exist(self):
        # A remote NoSuchOperatingSystem exception is re-raised locally.
        get_os_release_title = self.patch(
            clusterservice, "get_os_release_title")
        get_os_release_title.side_effect = exceptions.NoSuchOperatingSystem()
        arguments = {
            "osystem": factory.make_name("osystem"),
            "release": factory.make_name("release"),
        }
        with ExpectedException(exceptions.NoSuchOperatingSystem):
            yield call_responder(
                Cluster(), cluster.GetOSReleaseTitle, arguments)


class TestClusterProtocol_ValidateLicenseKey(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.ValidateLicenseKey.commandName)
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_calls_validate_license_key(self):
        validate_license_key = self.patch(
            clusterservice, "validate_license_key")
        validate_license_key.return_value = factory.pick_bool()
        arguments = {
            "osystem": factory.make_name("osystem"),
            "release": factory.make_name("release"),
            "key": factory.make_name("key"),
        }
        observed = yield call_responder(
            Cluster(), cluster.ValidateLicenseKey, arguments)
        expected = {"is_valid": validate_license_key.return_value}
        self.assertEqual(expected, observed)
        # The arguments are passed to the responder positionally.
        self.assertThat(validate_license_key, MockCalledOnceWith(
            arguments["osystem"], arguments["release"], arguments["key"]))

    @inlineCallbacks
    def test_exception_when_os_does_not_exist(self):
        # A remote NoSuchOperatingSystem exception is re-raised locally.
        validate_license_key = self.patch(
            clusterservice, "validate_license_key")
        validate_license_key.side_effect = exceptions.NoSuchOperatingSystem()
        arguments = {
            "osystem": factory.make_name("osystem"),
            "release": factory.make_name("release"),
            "key": factory.make_name("key"),
        }
        with ExpectedException(exceptions.NoSuchOperatingSystem):
            yield call_responder(
                Cluster(), cluster.ValidateLicenseKey, arguments)


class TestClusterProtocol_GetPreseedData(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def make_arguments(self):
        return {
            "osystem": factory.make_name("osystem"),
            "preseed_type": factory.make_name("preseed_type"),
            "node_system_id": factory.make_name("system_id"),
            "node_hostname": factory.make_name("hostname"),
            "consumer_key": factory.make_name("consumer_key"),
            "token_key": factory.make_name("token_key"),
            "token_secret": factory.make_name("token_secret"),
            "metadata_url": urlparse(
                "https://%s/path/to/metadata" % factory.make_hostname()),
        }

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.GetPreseedData.commandName)
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_calls_get_preseed_data(self):
        get_preseed_data = self.patch(clusterservice, "get_preseed_data")
        get_preseed_data.return_value = factory.make_name("data")
        arguments = self.make_arguments()
        observed = yield call_responder(
            Cluster(), cluster.GetPreseedData, arguments)
        expected = {"data": get_preseed_data.return_value}
        self.assertEqual(expected, observed)
        # The arguments are passed to the responder positionally.
        self.assertThat(get_preseed_data, MockCalledOnceWith(
            arguments["osystem"], arguments["preseed_type"],
            arguments["node_system_id"], arguments["node_hostname"],
            arguments["consumer_key"], arguments["token_key"],
            arguments["token_secret"], arguments["metadata_url"]))

    @inlineCallbacks
    def test_exception_when_os_does_not_exist(self):
        # A remote NoSuchOperatingSystem exception is re-raised locally.
        get_preseed_data = self.patch(
            clusterservice, "get_preseed_data")
        get_preseed_data.side_effect = exceptions.NoSuchOperatingSystem()
        arguments = self.make_arguments()
        with ExpectedException(exceptions.NoSuchOperatingSystem):
            yield call_responder(
                Cluster(), cluster.GetPreseedData, arguments)

    @inlineCallbacks
    def test_exception_when_preseed_not_implemented(self):
        # A remote NotImplementedError exception is re-raised locally.
        # Choose an operating system which has not overridden the
        # default compose_preseed.
        osystem_name = next(
            osystem_name for osystem_name, osystem in OperatingSystemRegistry
            if osystem.compose_preseed == OperatingSystem.compose_preseed)
        arguments = self.make_arguments()
        arguments["osystem"] = osystem_name
        with ExpectedException(exceptions.NoSuchOperatingSystem):
            yield call_responder(
                Cluster(), cluster.GetPreseedData, arguments)


class TestClusterProtocol_ComposeCurtinNetworkPreseed(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def make_args(self, osystem=None):
        if osystem is None:
            osystem = factory.make_name('os')
        mac = factory.make_mac_address()
        return {
            'osystem': osystem,
            'config': {
                'interfaces': [(factory.make_name('eth'), mac)],
                'auto_interfaces': [mac],
                'ips_mapping': {mac: [factory.make_ipv4_address()]},
                'gateways_mapping': {mac: [factory.make_ipv4_address()]},
                'nameservers': [],
                },
            'disable_ipv4': factory.pick_bool(),
            }

    def test__is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.ComposeCurtinNetworkPreseed.commandName)
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test__calls_compose_curtin_network_preseed(self):
        preseed = [factory.make_name('preseed')]
        fake = self.patch_autospec(
            clusterservice, 'compose_curtin_network_preseed')
        fake.return_value = preseed
        args = self.make_args()

        response = yield call_responder(
            Cluster(), cluster.ComposeCurtinNetworkPreseed, args)

        self.expectThat(response, Equals({'data': preseed}))
        self.expectThat(
            fake,
            MockCalledOnceWith(
                args['osystem'], args['config'], args['disable_ipv4']))

    @inlineCallbacks
    def test__fails_for_unknown_OS(self):
        args = self.make_args(osystem=factory.make_name('nonexistent-os'))
        with ExpectedException(exceptions.NoSuchOperatingSystem):
            yield call_responder(
                Cluster(), cluster.ComposeCurtinNetworkPreseed, args)


class TestClusterProtocol_PowerOn_PowerOff(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    scenarios = (
        ("power-on", {
            "command": cluster.PowerOn,
            "expected_power_change": "on",
        }),
        ("power-off", {
            "command": cluster.PowerOff,
            "expected_power_change": "off",
        }),
    )

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(self.command.commandName)
        self.assertIsNotNone(responder)

    def test_executes_maybe_change_power_state(self):
        maybe_change_power_state = self.patch(
            clusterservice, "maybe_change_power_state")

        system_id = factory.make_name("system_id")
        hostname = factory.make_name("hostname")
        power_type = factory.make_name("power_type")
        context = {
            factory.make_name("name"): factory.make_name("value"),
        }

        d = call_responder(Cluster(), self.command, {
            "system_id": system_id,
            "hostname": hostname,
            "power_type": power_type,
            "context": context,
        })

        def check(response):
            self.assertThat(
                maybe_change_power_state,
                MockCalledOnceWith(
                    system_id, hostname, power_type,
                    power_change=self.expected_power_change, context=context))
        return d.addCallback(check)

    def test_power_on_can_propagate_UnknownPowerType(self):
        self.patch(clusterservice, "maybe_change_power_state").side_effect = (
            UnknownPowerType)

        d = call_responder(Cluster(), self.command, {
            "system_id": "id", "hostname": "hostname", "power_type": "type",
            "context": {},
        })
        # If the call doesn't fail then we have a test failure; we're
        # *expecting* UnknownPowerType to be raised.
        d.addCallback(self.fail)

        def check(failure):
            failure.trap(UnknownPowerType)
        return d.addErrback(check)

    def test_power_on_can_propagate_NotImplementedError(self):
        self.patch(clusterservice, "maybe_change_power_state").side_effect = (
            NotImplementedError)

        d = call_responder(Cluster(), self.command, {
            "system_id": "id", "hostname": "hostname", "power_type": "type",
            "context": {},
        })
        # If the call doesn't fail then we have a test failure; we're
        # *expecting* NotImplementedError to be raised.
        d.addCallback(self.fail)

        def check(failure):
            failure.trap(NotImplementedError)
        return d.addErrback(check)

    def test_power_on_can_propagate_PowerActionFail(self):
        self.patch(clusterservice, "maybe_change_power_state").side_effect = (
            PowerActionFail)

        d = call_responder(Cluster(), self.command, {
            "system_id": "id", "hostname": "hostname", "power_type": "type",
            "context": {},
        })
        # If the call doesn't fail then we have a test failure; we're
        # *expecting* PowerActionFail to be raised.
        d.addCallback(self.fail)

        def check(failure):
            failure.trap(PowerActionFail)
        return d.addErrback(check)

    def test_power_on_can_propagate_PowerActionAlreadyInProgress(self):
        self.patch(clusterservice, "maybe_change_power_state").side_effect = (
            exceptions.PowerActionAlreadyInProgress)

        d = call_responder(Cluster(), self.command, {
            "system_id": "id", "hostname": "hostname", "power_type": "type",
            "context": {},
        })
        # If the call doesn't fail then we have a test failure; we're
        # *expecting* PowerActionFail to be raised.
        d.addCallback(self.fail)

        def check(failure):
            failure.trap(exceptions.PowerActionAlreadyInProgress)
        return d.addErrback(check)


class TestClusterProtocol_PowerQuery(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.PowerQuery.commandName)
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_returns_power_state(self):
        state = random.choice(['on', 'off'])
        power_state_update = self.patch(
            power_module, "power_state_update")
        perform_power_query = self.patch(
            power_module, "perform_power_query")
        perform_power_query.return_value = state

        arguments = {
            'system_id': factory.make_name(''),
            'hostname': factory.make_name(''),
            'power_type': random.choice(QUERY_POWER_TYPES),
            'context': factory.make_name(''),
        }
        observed = yield call_responder(
            Cluster(), cluster.PowerQuery, arguments)
        self.assertEqual({'state': state}, observed)
        self.assertThat(
            perform_power_query,
            MockCalledOnceWith(
                arguments['system_id'], arguments['hostname'],
                arguments['power_type'], arguments['context']))
        self.assertThat(
            power_state_update,
            MockCalledOnceWith(arguments['system_id'], state))


class TestClusterProtocol_ConfigureDHCP(MAASTestCase):

    scenarios = (
        ("DHCPv4", {
            "dhcp_server": (dhcp, "DHCPv4Server"),
            "command": cluster.ConfigureDHCPv4,
            "make_network": factory.make_ipv4_network,
        }),
        ("DHCPv6", {
            "dhcp_server": (dhcp, "DHCPv6Server"),
            "command": cluster.ConfigureDHCPv6,
            "make_network": factory.make_ipv6_network,
        }),
    )

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test__is_registered(self):
        self.assertIsNotNone(
            Cluster().locateResponder(self.command.commandName))

    @inlineCallbacks
    def test__executes_configure_dhcp(self):
        DHCPServer = self.patch_autospec(*self.dhcp_server)
        configure = self.patch_autospec(dhcp, "configure")

        omapi_key = factory.make_name('key')
        subnet_configs = [make_subnet_config()]

        yield call_responder(Cluster(), self.command, {
            'omapi_key': omapi_key,
            'subnet_configs': subnet_configs,
            })

        self.assertThat(DHCPServer, MockCalledOnceWith(omapi_key))
        self.assertThat(configure, MockCalledOnceWith(
            DHCPServer.return_value, subnet_configs))

    @inlineCallbacks
    def test__limits_concurrency(self):
        self.patch_autospec(*self.dhcp_server)

        def check_dhcp_locked(server, subnet_configs):
            self.assertTrue(concurrency.dhcp.locked)
            # While we're here, check this is *not* the IO thread.
            self.expectThat(isInIOThread(), Is(False))

        self.patch(dhcp, "configure", check_dhcp_locked)

        self.assertFalse(concurrency.dhcp.locked)
        yield call_responder(Cluster(), self.command, {
            'omapi_key': factory.make_name('key'),
            'subnet_configs': [],
            })
        self.assertFalse(concurrency.dhcp.locked)

    @inlineCallbacks
    def test__propagates_CannotConfigureDHCP(self):
        configure = self.patch_autospec(dhcp, "configure")
        configure.side_effect = (
            exceptions.CannotConfigureDHCP("Deliberate failure"))
        omapi_key = factory.make_name('key')
        network = self.make_network()
        ip_low, ip_high = factory.make_ip_range(network)
        subnet_configs = [make_subnet_config()]

        with ExpectedException(exceptions.CannotConfigureDHCP):
            yield call_responder(Cluster(), self.command, {
                'omapi_key': omapi_key,
                'subnet_configs': subnet_configs,
                })


class TestClusterProtocol_CreateHostMaps(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.CreateHostMaps.commandName)
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_executes_create_host_maps(self):
        create_host_maps = self.patch(clusterservice, "create_host_maps")
        mappings = [
            {"ip_address": factory.make_ipv4_address(),
             "mac_address": factory.make_mac_address()}
            for _ in range(2)
        ]
        shared_key = factory.make_name("shared_key")

        yield call_responder(Cluster(), cluster.CreateHostMaps, {
            "mappings": mappings, "shared_key": shared_key,
        })
        self.assertThat(
            create_host_maps, MockCalledOnceWith(
                mappings, shared_key))

    @inlineCallbacks
    def test__limits_concurrency(self):

        def check_dhcp_locked(mappings, shared_key):
            self.assertTrue(concurrency.dhcp.locked)
            # While we're here, check this is *not* the IO thread.
            self.expectThat(isInIOThread(), Is(False))

        self.patch(clusterservice, "create_host_maps", check_dhcp_locked)

        self.assertFalse(concurrency.dhcp.locked)
        yield call_responder(Cluster(), cluster.CreateHostMaps, {
            "mappings": {}, "shared_key": factory.make_name("key"),
        })
        self.assertFalse(concurrency.dhcp.locked)


class TestClusterProtocol_RemoveHostMaps(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.RemoveHostMaps.commandName)
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_executes_remove_host_maps(self):
        remove_host_maps = self.patch(clusterservice, "remove_host_maps")
        ip_addresses = [factory.make_ipv4_address() for _ in range(2)]
        shared_key = factory.make_name("shared_key")

        yield call_responder(Cluster(), cluster.RemoveHostMaps, {
            "ip_addresses": ip_addresses, "shared_key": shared_key,
        })
        self.assertThat(
            remove_host_maps, MockCalledOnceWith(
                ip_addresses, shared_key))

    @inlineCallbacks
    def test__limits_concurrency(self):

        def check_dhcp_locked(ip_addresses, shared_key):
            self.assertTrue(concurrency.dhcp.locked)
            # While we're here, check this is *not* the IO thread.
            self.expectThat(isInIOThread(), Is(False))

        self.patch(clusterservice, "remove_host_maps", check_dhcp_locked)

        self.assertFalse(concurrency.dhcp.locked)
        yield call_responder(Cluster(), cluster.RemoveHostMaps, {
            "ip_addresses": [], "shared_key": factory.make_name("key"),
        })
        self.assertFalse(concurrency.dhcp.locked)


class TestClusterProtocol_StartMonitors(MAASTestCase):

    def test__is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.StartMonitors.commandName)
        self.assertIsNotNone(responder)

    def test__executes_start_monitors(self):
        deadline = datetime.now(amp.utc) + timedelta(seconds=10)
        monitors = [{
            "deadline": deadline, "context": factory.make_name("ctx"),
            "id": factory.make_name("id")}]
        d = call_responder(
            Cluster(), cluster.StartMonitors, {"monitors": monitors})
        self.addCleanup(cancel_monitor, monitors[0]["id"])
        self.assertTrue(d.called)
        self.assertThat(running_monitors, Contains(monitors[0]["id"]))


class TestClusterProtocol_CancelMonitor(MAASTestCase):

    def test__is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.CancelMonitor.commandName)
        self.assertIsNotNone(responder)

    def test__executes_cancel_monitor(self):
        deadline = datetime.now(amp.utc) + timedelta(seconds=10)
        monitors = [{
            "deadline": deadline, "context": factory.make_name("ctx"),
            "id": factory.make_name("id")}]
        call_responder(
            Cluster(), cluster.StartMonitors, {"monitors": monitors})

        call_responder(
            Cluster(), cluster.CancelMonitor, {"id": monitors[0]["id"]})
        self.assertThat(running_monitors, Not(Contains(monitors[0]["id"])))


class TestClusterProtocol_EvaluateTag(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test__is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.EvaluateTag.commandName)
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_happy_path(self):
        get_maas_url = self.patch_autospec(tags, "get_maas_url")
        get_maas_url.return_value = sentinel.maas_url
        get_cluster_uuid = self.patch_autospec(tags, "get_cluster_uuid")
        get_cluster_uuid.return_value = sentinel.cluster_uuid

        # Prevent real work being done, which would involve HTTP calls.
        self.patch_autospec(tags, "process_node_tags")

        response = yield call_responder(
            Cluster(), cluster.EvaluateTag, {
                "tag_name": "all-nodes",
                "tag_definition": "//*",
                "tag_nsmap": [
                    {"prefix": "foo",
                     "uri": "http://foo.example.com/"},
                ],
                "credentials": "abc:def:ghi",
            })

        self.assertEqual({}, response)

    @inlineCallbacks
    def test__calls_through_to_evaluate_tag_helper(self):
        evaluate_tag = self.patch_autospec(clusterservice, "evaluate_tag")

        tag_name = factory.make_name("tag-name")
        tag_definition = factory.make_name("tag-definition")
        tag_ns_prefix = factory.make_name("tag-ns-prefix")
        tag_ns_uri = factory.make_name("tag-ns-uri")

        consumer_key = factory.make_name("ckey")
        resource_token = factory.make_name("rtok")
        resource_secret = factory.make_name("rsec")
        credentials = convert_tuple_to_string(
            (consumer_key, resource_token, resource_secret))

        yield call_responder(
            Cluster(), cluster.EvaluateTag, {
                "tag_name": tag_name,
                "tag_definition": tag_definition,
                "tag_nsmap": [
                    {"prefix": tag_ns_prefix, "uri": tag_ns_uri},
                ],
                "credentials": credentials,
            })

        self.assertThat(evaluate_tag, MockCalledOnceWith(
            tag_name, tag_definition, {tag_ns_prefix: tag_ns_uri},
            (consumer_key, resource_token, resource_secret),
        ))


class TestClusterProtocol_AddVirsh(MAASTestCase):

    def test__is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.AddVirsh.commandName)
        self.assertIsNotNone(responder)

    def test__calls_deferToThread_with_probe_virsh_and_enlist(self):
        mock_deferToThread = self.patch_autospec(
            clusterservice, 'deferToThread')
        user = factory.make_name('user')
        poweraddr = factory.make_name('poweraddr')
        password = factory.make_name('password')
        prefix_filter = factory.make_name('prefix_filter')
        call_responder(Cluster(), cluster.AddVirsh, {
            "user": user,
            "poweraddr": poweraddr,
            "password": password,
            "prefix_filter": prefix_filter,
            "accept_all": True,
            })
        self.assertThat(
            mock_deferToThread, MockCalledOnceWith(
                clusterservice.probe_virsh_and_enlist,
                user, poweraddr, password, prefix_filter, True))

    def test__password_is_optional(self):
        mock_deferToThread = self.patch_autospec(
            clusterservice, 'deferToThread')
        user = factory.make_name('user')
        poweraddr = factory.make_name('poweraddr')
        prefix_filter = factory.make_name('prefix_filter')
        call_responder(Cluster(), cluster.AddVirsh, {
            "user": user,
            "poweraddr": poweraddr,
            "password": None,
            "prefix_filter": prefix_filter,
            "accept_all": True,
            })
        self.assertThat(
            mock_deferToThread, MockCalledOnceWith(
                clusterservice.probe_virsh_and_enlist,
                user, poweraddr, None, prefix_filter, True))

    def test__can_be_called_without_password_key(self):
        mock_deferToThread = self.patch_autospec(
            clusterservice, 'deferToThread')
        user = factory.make_name('user')
        poweraddr = factory.make_name('poweraddr')
        prefix_filter = factory.make_name('prefix_filter')
        call_responder(Cluster(), cluster.AddVirsh, {
            "user": user,
            "poweraddr": poweraddr,
            "prefix_filter": prefix_filter,
            "accept_all": True,
            })
        self.assertThat(
            mock_deferToThread, MockCalledOnceWith(
                clusterservice.probe_virsh_and_enlist,
                user, poweraddr, None, prefix_filter, True))

    def test__logs_error_to_maaslog(self):
        fake_error = factory.make_name('error')
        self.patch(clusterservice, 'maaslog')
        mock_deferToThread = self.patch_autospec(
            clusterservice, 'deferToThread')
        mock_deferToThread.return_value = fail(Exception(fake_error))
        user = factory.make_name('user')
        poweraddr = factory.make_name('poweraddr')
        password = factory.make_name('password')
        prefix_filter = factory.make_name('prefix_filter')
        call_responder(Cluster(), cluster.AddVirsh, {
            "user": user,
            "poweraddr": poweraddr,
            "password": password,
            "prefix_filter": prefix_filter,
            "accept_all": True,
            })
        self.assertThat(
            clusterservice.maaslog.error,
            MockAnyCall(
                "Failed to probe and enlist %s nodes: %s",
                "virsh", fake_error))


class TestClusterProtocol_AddESXi(MAASTestCase):

    def test__is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.AddESXi.commandName)
        self.assertIsNotNone(responder)

    def test__calls_deferToThread_with_probe_esxi_and_enlist(self):
        mock_deferToThread = self.patch_autospec(
            clusterservice, 'deferToThread')
        user = factory.make_name('user')
        poweraddr = factory.make_name('poweraddr')
        password = factory.make_name('password')
        prefix_filter = factory.make_name('prefix_filter')
        call_responder(Cluster(), cluster.AddESXi, {
            "user": user,
            "poweraddr": poweraddr,
            "password": password,
            "prefix_filter": prefix_filter,
            "accept_all": True,
            })
        self.assertThat(
            mock_deferToThread, MockCalledOnceWith(
                clusterservice.probe_esxi_and_enlist,
                user, poweraddr, password, prefix_filter, True))

    def test__logs_error_to_maaslog(self):
        fake_error = factory.make_name('error')
        self.patch(clusterservice, 'maaslog')
        mock_deferToThread = self.patch_autospec(
            clusterservice, 'deferToThread')
        mock_deferToThread.return_value = fail(Exception(fake_error))
        user = factory.make_name('user')
        poweraddr = factory.make_name('poweraddr')
        password = factory.make_name('password')
        prefix_filter = factory.make_name('prefix_filter')
        call_responder(Cluster(), cluster.AddESXi, {
            "user": user,
            "poweraddr": poweraddr,
            "password": password,
            "prefix_filter": prefix_filter,
            "accept_all": True,
            })
        self.assertThat(
            clusterservice.maaslog.error,
            MockAnyCall(
                "Failed to probe and enlist %s nodes: %s",
                "esxi", fake_error))


class TestClusterProtocol_AddSeaMicro15k(MAASTestCase):

    def test__is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.AddSeaMicro15k.commandName)
        self.assertIsNotNone(responder)

    def test__calls_find_ip_via_arp(self):
        # Prevent any actual probing from happing.
        self.patch_autospec(
            clusterservice, 'deferToThread')
        find_ip_via_arp = self.patch_autospec(
            clusterservice, 'find_ip_via_arp')
        find_ip_via_arp.return_value = factory.make_ipv4_address()

        user = factory.make_name('user')
        mac = factory.make_mac_address()
        username = factory.make_name('user')
        password = factory.make_name('password')
        power_control = factory.make_name('power_control')
        call_responder(Cluster(), cluster.AddSeaMicro15k, {
            "user": user,
            "mac": mac,
            "username": username,
            "password": password,
            "power_control": power_control,
            "accept_all": True,
            })

        self.assertThat(
            find_ip_via_arp, MockCalledOnceWith(mac))

    @inlineCallbacks
    def test__raises_and_logs_warning_if_no_ip_found_for_mac(self):
        maaslog = self.patch(clusterservice, 'maaslog')
        find_ip_via_arp = self.patch_autospec(
            clusterservice, 'find_ip_via_arp')
        find_ip_via_arp.return_value = None

        user = factory.make_name('user')
        mac = factory.make_mac_address()
        username = factory.make_name('user')
        password = factory.make_name('password')
        power_control = factory.make_name('power_control')

        with ExpectedException(exceptions.NoIPFoundForMACAddress):
            yield call_responder(Cluster(), cluster.AddSeaMicro15k, {
                "user": user,
                "mac": mac,
                "username": username,
                "password": password,
                "power_control": power_control,
                "accept_all": True,
                })

        self.assertThat(
            maaslog.warning,
            MockCalledOnceWith(
                "Couldn't find IP address for MAC %s" % mac))

    def test__calls_deferToThread_with_probe_seamicro15k_and_enlist(self):
        mock_deferToThread = self.patch_autospec(
            clusterservice, 'deferToThread')
        find_ip_via_arp = self.patch_autospec(
            clusterservice, 'find_ip_via_arp')
        find_ip_via_arp.return_value = factory.make_ipv4_address()

        user = factory.make_name('user')
        mac = factory.make_mac_address()
        username = factory.make_name('user')
        password = factory.make_name('password')
        power_control = factory.make_name('power_control')
        call_responder(Cluster(), cluster.AddSeaMicro15k, {
            "user": user,
            "mac": mac,
            "username": username,
            "password": password,
            "power_control": power_control,
            "accept_all": True,
            })

        self.assertThat(
            mock_deferToThread, MockCalledOnceWith(
                clusterservice.probe_seamicro15k_and_enlist,
                user, find_ip_via_arp.return_value, username,
                password, power_control=power_control, accept_all=True))

    def test__logs_error_to_maaslog(self):
        fake_error = factory.make_name('error')
        self.patch(clusterservice, 'maaslog')
        mock_deferToThread = self.patch_autospec(
            clusterservice, 'deferToThread')
        mock_deferToThread.return_value = fail(Exception(fake_error))
        find_ip_via_arp = self.patch_autospec(
            clusterservice, 'find_ip_via_arp')
        find_ip_via_arp.return_value = factory.make_ipv4_address()

        user = factory.make_name('user')
        mac = factory.make_mac_address()
        username = factory.make_name('user')
        password = factory.make_name('password')
        power_control = factory.make_name('power_control')
        call_responder(Cluster(), cluster.AddSeaMicro15k, {
            "user": user,
            "mac": mac,
            "username": username,
            "password": password,
            "power_control": power_control,
            "accept_all": True,
            })
        self.assertThat(
            clusterservice.maaslog.error,
            MockAnyCall(
                "Failed to probe and enlist %s nodes: %s",
                "SeaMicro 15000", fake_error))


class TestClusterProtocol_EnlistNodesFromMSCM(MAASTestCase):

    def test__is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.EnlistNodesFromMSCM.commandName)
        self.assertIsNotNone(responder)

    def test__deferToThread_with_probe_and_enlist_mscm(self):
        mock_deferToThread = self.patch_autospec(
            clusterservice, 'deferToThread')

        user = factory.make_name('user')
        host = factory.make_name('host')
        username = factory.make_name('user')
        password = factory.make_name('password')

        call_responder(Cluster(), cluster.EnlistNodesFromMSCM, {
            "user": user,
            "host": host,
            "username": username,
            "password": password,
            "accept_all": True,
        })

        self.assertThat(
            mock_deferToThread, MockCalledOnceWith(
                clusterservice.probe_and_enlist_mscm,
                user, host, username, password, True))

    def test__logs_error_to_maaslog(self):
        fake_error = factory.make_name('error')
        self.patch(clusterservice, 'maaslog')
        mock_deferToThread = self.patch_autospec(
            clusterservice, 'deferToThread')
        mock_deferToThread.return_value = fail(Exception(fake_error))
        user = factory.make_name('user')
        host = factory.make_name('host')
        username = factory.make_name('user')
        password = factory.make_name('password')

        call_responder(Cluster(), cluster.EnlistNodesFromMSCM, {
            "user": user,
            "host": host,
            "username": username,
            "password": password,
            "accept_all": True,
        })
        self.assertThat(
            clusterservice.maaslog.error,
            MockAnyCall(
                "Failed to probe and enlist %s nodes: %s",
                "Moonshot", fake_error))


class TestClusterProtocol_EnlistNodesFromUCSM(MAASTestCase):

    def test__is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.EnlistNodesFromUCSM.commandName)
        self.assertIsNotNone(responder)

    def test__calls_deferToThread_with_probe_and_enlist_ucsm(self):
        mock_deferToThread = self.patch_autospec(
            clusterservice, 'deferToThread')

        user = factory.make_name('user')
        url = factory.make_url()
        username = factory.make_name('user')
        password = factory.make_name('password')

        call_responder(Cluster(), cluster.EnlistNodesFromUCSM, {
            "user": user,
            "url": url,
            "username": username,
            "password": password,
            "accept_all": True,
        })

        self.assertThat(
            mock_deferToThread, MockCalledOnceWith(
                clusterservice.probe_and_enlist_ucsm,
                user, url, username, password, True))

    def test__logs_error_to_maaslog(self):
        fake_error = factory.make_name('error')
        self.patch(clusterservice, 'maaslog')
        mock_deferToThread = self.patch_autospec(
            clusterservice, 'deferToThread')
        mock_deferToThread.return_value = fail(Exception(fake_error))
        user = factory.make_name('user')
        url = factory.make_url()
        username = factory.make_name('user')
        password = factory.make_name('password')

        call_responder(Cluster(), cluster.EnlistNodesFromUCSM, {
            "user": user,
            "url": url,
            "username": username,
            "password": password,
            "accept_all": True,
        })
        self.assertThat(
            clusterservice.maaslog.error,
            MockAnyCall(
                "Failed to probe and enlist %s nodes: %s",
                "UCS", fake_error))


class TestClusterProtocol_EnlistNodesFromMicrosoftOCS(MAASTestCase):

    def test__is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.EnlistNodesFromMicrosoftOCS.commandName)
        self.assertIsNotNone(responder)

    def test__defers_probe_and_enlist_msftocs_to_thread(self):
        mock_deferToThread = self.patch_autospec(
            clusterservice, 'deferToThread')

        user = factory.make_name('user')
        ip = factory.make_ipv4_address()
        port = '%d' % randint(2000, 4000)
        username = factory.make_name('user')
        password = factory.make_name('password')

        call_responder(Cluster(), cluster.EnlistNodesFromMicrosoftOCS, {
            "user": user,
            "ip": ip,
            "port": port,
            "username": username,
            "password": password,
            "accept_all": True,
        })

        self.assertThat(
            mock_deferToThread, MockCalledOnceWith(
                clusterservice.probe_and_enlist_msftocs,
                user, ip, port, username, password, True))

    def test__logs_error_to_maaslog(self):
        fake_error = factory.make_name('error')
        self.patch(clusterservice, 'maaslog')
        mock_deferToThread = self.patch_autospec(
            clusterservice, 'deferToThread')
        mock_deferToThread.return_value = fail(Exception(fake_error))
        user = factory.make_name('user')
        ip = factory.make_ipv4_address()
        port = '%d' % randint(2000, 4000)
        username = factory.make_name('user')
        password = factory.make_name('password')

        call_responder(Cluster(), cluster.EnlistNodesFromMicrosoftOCS, {
            "user": user,
            "ip": ip,
            "port": port,
            "username": username,
            "password": password,
            "accept_all": True,
        })
        self.assertThat(
            clusterservice.maaslog.error,
            MockAnyCall(
                "Failed to probe and enlist %s nodes: %s",
                "MicrosoftOCS", fake_error))
