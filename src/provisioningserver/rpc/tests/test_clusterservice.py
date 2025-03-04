# Copyright 2014-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from hashlib import sha256
from hmac import HMAC
import json
import os
from pathlib import Path
import random
import socket
from unittest import TestCase
from unittest.mock import ANY, call, MagicMock, Mock, sentinel
from urllib.parse import urlparse

from fixtures import TempDir
from netaddr import IPNetwork
from twisted import web
from twisted.application.internet import TimerService
from twisted.internet import error, reactor
from twisted.internet.defer import Deferred, fail, inlineCallbacks, succeed
from twisted.internet.error import ConnectionClosed
from twisted.internet.task import Clock
from twisted.internet.testing import StringTransportWithDisconnection
from twisted.python.failure import Failure
from twisted.web.client import Headers
from zope.interface.verify import verifyObject

from apiclient.utils import ascii_url
from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from maastesting.twisted import (
    always_fail_with,
    always_succeed_with,
    extract_result,
    TwistedLoggerFixture,
)
from provisioningserver.certificates import (
    Certificate,
    CertificateRequest,
    get_maas_cluster_cert_paths,
)
from provisioningserver.drivers.pod import (
    DiscoveredMachine,
    DiscoveredPod,
    DiscoveredPodHints,
    DiscoveredPodProject,
    RequestedMachine,
    RequestedMachineBlockDevice,
    RequestedMachineInterface,
)
from provisioningserver.drivers.power import PowerError
from provisioningserver.drivers.power.registry import PowerDriverRegistry
from provisioningserver.rpc import (
    cluster,
    clusterservice,
    common,
    exceptions,
    getRegionClient,
    pods,
)
from provisioningserver.rpc import power as power_module
from provisioningserver.rpc.clusterservice import (
    Cluster,
    ClusterClient,
    ClusterClientCheckerService,
    ClusterClientService,
    executeScanNetworksSubprocess,
    get_scan_all_networks_args,
    spawnProcessAndNullifyStdout,
)
from provisioningserver.rpc.interfaces import IConnection
from provisioningserver.rpc.testing import (
    call_responder,
    MockLiveClusterToRegionRPCFixture,
)
from provisioningserver.rpc.testing.doubles import (
    FakeBusyConnectionToRegion,
    FakeConnection,
)
from provisioningserver.security import fernet_encrypt_psk
from provisioningserver.testing.config import ClusterConfigurationFixture
from provisioningserver.utils import env as utils_env
from provisioningserver.utils.env import MAAS_ID, MAAS_SECRET, MAAS_UUID
from provisioningserver.utils.fs import get_maas_common_command, NamedLock
from provisioningserver.utils.shell import ExternalProcessError
from provisioningserver.utils.testing import MAASIDFixture
from provisioningserver.utils.twisted import makeDeferredWithProcessProtocol
from provisioningserver.utils.version import get_running_version

TIMEOUT = get_testing_timeout()


class TestClusterProtocol(MAASTestCase):
    def test_unauthenticated_allowed_commands(self):
        protocol = Cluster()
        self.assertEqual(
            [cluster.Authenticate.commandName],
            protocol.unauthenticated_commands,
        )

    def test_default_auth_status(self):
        protocol = Cluster()
        self.assertEqual(False, protocol.auth_status.is_authenticated)


class TestClusterProtocol_Identify(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_identify_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(cluster.Identify.commandName)
        self.assertIsNotNone(responder)

    def test_identify_reports_system_id(self):
        system_id = factory.make_name("id")
        self.useFixture(MAASIDFixture(system_id))
        d = call_responder(Cluster(), cluster.Identify, {})

        def check(response):
            self.assertEqual({"ident": system_id}, response)

        return d.addCallback(check)


class TestClusterProtocol_Authenticate(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_authenticate_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(cluster.Authenticate.commandName)
        self.assertIsNotNone(responder)

    def test_authenticate_calculates_digest_with_salt(self):
        message = factory.make_bytes()
        secret = factory.make_bytes()
        MAAS_SECRET.set(secret)

        args = {"message": message}
        d = call_responder(Cluster(), cluster.Authenticate, args)
        response = extract_result(d)
        digest = response["digest"]
        salt = response["salt"]

        self.assertEqual(len(salt), 16)
        expected_digest = HMAC(secret, message + salt, sha256).digest()
        self.assertEqual(expected_digest, digest)


class TestClusterProtocol_DescribePowerTypes(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_describe_power_types_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.DescribePowerTypes.commandName
        )
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_describe_power_types_returns_jsonized_schema(self):
        response = yield call_responder(
            Cluster(), cluster.DescribePowerTypes, {}
        )

        self.assertEqual(response.keys(), {"power_types"})
        self.assertEqual(
            PowerDriverRegistry.get_schema(detect_missing_packages=False),
            response["power_types"],
        )


def make_inert_client_service(max_idle_conns=1, max_conns=1, keepalive=1):
    service = ClusterClientService(
        Clock(), max_idle_conns, max_conns, keepalive
    )
    # ClusterClientService's superclass, TimerService, creates a
    # LoopingCall with now=True. We neuter it here to allow
    # observation of the behaviour of _update_interval() for
    # example.
    service.call = (lambda: None, (), {})
    return service


class TestClusterClientService(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def fakeAgentResponse(self, data="", code=200):
        self.patch(clusterservice, "readBody").return_value = succeed(data)
        mock_agent = MagicMock()
        response = MagicMock(code=code)
        mock_agent.request.return_value = succeed(response)
        self.patch(clusterservice, "Agent").return_value = mock_agent

    def test_init_sets_appropriate_instance_attributes(self):
        service = ClusterClientService(sentinel.reactor)
        self.assertIsInstance(service, TimerService)
        self.assertIs(service.clock, sentinel.reactor)

    def test_get_config_rpc_info_urls(self):
        maas_urls = [factory.make_simple_http_url() for _ in range(3)]
        self.useFixture(ClusterConfigurationFixture(maas_url=maas_urls))
        service = ClusterClientService(reactor)
        observed_urls = service._get_config_rpc_info_urls()
        self.assertEqual(maas_urls, observed_urls)

    def test_get_saved_rpc_info_urls(self):
        saved_urls = [factory.make_simple_http_url() for _ in range(3)]
        service = ClusterClientService(reactor)
        with open(service._get_saved_rpc_info_path(), "w") as stream:
            for url in saved_urls:
                stream.write("%s\n" % url)
        observed_urls = service._get_saved_rpc_info_urls()
        self.assertEqual(saved_urls, observed_urls)

    def test_update_saved_rpc_info_state(self):
        service = ClusterClientService(reactor)
        ipv4client = ClusterClient(("1.1.1.1", 1111), "host1:pid=1", service)
        ipv6client = ClusterClient(("::ffff", 2222), "host2:pid=2", service)
        ipv6mapped = ClusterClient(
            ("::ffff:3.3.3.3", 3333), "host3:pid=3", service
        )
        hostclient = ClusterClient(
            ("example.com", 4444), "host4:pid=4", service
        )

        # Fake some connections.
        service.connections.connections = {
            ipv4client.eventloop: [ipv4client],
            ipv6client.eventloop: [ipv6client],
            ipv6mapped.eventloop: [ipv6mapped],
            hostclient.eventloop: [hostclient],
        }

        # Update the RPC state to the filesystem and info cache.
        self.assertIsNone(service._rpc_info_state)
        service._update_saved_rpc_info_state()

        # Ensure that the info state is set.
        self.assertEqual(
            service._rpc_info_state,
            {
                client.address[0]
                for _, clients in service.connections.items()
                for client in clients
            },
        )

        # Check that the written rpc state is valid.
        self.assertEqual(
            service._get_saved_rpc_info_urls(),
            [
                "http://1.1.1.1:5240/MAAS",
                "http://[::ffff]:5240/MAAS",
                "http://3.3.3.3:5240/MAAS",
                "http://example.com:5240/MAAS",
            ],
        )

    @inlineCallbacks
    def test_build_rpc_info_urls(self):
        # Because this actually will try to resolve the URL's in the test we
        # keep them to localhost so it works on all systems.
        maas_urls = ["http://127.0.0.1:5240/" for _ in range(3)]
        expected_urls = [
            ([b"http://127.0.0.1:5240/rpc/"], "http://127.0.0.1:5240/")
            for url in maas_urls
        ]
        service = ClusterClientService(reactor)
        observed_urls = yield service._build_rpc_info_urls(maas_urls)
        self.assertEqual(expected_urls, observed_urls)

    def test_doUpdate_connect_502_error_is_logged_tersely(self):
        self.fakeAgentResponse(code=502)
        logger = self.useFixture(TwistedLoggerFixture())

        service = ClusterClientService(Clock())
        # Starting the service causes the first update to be performed.
        service.startService()

        dump = logger.dump()
        self.assertIn("Region is not advertising RPC endpoints.", dump)

    def test_doUpdate_connect_503_error_is_logged_tersely(self):
        self.fakeAgentResponse(code=503)
        logger = self.useFixture(TwistedLoggerFixture())

        service = ClusterClientService(Clock())
        # Starting the service causes the first update to be performed.
        service.startService()

        dump = logger.dump()
        self.assertIn("Region is not advertising RPC endpoints.", dump)

    def test_doUpdate_makes_parallel_requests(self):
        mock_agent = MagicMock()
        mock_agent.request.return_value = always_fail_with(
            web.error.Error(500)
        )
        self.patch(clusterservice, "Agent").return_value = mock_agent

        logger = self.useFixture(TwistedLoggerFixture())

        service = ClusterClientService(Clock())
        _get_config_rpc_info_urls = self.patch(
            service, "_get_config_rpc_info_urls"
        )
        _get_config_rpc_info_urls.return_value = [
            "http://127.0.0.1/MAAS",
            "http://127.0.0.1/MAAS",
        ]
        _build_rpc_info_urls = self.patch(service, "_build_rpc_info_urls")
        _build_rpc_info_urls.return_value = succeed(
            [
                ([b"http://[::ffff:127.0.0.1]/MAAS"], "http://127.0.0.1/MAAS"),
                ([b"http://[::ffff:127.0.0.1]/MAAS"], "http://127.0.0.1/MAAS"),
            ]
        )

        # Starting the service causes the first update to be performed.
        service.startService()

        mock_agent.request.assert_has_calls(
            [
                call(
                    b"GET",
                    ascii_url("http://[::ffff:127.0.0.1]/MAAS"),
                    Headers(
                        {
                            "User-Agent": [
                                "provisioningserver.rpc.clusterservice.ClusterClientService"
                            ],
                            "Host": ["127.0.0.1"],
                        }
                    ),
                ),
                call(
                    b"GET",
                    ascii_url("http://[::ffff:127.0.0.1]/MAAS"),
                    Headers(
                        {
                            "User-Agent": [
                                "provisioningserver.rpc.clusterservice.ClusterClientService"
                            ],
                            "Host": ["127.0.0.1"],
                        }
                    ),
                ),
            ]
        )
        dump = logger.dump()
        self.assertIn(
            "Failed to contact region. (While requesting RPC info at "
            "http://127.0.0.1/MAAS, http://127.0.0.1/MAAS)",
            dump,
        )

    def test_doUpdate_makes_parallel_with_serial_requests(self):
        mock_agent = MagicMock()
        mock_agent.request.return_value = always_fail_with(
            web.error.Error(500)
        )
        self.patch(clusterservice, "Agent").return_value = mock_agent

        logger = self.useFixture(TwistedLoggerFixture())

        service = ClusterClientService(Clock())
        _get_config_rpc_info_urls = self.patch(
            service, "_get_config_rpc_info_urls"
        )
        _get_config_rpc_info_urls.return_value = [
            "http://127.0.0.1/MAAS",
            "http://127.0.0.1/MAAS",
        ]
        _build_rpc_info_urls = self.patch(service, "_build_rpc_info_urls")
        _build_rpc_info_urls.return_value = succeed(
            [
                (
                    [
                        b"http://[::ffff:127.0.0.1]/MAAS",
                        b"http://127.0.0.1/MAAS",
                    ],
                    "http://127.0.0.1/MAAS",
                ),
                (
                    [
                        b"http://[::ffff:127.0.0.1]/MAAS",
                        b"http://127.0.0.1/MAAS",
                    ],
                    "http://127.0.0.1/MAAS",
                ),
            ]
        )

        # Starting the service causes the first update to be performed.
        service.startService()

        mock_agent.request.assert_has_calls(
            [
                call(
                    b"GET",
                    ascii_url("http://[::ffff:127.0.0.1]/MAAS"),
                    Headers(
                        {
                            "User-Agent": [
                                "provisioningserver.rpc.clusterservice.ClusterClientService"
                            ],
                            "Host": ["127.0.0.1"],
                        }
                    ),
                ),
                call(
                    b"GET",
                    ascii_url("http://127.0.0.1/MAAS"),
                    Headers(
                        {
                            "User-Agent": [
                                "provisioningserver.rpc.clusterservice.ClusterClientService"
                            ],
                            "Host": ["127.0.0.1"],
                        }
                    ),
                ),
                call(
                    b"GET",
                    ascii_url("http://[::ffff:127.0.0.1]/MAAS"),
                    Headers(
                        {
                            "User-Agent": [
                                "provisioningserver.rpc.clusterservice.ClusterClientService"
                            ],
                            "Host": ["127.0.0.1"],
                        }
                    ),
                ),
                call(
                    b"GET",
                    ascii_url("http://127.0.0.1/MAAS"),
                    Headers(
                        {
                            "User-Agent": [
                                "provisioningserver.rpc.clusterservice.ClusterClientService"
                            ],
                            "Host": ["127.0.0.1"],
                        }
                    ),
                ),
            ]
        )
        dump = logger.dump()
        self.assertIn(
            "Failed to contact region. (While requesting RPC info at "
            "http://127.0.0.1/MAAS, http://127.0.0.1/MAAS)",
            dump,
        )

    def test_doUpdate_falls_back_to_rpc_info_state(self):
        mock_agent = MagicMock()
        mock_agent.request.return_value = always_fail_with(
            web.error.Error(500)
        )
        self.patch(clusterservice, "Agent").return_value = mock_agent

        logger = self.useFixture(TwistedLoggerFixture())

        service = ClusterClientService(Clock())
        _get_config_rpc_info_urls = self.patch(
            service, "_get_config_rpc_info_urls"
        )
        _get_config_rpc_info_urls.return_value = [
            "http://127.0.0.1/MAAS",
            "http://127.0.0.1/MAAS",
        ]
        _get_saved_rpc_info_urls = self.patch(
            service, "_get_saved_rpc_info_urls"
        )
        _get_saved_rpc_info_urls.return_value = [
            "http://127.0.0.1/MAAS",
            "http://127.0.0.1/MAAS",
        ]
        _build_rpc_info_urls = self.patch(service, "_build_rpc_info_urls")
        _build_rpc_info_urls.side_effect = [
            succeed(
                [
                    (
                        [b"http://[::ffff:127.0.0.1]/MAAS"],
                        "http://127.0.0.1/MAAS",
                    ),
                    (
                        [b"http://[::ffff:127.0.0.1]/MAAS"],
                        "http://127.0.0.1/MAAS",
                    ),
                ]
            ),
            succeed(
                [
                    (
                        [b"http://[::ffff:127.0.0.1]/MAAS"],
                        "http://127.0.0.1/MAAS",
                    ),
                    (
                        [b"http://[::ffff:127.0.0.1]/MAAS"],
                        "http://127.0.0.1/MAAS",
                    ),
                ]
            ),
        ]

        # Starting the service causes the first update to be performed.
        service.startService()

        mock_agent.request.assert_has_calls(
            [
                call(
                    b"GET",
                    ascii_url("http://[::ffff:127.0.0.1]/MAAS"),
                    Headers(
                        {
                            "User-Agent": [
                                "provisioningserver.rpc.clusterservice.ClusterClientService"
                            ],
                            "Host": ["127.0.0.1"],
                        }
                    ),
                ),
                call(
                    b"GET",
                    ascii_url("http://[::ffff:127.0.0.1]/MAAS"),
                    Headers(
                        {
                            "User-Agent": [
                                "provisioningserver.rpc.clusterservice.ClusterClientService"
                            ],
                            "Host": ["127.0.0.1"],
                        }
                    ),
                ),
                call(
                    b"GET",
                    ascii_url("http://[::ffff:127.0.0.1]/MAAS"),
                    Headers(
                        {
                            "User-Agent": [
                                "provisioningserver.rpc.clusterservice.ClusterClientService"
                            ],
                            "Host": ["127.0.0.1"],
                        }
                    ),
                ),
                call(
                    b"GET",
                    ascii_url("http://[::ffff:127.0.0.1]/MAAS"),
                    Headers(
                        {
                            "User-Agent": [
                                "provisioningserver.rpc.clusterservice.ClusterClientService"
                            ],
                            "Host": ["127.0.0.1"],
                        }
                    ),
                ),
            ]
        )
        dump = logger.dump()
        self.assertIn(
            "Failed to contact region. (While requesting RPC info at "
            "http://127.0.0.1/MAAS, http://127.0.0.1/MAAS)",
            dump,
        )

    def test_failed_update_is_logged(self):
        logger = self.useFixture(TwistedLoggerFixture())

        service = ClusterClientService(Clock())
        _doUpdate = self.patch(service, "_doUpdate")
        _doUpdate.side_effect = error.ConnectionRefusedError()

        # Starting the service causes the first update to be performed, which
        # will fail because of above.
        service.startService()
        _doUpdate.assert_called_once_with()

        dump = logger.dump()
        self.assertIn("Connection was refused by other side.", dump)

    def test_update_connect_error_is_logged_tersely(self):
        mock_agent = MagicMock()
        mock_agent.request.side_effect = error.ConnectionRefusedError()
        self.patch(clusterservice, "Agent").return_value = mock_agent

        logger = self.useFixture(TwistedLoggerFixture())

        service = ClusterClientService(Clock())
        _get_config_rpc_info_urls = self.patch(
            service, "_get_config_rpc_info_urls"
        )
        _get_config_rpc_info_urls.return_value = ["http://127.0.0.1/MAAS"]
        _build_rpc_info_urls = self.patch(service, "_build_rpc_info_urls")
        _build_rpc_info_urls.return_value = succeed(
            [([b"http://[::ffff:127.0.0.1]/MAAS"], "http://127.0.0.1/MAAS")]
        )

        # Starting the service causes the first update to be performed.
        service.startService()

        mock_agent.request.assert_called_once_with(
            b"GET",
            ascii_url("http://[::ffff:127.0.0.1]/MAAS"),
            Headers(
                {
                    "User-Agent": [
                        "provisioningserver.rpc.clusterservice.ClusterClientService"
                    ],
                    "Host": ["127.0.0.1"],
                }
            ),
        )
        dump = logger.dump()
        self.assertIn(
            "Region not available: Connection was refused by other side.", dump
        )
        self.assertIn("While requesting RPC info at", dump)

    def test_update_connect_includes_host(self):
        # Regression test for LP:1792462
        mock_agent = MagicMock()
        mock_agent.request.side_effect = error.ConnectionRefusedError()
        self.patch(clusterservice, "Agent").return_value = mock_agent

        service = ClusterClientService(Clock())
        fqdn = "%s.example.com" % factory.make_hostname()
        _get_config_rpc_info_urls = self.patch(
            service, "_get_config_rpc_info_urls"
        )
        _get_config_rpc_info_urls.return_value = ["http://%s/MAAS" % fqdn]
        _build_rpc_info_urls = self.patch(service, "_build_rpc_info_urls")
        _build_rpc_info_urls.return_value = succeed(
            [([b"http://[::ffff:127.0.0.1]/MAAS"], "http://%s/MAAS" % fqdn)]
        )

        # Starting the service causes the first update to be performed.
        service.startService()

        mock_agent.request.assert_called_once_with(
            b"GET",
            ascii_url("http://[::ffff:127.0.0.1]/MAAS"),
            Headers(
                {
                    "User-Agent": [
                        "provisioningserver.rpc.clusterservice.ClusterClientService"
                    ],
                    "Host": [fqdn],
                }
            ),
        )

    # The following represents an example response from the RPC info
    # view in maasserver. Event-loops listen on ephemeral ports, and
    # it's up to the RPC info view to direct clients to them.
    example_rpc_info_view_response = json.dumps(
        {
            "eventloops": {
                # An event-loop in pid 1001 on host1. This host has two
                # configured IP addresses, 1.1.1.1 and 1.1.1.2.
                "host1:pid=1001": [
                    ("::ffff:1.1.1.1", 1111),
                    ("::ffff:1.1.1.2", 2222),
                ],
                # An event-loop in pid 2002 on host1. This host has two
                # configured IP addresses, 1.1.1.1 and 1.1.1.2.
                "host1:pid=2002": [
                    ("::ffff:1.1.1.1", 3333),
                    ("::ffff:1.1.1.2", 4444),
                ],
                # An event-loop in pid 3003 on host2. This host has one
                # configured IP address, 2.2.2.2.
                "host2:pid=3003": [("::ffff:2.2.2.2", 5555)],
            }
        }
    ).encode("ascii")

    def test_doUpdate_calls__update_connections(self):
        maas_url = "http://localhost/%s/" % factory.make_name("path")
        self.useFixture(ClusterConfigurationFixture(maas_url=maas_url))
        self.patch_autospec(socket, "getaddrinfo").return_value = (
            None,
            None,
            None,
            None,
            ("::ffff:127.0.0.1", 80, 0, 1),
        )
        self.fakeAgentResponse(data=self.example_rpc_info_view_response)
        service = ClusterClientService(Clock())
        _update_connections = self.patch(service, "_update_connections")
        service.startService()
        _update_connections.assert_called_once_with(
            {
                "host2:pid=3003": [["::ffff:2.2.2.2", 5555]],
                "host1:pid=2002": [
                    ["::ffff:1.1.1.1", 3333],
                    ["::ffff:1.1.1.2", 4444],
                ],
                "host1:pid=1001": [
                    ["::ffff:1.1.1.1", 1111],
                    ["::ffff:1.1.1.2", 2222],
                ],
            }
        )

    @inlineCallbacks
    def test_update_connections_initially(self):
        service = ClusterClientService(Clock())
        mock_client = Mock()
        _make_connection = self.patch(service.connections, "connect")
        _make_connection.side_effect = lambda *args: succeed(mock_client)
        _drop_connection = self.patch(service.connections, "disconnect")

        info = json.loads(self.example_rpc_info_view_response.decode("ascii"))
        yield service._update_connections(info["eventloops"])

        _make_connection_expected = [
            call("host1:pid=1001", ("::ffff:1.1.1.1", 1111)),
            call("host1:pid=2002", ("::ffff:1.1.1.1", 3333)),
            call("host2:pid=3003", ("::ffff:2.2.2.2", 5555)),
        ]
        self.assertEqual(
            _make_connection_expected, _make_connection.call_args_list
        )
        self.assertEqual(
            {
                "host1:pid=1001": mock_client,
                "host1:pid=2002": mock_client,
                "host2:pid=3003": mock_client,
            },
            service.connections.try_connections,
        )

        self.assertEqual([], _drop_connection.mock_calls)

    @inlineCallbacks
    def test_update_connections_logs_fully_connected(self):
        service = ClusterClientService(Clock())
        eventloops = {
            "region1:123": [("::ffff:127.0.0.1", 1234)],
            "region1:124": [("::ffff:127.0.0.1", 1235)],
            "region2:123": [("::ffff:127.0.0.2", 1234)],
            "region2:124": [("::ffff:127.0.0.2", 1235)],
        }
        for eventloop, addresses in eventloops.items():
            for address in addresses:
                client = Mock()
                client.address = address
                service.connections.connections[eventloop] = [client]

        logger = self.useFixture(TwistedLoggerFixture())

        yield service._update_connections(eventloops)
        # Second call should not add it to the log.
        yield service._update_connections(eventloops)

        self.assertEqual(
            "Fully connected to all 4 event-loops on all 2 region "
            "controllers (region1, region2).",
            logger.dump(),
        )

    @inlineCallbacks
    def test_update_connections_connect_error_is_logged_tersely(self):
        service = ClusterClientService(Clock())
        _make_connection = self.patch(service.connections, "connect")
        _make_connection.side_effect = error.ConnectionRefusedError()

        logger = self.useFixture(TwistedLoggerFixture())

        eventloops = {"an-event-loop": [("127.0.0.1", 1234)]}
        yield service._update_connections(eventloops)

        _make_connection.assert_called_once_with(
            "an-event-loop", ("::ffff:127.0.0.1", 1234)
        )

        self.assertEqual(
            "Making connections to event-loops: an-event-loop\n"
            "---\n"
            "Event-loop an-event-loop (::ffff:127.0.0.1:1234): Connection "
            "was refused by other side.",
            logger.dump(),
        )

    @inlineCallbacks
    def test_update_connections_unknown_error_is_logged_with_stack(self):
        service = ClusterClientService(Clock())
        _make_connection = self.patch(service.connections, "connect")
        _make_connection.side_effect = RuntimeError("Something went wrong.")

        logger = self.useFixture(TwistedLoggerFixture())

        eventloops = {"an-event-loop": [("127.0.0.1", 1234)]}
        yield service._update_connections(eventloops)

        _make_connection.assert_called_once_with(
            "an-event-loop", ("::ffff:127.0.0.1", 1234)
        )

        self.assertEqual(
            logger.messages,
            [
                "Making connections to event-loops: an-event-loop",
                "Failure with event-loop an-event-loop (::ffff:127.0.0.1:1234)",
            ],
        )
        failure_messages = [
            failure.getErrorMessage() for failure in logger.failures
        ]
        self.assertEqual(failure_messages, ["Something went wrong."])

    def test_update_connections_when_there_are_existing_connections(self):
        service = ClusterClientService(Clock())
        _connect = self.patch(service.connections, "connect")
        _disconnect = self.patch(service.connections, "disconnect")

        host1client = ClusterClient(
            ("::ffff:1.1.1.1", 1111), "host1:pid=1", service
        )
        host2client = ClusterClient(
            ("::ffff:2.2.2.2", 2222), "host2:pid=2", service
        )
        host3client = ClusterClient(
            ("::ffff:3.3.3.3", 3333), "host3:pid=3", service
        )

        # Fake some connections.
        service.connections.connections = {
            host1client.eventloop: [host1client],
            host2client.eventloop: [host2client],
        }

        # Request a new set of connections that overlaps with the
        # existing connections.
        service._update_connections(
            {
                host1client.eventloop: [host1client.address],
                host3client.eventloop: [host3client.address],
            }
        )

        # A connection is made for host3's event-loop, and the
        # connection to host2's event-loop is dropped.
        _connect.assert_called_once_with(
            host3client.eventloop, host3client.address
        )
        _disconnect.assert_called_once_with(host2client)

    @inlineCallbacks
    def test_update_only_updates_interval_when_eventloops_are_unknown(self):
        service = ClusterClientService(Clock())
        self.patch_autospec(service, "_get_config_rpc_info_urls")
        self.patch_autospec(service, "_build_rpc_info_urls")
        self.patch_autospec(service, "_parallel_fetch_rpc_info")
        self.patch_autospec(service, "_update_connections")
        # Return urls from _get_config_rpc_info_urls and _build_rpc_info_urls.
        service._get_config_rpc_info_urls.return_value = [
            "http://127.0.0.1/MAAS"
        ]
        service._build_rpc_info_urls.return_value = succeed(
            [([b"http://[::ffff:127.0.0.1]/MAAS"], "http://127.0.0.1/MAAS")]
        )
        # Return None instead of a list of event-loop endpoints. This is the
        # response that the region will give when the advertising service is
        # not running.
        service._parallel_fetch_rpc_info.return_value = succeed((None, None))
        # Set the step to a bogus value so we can see it change.
        service.step = 999

        logger = self.useFixture(TwistedLoggerFixture())

        yield service.startService()

        service._update_connections.assert_not_called()
        self.assertEqual(service.INTERVAL_LOW, service.step)
        self.assertEqual(
            "Region is not advertising RPC endpoints. (While requesting RPC"
            " info at http://127.0.0.1/MAAS)",
            logger.dump(),
        )

    def test_add_connection_removes_from_try_connections(self):
        service = make_inert_client_service()
        service.startService()
        endpoint = Mock()
        connection = Mock()
        connection.address = (":::ffff", 2222)
        service.connections.try_connections[endpoint] = connection
        service.add_connection(endpoint, connection)
        self.assertEqual({}, service.connections.try_connections)

    def test_add_connection_adds_to_connections(self):
        service = make_inert_client_service()
        service.startService()
        endpoint = Mock()
        connection = Mock()
        connection.address = (":::ffff", 2222)
        service.add_connection(endpoint, connection)
        self.assertEqual(service.connections, {endpoint: [connection]})

    def test_add_connection_calls__update_saved_rpc_info_state(self):
        service = make_inert_client_service()
        service.startService()
        endpoint = Mock()
        connection = Mock()
        connection.address = (":::ffff", 2222)
        self.patch_autospec(service, "_update_saved_rpc_info_state")
        service.add_connection(endpoint, connection)
        service._update_saved_rpc_info_state.assert_called_once_with()

    @inlineCallbacks
    def test_add_connection_creates_max_idle_connections(self):
        service = make_inert_client_service(max_idle_conns=2)
        service.startService()
        endpoint = Mock()
        connection = Mock()
        connection.eventloop = endpoint
        connection.address = (":::ffff", 2222)

        @inlineCallbacks
        def mock_connect(ev, addr):
            new_conn = Mock()
            new_conn.eventloop = ev
            new_conn.address = addr
            yield service.add_connection(ev, new_conn)
            return new_conn

        self.patch(service.connections, "connect").side_effect = mock_connect
        self.patch_autospec(service, "_update_saved_rpc_info_state")
        yield service.add_connection(endpoint, connection)
        self.assertEqual(
            len(
                [
                    conn
                    for conns in service.connections.values()
                    for conn in conns
                ]
            ),
            service.connections._max_idle_connections,
        )

    def test_remove_connection_removes_from_try_connections(self):
        service = make_inert_client_service()
        service.startService()
        endpoint = Mock()
        connection = Mock()
        service.connections.try_connections[endpoint] = connection
        service.remove_connection(endpoint, connection)
        self.assertEqual(service.connections.try_connections, {})

    def test_remove_connection_removes_from_connections(self):
        service = make_inert_client_service()
        service.startService()
        endpoint = Mock()
        connection = Mock()
        service.connections[endpoint] = {connection}
        service.remove_connection(endpoint, connection)
        self.assertEqual({}, service.connections)

    def test_remove_connection_lowers_recheck_interval(self):
        service = make_inert_client_service()
        service.startService()
        endpoint = Mock()
        connection = Mock()
        service.connections[endpoint] = {connection}
        service.remove_connection(endpoint, connection)
        self.assertEqual(service.step, service.INTERVAL_LOW)

    def test_getClient(self):
        service = ClusterClientService(Clock())
        service.connections.connections = {
            sentinel.eventloop01: [FakeConnection()],
            sentinel.eventloop02: [FakeConnection()],
            sentinel.eventloop03: [FakeConnection()],
        }
        self.assertIn(
            service.getClient(),
            {
                common.Client(conn)
                for conns in service.connections.values()
                for conn in conns
            },
        )

    def test_getClient_when_there_are_no_connections(self):
        service = ClusterClientService(Clock())
        service.connections.connections = {}
        self.assertRaises(exceptions.NoConnectionsAvailable, service.getClient)

    def test_getClient_returns_a_busy_connection_when_busy_ok_is_True(self):
        service = ClusterClientService(Clock(), max_conns=1)
        service.connections.connections = {
            sentinel.eventloop01: [FakeBusyConnectionToRegion()],
            sentinel.eventloop02: [FakeBusyConnectionToRegion()],
            sentinel.eventloop03: [FakeBusyConnectionToRegion()],
        }
        client = service.getClient(busy_ok=True)
        self.assertTrue(client._conn.in_use)
        self.assertIn(
            client,
            {
                common.Client(conn)
                for conns in service.connections.values()
                for conn in conns
            },
        )

    @inlineCallbacks
    def test_getClientNow_scales_connections_when_busy(self):
        service = ClusterClientService(Clock(), max_conns=2)
        service.connections.connections = {
            sentinel.eventloop01: [FakeBusyConnectionToRegion()],
            sentinel.eventloop02: [FakeBusyConnectionToRegion()],
            sentinel.eventloop03: [FakeBusyConnectionToRegion()],
        }
        self.patch(service.connections, "connect").return_value = succeed(
            FakeConnection()
        )

        # skip the connectionMade logic for this test
        @inlineCallbacks
        def mock_scale_up_connections():
            for ev, conns in service.connections.items():
                if len(conns) < service.connections._max_connections:
                    conn = yield service.connections.connect()
                    service.connections[ev].append(conn)
                    break

        scale_up = self.patch(service.connections, "scale_up_connections")
        scale_up.side_effect = mock_scale_up_connections

        original_conns = [
            conn for conns in service.connections.values() for conn in conns
        ]
        new_client = yield service.getClientNow()
        new_conn = new_client._conn
        scale_up.assert_called_once()
        self.assertIsNotNone(new_conn)
        self.assertNotIn(new_conn, original_conns)
        self.assertIn(
            new_conn,
            [conn for conns in service.connections.values() for conn in conns],
        )

    @inlineCallbacks
    def test_getClientNow_returns_an_existing_connection_when_max_are_open(
        self,
    ):
        service = ClusterClientService(Clock(), max_conns=1)
        service.connections.connections = {
            sentinel.eventloop01: [FakeBusyConnectionToRegion()],
            sentinel.eventloop02: [FakeBusyConnectionToRegion()],
            sentinel.eventloop03: [FakeBusyConnectionToRegion()],
        }
        self.patch(service, "_make_connection").return_value = succeed(
            FakeConnection()
        )
        original_conns = [
            conn for conns in service.connections.values() for conn in conns
        ]
        new_client = yield service.getClientNow()
        new_conn = new_client._conn
        self.assertIsNotNone(new_conn)
        self.assertIn(new_conn, original_conns)

    @inlineCallbacks
    def test_getClientNow_returns_current_connection(self):
        service = ClusterClientService(Clock())
        service.connections.connections = {
            sentinel.eventloop01: [FakeConnection()],
            sentinel.eventloop02: [FakeConnection()],
            sentinel.eventloop03: [FakeConnection()],
        }
        client = yield service.getClientNow()
        self.assertIn(
            client,
            [
                common.Client(conn)
                for conns in service.connections.values()
                for conn in conns
            ],
        )

    @inlineCallbacks
    def test_getClientNow_calls__tryUpdate_when_there_are_no_connections(self):
        service = ClusterClientService(Clock())

        def addConnections():
            service.connections.connections = {
                sentinel.eventloop01: [FakeConnection()],
                sentinel.eventloop02: [FakeConnection()],
                sentinel.eventloop03: [FakeConnection()],
            }
            return succeed(None)

        self.patch(service, "_tryUpdate").side_effect = addConnections
        client = yield service.getClientNow()
        self.assertIn(
            client,
            {
                common.Client(conn)
                for conns in service.connections.values()
                for conn in conns
            },
        )

    def test_getClientNow_raises_exception_when_no_clients(self):
        service = ClusterClientService(Clock())

        self.patch(service, "_tryUpdate").return_value = succeed(None)
        d = service.getClientNow()
        d.addCallback(lambda _: self.fail("Errback should have been called."))
        d.addErrback(
            lambda failure: self.assertIsInstance(
                failure.value, exceptions.NoConnectionsAvailable
            )
        )
        return d

    def test_tryUpdate_prevents_concurrent_calls_to__doUpdate(self):
        service = ClusterClientService(Clock())

        d_doUpdate_1, d_doUpdate_2 = Deferred(), Deferred()
        _doUpdate = self.patch(service, "_doUpdate")
        _doUpdate.side_effect = [d_doUpdate_1, d_doUpdate_2]

        # Try updating a couple of times concurrently.
        d_tryUpdate_1 = service._tryUpdate()
        d_tryUpdate_2 = service._tryUpdate()
        # _doUpdate completes and returns `done`.
        d_doUpdate_1.callback(sentinel.done1)
        # Both _tryUpdate calls yield the same result.
        self.assertIs(extract_result(d_tryUpdate_1), sentinel.done1)
        self.assertIs(extract_result(d_tryUpdate_2), sentinel.done1)
        # _doUpdate was called only once.
        _doUpdate.assert_called_once_with()

        # The mechanism has reset and is ready to go again.
        d_tryUpdate_3 = service._tryUpdate()
        d_doUpdate_2.callback(sentinel.done2)
        self.assertIs(extract_result(d_tryUpdate_3), sentinel.done2)

    def test_getAllClients(self):
        service = ClusterClientService(Clock())
        uuid1 = factory.make_UUID()
        c1 = FakeConnection()
        service.connections[uuid1] = {c1}
        uuid2 = factory.make_UUID()
        c2 = FakeConnection()
        service.connections[uuid2] = {c2}
        clients = service.getAllClients()
        self.assertEqual(clients, [common.Client(c1), common.Client(c2)])

    def test_getAllClients_when_there_are_no_connections(self):
        service = ClusterClientService(Clock())
        self.assertEqual([], service.getAllClients())


class TestClusterClientServiceIntervals(MAASTestCase):
    scenarios = (
        (
            "initial",
            {
                "time_running": 0,
                "num_eventloops": None,
                "num_connections": None,
                "expected": ClusterClientService.INTERVAL_LOW,
            },
        ),
        (
            "shortly-after-start",
            {
                "time_running": 10,
                "num_eventloops": 1,  # same as num_connections.
                "num_connections": 1,  # same as num_eventloops.
                "expected": ClusterClientService.INTERVAL_LOW,
            },
        ),
        (
            "no-event-loops",
            {
                "time_running": 1000,
                "num_eventloops": 0,
                "num_connections": sentinel.undefined,
                "expected": ClusterClientService.INTERVAL_LOW,
            },
        ),
        (
            "no-connections",
            {
                "time_running": 1000,
                "num_eventloops": 1,  # anything > 1.
                "num_connections": 0,
                "expected": ClusterClientService.INTERVAL_LOW,
            },
        ),
        (
            "fewer-connections-than-event-loops",
            {
                "time_running": 1000,
                "num_eventloops": 2,  # anything > num_connections.
                "num_connections": 1,  # anything > 0.
                "expected": ClusterClientService.INTERVAL_MID,
            },
        ),
        (
            "default",
            {
                "time_running": 1000,
                "num_eventloops": 3,  # same as num_connections.
                "num_connections": 3,  # same as num_eventloops.
                "expected": ClusterClientService.INTERVAL_HIGH,
            },
        ),
    )

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_calculate_interval(self):
        service = make_inert_client_service()
        service.startService()
        service.clock.advance(self.time_running)
        self.assertEqual(
            self.expected,
            service._calculate_interval(
                self.num_eventloops, self.num_connections
            ),
        )


class TestClusterClientBase(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.useFixture(
            ClusterConfigurationFixture(
                maas_url=factory.make_simple_http_url(),
            )
        )
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

    def make_running_client(self):
        client = clusterservice.ClusterClient(
            address=("example.com", 1234),
            eventloop="eventloop:pid=12345",
            service=make_inert_client_service(),
        )
        client.service.startService()
        return client


class TestClusterClientClusterCertificatesAreStored(TestClusterClientBase):
    @inlineCallbacks
    def test_cluster_certificates_are_stored(self):
        maas_data = os.getenv("MAAS_ROOT")
        certs_dir = f"{maas_data}/certificates"
        os.mkdir(certs_dir)

        client = self.make_running_client()

        maasca = Certificate.generate_ca_certificate("maas")
        certificate_request = CertificateRequest.generate("request")
        certificate = maasca.sign_certificate_request(certificate_request)

        callRemote = self.patch_autospec(client, "callRemote")
        callRemote.side_effect = always_succeed_with(
            {
                "system_id": "...",
                "encrypted_cluster_certificate": fernet_encrypt_psk(
                    json.dumps(
                        {
                            "cert": certificate.certificate_pem(),
                            "key": certificate.private_key_pem(),
                            "cacerts": certificate.ca_certificates_pem(),
                        }
                    )
                ),
            }
        )

        result = yield client.registerRackWithRegion()
        self.assertTrue(result)
        self.assertEqual(
            get_maas_cluster_cert_paths(),
            (
                f"{certs_dir}/cluster.pem",
                f"{certs_dir}/cluster.key",
                f"{certs_dir}/cacerts.pem",
            ),
        )


class TestClusterClient(TestClusterClientBase):
    def setUp(self):
        super().setUp()
        # Simulate that the rack already has the cluster certificates
        self.patch(
            clusterservice, "get_maas_cluster_cert_paths"
        ).return_value = ("/test", "/test")

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
        register = self.patch_autospec(client, "registerRackWithRegion")
        register.side_effect = always_succeed_with(True)

    def patch_register_for_failure(self, client):
        register = self.patch_autospec(client, "registerRackWithRegion")
        register.side_effect = always_succeed_with(False)

    def patch_register_for_error(self, client, exception):
        register = self.patch_autospec(client, "registerRackWithRegion")
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
        self.assertEqual(client.eventloop, client.ident)

    def test_connecting(self):
        client = self.make_running_client()
        client.service.connections.try_connections[client.eventloop] = client
        self.patch_authenticate_for_success(client)
        self.patch_register_for_success(client)
        self.assertEqual(client.service.connections, {})
        wait_for_authenticated = client.authenticated.get()
        self.assertIsInstance(wait_for_authenticated, Deferred)
        self.assertFalse(wait_for_authenticated.called)
        wait_for_ready = client.ready.get()
        self.assertIsInstance(wait_for_ready, Deferred)
        self.assertFalse(wait_for_ready.called)
        client.connectionMade()
        # authenticated has been set to True, denoting a successfully
        # authenticated region.
        self.assertTrue(extract_result(wait_for_authenticated))
        # ready has been set with the name of the event-loop.
        self.assertEqual(client.eventloop, extract_result(wait_for_ready))
        self.assertEqual(len(client.service.connections.try_connections), 0)
        self.assertEqual(
            client.service.connections.connections,
            {client.eventloop: [client]},
        )

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
        self.assertFalse(extract_result(client.authenticated.get()))
        # ready was set with AuthenticationFailed.
        self.assertRaises(
            exceptions.AuthenticationFailed, extract_result, client.ready.get()
        )

        # The connections list is unchanged because the new connection
        # immediately disconnects.
        self.assertEqual(client.service.connections.connections, {})
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
            exception_type, extract_result, client.authenticated.get()
        )
        # ready also errbacks with the same error.
        self.assertRaises(exception_type, extract_result, client.ready.get())

        # The log was written to.
        self.assertIn(
            "Event-loop 'eventloop:pid=12345' handshake failed; dropping connection.",
            {err["why"] for err in logger.errors},
        )

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
        self.assertTrue(extract_result(client.authenticated.get()))
        # ready was set with AuthenticationFailed.
        self.assertRaises(
            exceptions.RegistrationFailed, extract_result, client.ready.get()
        )

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
        self.assertTrue(extract_result(client.authenticated.get()))
        # ready was set with the exception we made.
        self.assertRaises(exception_type, extract_result, client.ready.get())

        # The log was written to.
        self.assertIn(
            "Event-loop 'eventloop:pid=12345' handshake failed; dropping connection.",
            {err["why"] for err in logger.errors},
        )

        # The connections list is unchanged because the new connection
        # immediately disconnects.
        self.assertEqual(client.service.connections, {})
        self.assertFalse(client.connected)

    def test_handshakeFailed_does_not_log_when_connection_is_closed(self):
        client = self.make_running_client()
        with TwistedLoggerFixture() as logger:
            client.handshakeFailed(Failure(ConnectionClosed()))
        # ready was set with ConnectionClosed.
        self.assertRaises(ConnectionClosed, extract_result, client.ready.get())
        # Nothing was logged.
        self.assertEqual("", logger.output)

    # XXX: blake_r 2015-02-26 bug=1426089: Failing because of an unknown
    # reason. This is commented out instead of using @skip because of
    # running MAASTwistedRunTest will cause twisted to complain.
    # @inlineCallbacks
    # def test_secureConnection_end_to_end(self):
    #     fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
    #     protocol, connecting = fixture.makeEventLoop()
    #     self.addCleanup((yield connecting))
    #     client = yield getRegionClient()
    #     # XXX: Expose secureConnection() in the client.
    #     yield client._conn.secureConnection()
    #     self.assertTrue(client.isSecure())

    def test_authenticateRegion_accepts_matching_digests(self):
        MAAS_SECRET.set(factory.make_bytes())
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
        MAAS_SECRET.set(factory.make_bytes())
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
        protocol.Authenticate.assert_called_once_with(protocol, message=ANY)

    @inlineCallbacks
    def test_registerRackWithRegion_returns_True_when_accepted(self):
        logger = self.useFixture(TwistedLoggerFixture())
        client = self.make_running_client()

        callRemote = self.patch_autospec(client, "callRemote")
        callRemote.side_effect = always_succeed_with({"system_id": "..."})

        result = yield client.registerRackWithRegion()
        self.assertTrue(result)

        self.assertIn(
            f"Rack controller '{client.localIdent}' registered (via eventloop:pid=12345) with MAAS version 2.2 or below.",
            logger.dump(),
        )

    @inlineCallbacks
    def test_registerRackWithRegion_logs_version_if_supplied(self):
        client = self.make_running_client()

        callRemote = self.patch_autospec(client, "callRemote")
        callRemote.side_effect = always_succeed_with(
            {"system_id": "...", "version": "2.3.0"}
        )

        logger = self.useFixture(TwistedLoggerFixture())

        result = yield client.registerRackWithRegion()
        self.assertTrue(result)

        self.assertIn(
            "Rack controller '...' registered (via eventloop:pid=12345) with MAAS version 2.3.0.",
            logger.output,
        )

    @inlineCallbacks
    def test_registerRackWithRegion_logs_unknown_version_if_empty(self):
        client = self.make_running_client()

        callRemote = self.patch_autospec(client, "callRemote")
        callRemote.side_effect = always_succeed_with(
            {"system_id": "...", "version": ""}
        )

        logger = self.useFixture(TwistedLoggerFixture())

        result = yield client.registerRackWithRegion()
        self.assertTrue(result)

        self.assertIn(
            "Rack controller '...' registered (via eventloop:pid=12345) with unknown MAAS version.",
            logger.output,
        )

    @inlineCallbacks
    def test_registerRackWithRegion_sets_localIdent(self):
        client = self.make_running_client()

        system_id = factory.make_name("id")
        callRemote = self.patch_autospec(client, "callRemote")
        callRemote.side_effect = always_succeed_with({"system_id": system_id})

        result = yield client.registerRackWithRegion()
        self.assertTrue(result)
        self.assertEqual(system_id, client.localIdent)

    @inlineCallbacks
    def test_registerRackWithRegion_calls_set_maas_id(self):
        self.maas_id = None

        def set_id(maas_id):
            self.maas_id = maas_id

        set_id_mock = self.patch(clusterservice.MAAS_ID, "set")
        set_id_mock.side_effect = set_id

        client = self.make_running_client()

        system_id = factory.make_name("id")
        callRemote = self.patch_autospec(client, "callRemote")
        callRemote.side_effect = always_succeed_with({"system_id": system_id})

        result = yield client.registerRackWithRegion()
        self.assertTrue(result)
        set_id_mock.assert_called_once_with(system_id)

    @inlineCallbacks
    def test_registerRackWithRegion_sets_global_labels(self):
        mock_set_global_labels = self.patch(
            clusterservice, "set_global_labels"
        )
        client = self.make_running_client()

        system_id = factory.make_name("id")
        callRemote = self.patch_autospec(client, "callRemote")
        callRemote.side_effect = always_succeed_with(
            {"system_id": system_id, "uuid": "a-b-c"}
        )

        result = yield client.registerRackWithRegion()
        self.assertTrue(result)
        mock_set_global_labels.assert_called_once_with(maas_uuid="a-b-c")

    @inlineCallbacks
    def test_registerRackWithRegion_sets_uuid(self):
        maas_uuid = factory.make_name("uuid")
        client = self.make_running_client()

        system_id = factory.make_name("id")
        callRemote = self.patch_autospec(client, "callRemote")
        callRemote.side_effect = always_succeed_with(
            {"system_id": system_id, "uuid": maas_uuid}
        )

        result = yield client.registerRackWithRegion()
        self.assertTrue(result)
        self.assertEqual(MAAS_UUID.get(), maas_uuid)

    @inlineCallbacks
    def test_registerRackWithRegion_returns_False_when_rejected(self):
        client = self.make_running_client()

        callRemote = self.patch_autospec(client, "callRemote")
        callRemote.return_value = fail(
            exceptions.CannotRegisterRackController()
        )

        logger = self.useFixture(TwistedLoggerFixture())

        result = yield client.registerRackWithRegion()
        self.assertFalse(result)

        self.assertEqual(
            "Rack controller REJECTED by the region (via eventloop:pid=12345).",
            logger.output,
        )

    @inlineCallbacks
    def test_registerRackWithRegion_propagates_errors(self):
        client = self.make_running_client()
        exception_type = factory.make_exception_type()

        callRemote = self.patch_autospec(client, "callRemote")
        callRemote.return_value = fail(exception_type())

        caught_exc = None
        try:
            yield client.registerRackWithRegion()
        except Exception as exc:
            caught_exc = exc
        self.assertIsInstance(caught_exc, exception_type)

    @inlineCallbacks
    def test_registerRackWithRegion_end_to_end(self):
        system_id = factory.make_name("id")
        MAAS_ID.set(system_id)
        maas_url = factory.make_simple_http_url()
        hostname = "rackcontrol.example.com"
        self.patch_autospec(
            clusterservice, "gethostname"
        ).return_value = hostname
        self.useFixture(ClusterConfigurationFixture())
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture(maas_url))
        protocol, connecting = fixture.makeEventLoop()
        self.addCleanup((yield connecting))
        yield getRegionClient()
        protocol.RegisterRackController.assert_called_once_with(
            protocol,
            system_id=system_id,
            hostname=hostname,
            interfaces={},
            url=urlparse(maas_url),
            beacon_support=True,
            version=str(get_running_version()),
        )


class TestClusterClientCheckerService(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def make_client(self):
        client = Mock()
        client.return_value = succeed(None)
        return client

    def test_init_sets_up_timer_correctly(self):
        service = ClusterClientCheckerService(
            sentinel.client_service, sentinel.clock
        )
        self.assertEqual(service.call, (service.tryLoop, (), {}))
        self.assertEqual(service.step, 30)
        self.assertIs(service.client_service, sentinel.client_service)
        self.assertIs(service.clock, sentinel.clock)

    def test_tryLoop_calls_loop(self):
        service = ClusterClientCheckerService(
            sentinel.client_service, sentinel.clock
        )
        mock_loop = self.patch(service, "loop")
        mock_loop.return_value = succeed(None)
        service.tryLoop()
        mock_loop.assert_called_once_with()

    def test_loop_does_nothing_with_no_clients(self):
        mock_client_service = MagicMock()
        mock_client_service.getAllClients.return_value = []
        service = ClusterClientCheckerService(mock_client_service, reactor)
        # Test will timeout if this blocks longer than 5 seconds.
        return service.loop()

    @inlineCallbacks
    def test_loop_calls_ping_for_each_client(self):
        clients = [self.make_client() for _ in range(3)]
        mock_client_service = MagicMock()
        mock_client_service.getAllClients.return_value = clients
        service = ClusterClientCheckerService(mock_client_service, reactor)
        yield service.loop()
        for client in clients:
            client.assert_called_once_with(common.Ping, _timeout=10)

    @inlineCallbacks
    def test_ping_calls_loseConnection_on_failure(self):
        client = MagicMock()
        client.return_value = fail(factory.make_exception())
        mock_client_service = MagicMock()
        service = ClusterClientCheckerService(mock_client_service, reactor)
        yield service._ping(client)
        client._conn.transport.loseConnection.assert_called_once_with()


class TestClusterProtocol_PowerQuery(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(cluster.PowerQuery.commandName)
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_returns_power_state(self):
        state = random.choice(["on", "off"])
        perform_power_driver_query = self.patch(
            power_module, "perform_power_driver_query"
        )
        perform_power_driver_query.return_value = state
        power_driver = random.choice(
            [driver for _, driver in PowerDriverRegistry if driver.queryable]
        )
        arguments = {
            "system_id": factory.make_name("system"),
            "hostname": factory.make_name("hostname"),
            "power_type": power_driver.name,
            "context": factory.make_name("context"),
        }

        # Make sure power driver doesn't check for installed packages.
        self.patch_autospec(
            power_driver, "detect_missing_packages"
        ).return_value = []

        observed = yield call_responder(
            Cluster(), cluster.PowerQuery, arguments
        )
        self.assertEqual({"state": state, "error_msg": None}, observed)
        perform_power_driver_query.assert_called_once_with(
            arguments["system_id"],
            arguments["hostname"],
            arguments["power_type"],
            arguments["context"],
        )

    @inlineCallbacks
    def test_returns_power_error(self):
        perform_power_driver_query = self.patch(
            power_module, "perform_power_driver_query"
        )
        perform_power_driver_query.side_effect = PowerError("Error message")
        power_driver = random.choice(
            [driver for _, driver in PowerDriverRegistry if driver.queryable]
        )
        arguments = {
            "system_id": factory.make_name("system"),
            "hostname": factory.make_name("hostname"),
            "power_type": power_driver.name,
            "context": factory.make_name("context"),
        }

        # Make sure power driver doesn't check for installed packages.
        self.patch_autospec(
            power_driver, "detect_missing_packages"
        ).return_value = []

        observed = yield call_responder(
            Cluster(), cluster.PowerQuery, arguments
        )
        self.assertEqual(
            {"state": "error", "error_msg": "Error message"}, observed
        )
        perform_power_driver_query.assert_called_once_with(
            arguments["system_id"],
            arguments["hostname"],
            arguments["power_type"],
            arguments["context"],
        )


class TestClusterProtocol_SetBootOrder(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(cluster.SetBootOrder.commandName)
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_set_boot_order(self):
        mock_get_item = self.patch(PowerDriverRegistry, "get_item")
        mock_get_item.return_value.can_set_boot_order = True
        mock_get_item.return_value.set_boot_order.return_value = succeed(None)
        system_id = factory.make_name("system_id")
        context = factory.make_name("context")
        order = [
            {
                "id": random.randint(0, 100),
                "name": factory.make_name("name"),
                "mac_address": factory.make_mac_address(),
                "vendor": factory.make_name("vendor"),
                "product": factory.make_name("product"),
                "id_path": factory.make_name("id_path"),
                "model": factory.make_name("model"),
                "serial": factory.make_name("serial"),
            }
            for _ in range(3)
        ]

        yield call_responder(
            Cluster(),
            cluster.SetBootOrder,
            {
                "system_id": system_id,
                "hostname": factory.make_name("hostname"),
                "power_type": factory.make_name("power_type"),
                "context": context,
                "order": order,
            },
        )

        mock_get_item.return_value.set_boot_order.assert_called_once_with(
            system_id, context, order
        )

    @inlineCallbacks
    def test_set_boot_order_unknown_power_typer(self):
        mock_get_item = self.patch(PowerDriverRegistry, "get_item")
        mock_get_item.return_value = None
        system_id = factory.make_name("system_id")
        context = factory.make_name("context")
        order = [
            {
                "id": random.randint(0, 100),
                "name": factory.make_name("name"),
                "mac_address": factory.make_mac_address(),
                "vendor": factory.make_name("vendor"),
                "product": factory.make_name("product"),
                "id_path": factory.make_name("id_path"),
                "model": factory.make_name("model"),
                "serial": factory.make_name("serial"),
            }
            for _ in range(3)
        ]

        with TestCase.assertRaises(self, exceptions.UnknownPowerType):
            yield call_responder(
                Cluster(),
                cluster.SetBootOrder,
                {
                    "system_id": system_id,
                    "hostname": factory.make_name("hostname"),
                    "power_type": factory.make_name("power_type"),
                    "context": context,
                    "order": order,
                },
            )

    @inlineCallbacks
    def test_set_boot_order_unsupported(self):
        mock_get_item = self.patch(PowerDriverRegistry, "get_item")
        mock_get_item.return_value.can_set_boot_order = False
        system_id = factory.make_name("system_id")
        context = factory.make_name("context")
        order = [
            {
                "id": random.randint(0, 100),
                "name": factory.make_name("name"),
                "mac_address": factory.make_mac_address(),
                "vendor": factory.make_name("vendor"),
                "product": factory.make_name("product"),
                "id_path": factory.make_name("id_path"),
                "model": factory.make_name("model"),
                "serial": factory.make_name("serial"),
            }
            for _ in range(3)
        ]

        yield call_responder(
            Cluster(),
            cluster.SetBootOrder,
            {
                "system_id": system_id,
                "hostname": factory.make_name("hostname"),
                "power_type": factory.make_name("power_type"),
                "context": context,
                "order": order,
            },
        )

        mock_get_item.return_value.set_boot_order.assert_not_called()


class MAASTestCaseThatWaitsForDeferredThreads(MAASTestCase):
    """Capture deferred threads and wait for them during teardown.

    This will capture calls to `deferToThread` in the `clusterservice` module,
    and can be useful when work is deferred to threads in a way that cannot be
    observed via the system under test.

    Use of this may be an indicator for code that is poorly designed for
    testing. Consider refactoring so that your tests can explicitly deal with
    threads that have been deferred outside of the reactor.
    """

    # Subclasses can override this, but they MUST choose a runner that runs
    # the test itself and all clean-up functions in the Twisted reactor.
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.__deferToThreadOrig = clusterservice.deferToThread
        self.patch(clusterservice, "deferToThread", self.__deferToThread)

    def __deferToThread(self, f, *args, **kwargs):
        d = self.__deferToThreadOrig(f, *args, **kwargs)
        self.addCleanup(lambda: d)  # Wait during teardown.
        return d


class TestClusterProtocol_ScanNetworks(
    MAASTestCaseThatWaitsForDeferredThreads
):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(cluster.ScanNetworks.commandName)
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_raises_refresh_already_in_progress_when_locked(self):
        with NamedLock("scan-networks"):
            with TestCase.assertRaises(
                self, exceptions.ScanNetworksAlreadyInProgress
            ):
                yield call_responder(
                    Cluster(), cluster.ScanNetworks, {"scan_all": True}
                )

    @inlineCallbacks
    def test_acquires_lock_when_scanning_releases_when_done(self):
        def mock_scan(*args, **kwargs):
            lock = NamedLock("scan-networks")
            self.assertTrue(lock.is_locked())

        self.patch(clusterservice, "executeScanNetworksSubprocess", mock_scan)

        yield call_responder(
            Cluster(), cluster.ScanNetworks, {"scan_all": True}
        )

        lock = NamedLock("scan-networks")
        self.assertFalse(lock.is_locked())

    @inlineCallbacks
    def test_releases_on_error(self):
        exception = factory.make_exception()
        mock_scan = self.patch(clusterservice, "executeScanNetworksSubprocess")
        mock_scan.side_effect = exception

        with TwistedLoggerFixture() as logger:
            yield call_responder(
                Cluster(), cluster.ScanNetworks, {"scan_all": True}
            )

        # The failure is logged
        self.assertIn(
            "Failed to scan all networks.",
            {err["why"] for err in logger.errors},
        )

        # The lock is released
        lock = NamedLock("scan-networks")
        self.assertFalse(lock.is_locked())

    @inlineCallbacks
    def test_wraps_subprocess_scan_in_maybeDeferred(self):
        mock_maybeDeferred = self.patch_autospec(
            clusterservice, "maybeDeferred"
        )
        mock_maybeDeferred.side_effect = (succeed(None),)

        yield call_responder(
            Cluster(), cluster.ScanNetworks, {"scan_all": True}
        )

        mock_maybeDeferred.assert_called_once_with(
            clusterservice.executeScanNetworksSubprocess,
            cidrs=None,
            force_ping=None,
            interface=None,
            scan_all=True,
            slow=None,
            threads=None,
        )

    def test_get_scan_all_networks_args_asserts_for_invalid_config(self):
        with self.assertRaisesRegex(
            AssertionError, "Invalid scan parameters.*"
        ):
            get_scan_all_networks_args()

    def test_get_scan_all_networks_args_returns_expected_binary_args(self):
        args = get_scan_all_networks_args(scan_all=True)
        self.assertEqual(
            args, [get_maas_common_command().encode("utf-8"), b"scan-network"]
        )

    def test_get_scan_all_networks_args_sudo(self):
        is_dev_environment_mock = self.patch_autospec(
            clusterservice, "is_dev_environment"
        )
        is_dev_environment_mock.return_value = False
        args = get_scan_all_networks_args(scan_all=True)
        self.assertEqual(
            args,
            [
                b"sudo",
                b"-n",
                get_maas_common_command().encode("utf-8"),
                b"scan-network",
            ],
        )

    def test_get_scan_all_networks_args_returns_supplied_cidrs(self):
        args = get_scan_all_networks_args(
            cidrs=[IPNetwork("192.168.0.0/24"), IPNetwork("192.168.1.0/24")]
        )
        self.assertEqual(
            args,
            [
                get_maas_common_command().encode("utf-8"),
                b"scan-network",
                b"192.168.0.0/24",
                b"192.168.1.0/24",
            ],
        )

    def test_get_scan_all_networks_args_returns_supplied_interface(self):
        args = get_scan_all_networks_args(interface="eth0")
        self.assertEqual(
            args,
            [
                get_maas_common_command().encode("utf-8"),
                b"scan-network",
                b"eth0",
            ],
        )

    def test_get_scan_all_networks_with_all_optional_arguments(self):
        threads = random.randint(1, 10)
        args = get_scan_all_networks_args(
            scan_all=False,
            slow=True,
            threads=threads,
            force_ping=True,
            interface="eth0",
            cidrs=[IPNetwork("192.168.0.0/24"), IPNetwork("192.168.1.0/24")],
        )
        self.assertEqual(
            args,
            [
                get_maas_common_command().encode("utf-8"),
                b"scan-network",
                b"--threads",
                str(threads).encode("utf-8"),
                b"--ping",
                b"--slow",
                b"eth0",
                b"192.168.0.0/24",
                b"192.168.1.0/24",
            ],
        )

    @inlineCallbacks
    def test_spawnProcessAndNullifyStdout_nullifies_stdout(self):
        done, protocol = makeDeferredWithProcessProtocol()
        args = [b"/bin/bash", b"-c", b"echo foo"]
        outReceived = Mock()
        protocol.outReceived = outReceived
        spawnProcessAndNullifyStdout(protocol, args)
        yield done
        outReceived.assert_not_called()

    @inlineCallbacks
    def test_spawnProcessAndNullifyStdout_captures_stderr(self):
        done, protocol = makeDeferredWithProcessProtocol()
        args = [b"/bin/bash", b"-c", b"echo foo >&2"]
        errReceived = Mock()
        protocol.errReceived = errReceived
        spawnProcessAndNullifyStdout(protocol, args)
        yield done
        errReceived.assert_called_once_with(b"foo\n")

    @inlineCallbacks
    def test_executeScanNetworksSubprocess(self):
        mock_scan_args = self.patch(
            clusterservice, "get_scan_all_networks_args"
        )
        mock_scan_args.return_value = [b"/bin/bash", b"-c", b"echo -n foo >&2"]
        mock_log_msg = self.patch(clusterservice.log, "msg")
        d = executeScanNetworksSubprocess()
        yield d
        mock_log_msg.assert_called_once_with("Scan all networks: foo")


class TestClusterProtocol_AddChassis(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(cluster.AddChassis.commandName)
        self.assertIsNotNone(responder)

    def test_chassis_type_virsh_calls_probe_virsh_and_enlist(self):
        mock_deferToThread = self.patch_autospec(
            clusterservice, "deferToThread"
        )
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        prefix_filter = factory.make_name("prefix_filter")
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "virsh",
                "hostname": hostname,
                "password": password,
                "accept_all": accept_all,
                "domain": domain,
                "prefix_filter": prefix_filter,
            },
        )
        mock_deferToThread.assert_called_once_with(
            clusterservice.probe_virsh_and_enlist,
            user,
            hostname,
            password,
            prefix_filter,
            accept_all,
            domain,
        )

    def test_chassis_type_powerkvm_calls_probe_virsh_and_enlist(self):
        mock_deferToThread = self.patch_autospec(
            clusterservice, "deferToThread"
        )
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        prefix_filter = factory.make_name("prefix_filter")
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "powerkvm",
                "hostname": hostname,
                "password": password,
                "accept_all": accept_all,
                "domain": domain,
                "prefix_filter": prefix_filter,
            },
        )
        mock_deferToThread.assert_called_once_with(
            clusterservice.probe_virsh_and_enlist,
            user,
            hostname,
            password,
            prefix_filter,
            accept_all,
            domain,
        )

    def test_chassis_type_virsh_logs_error_to_maaslog(self):
        fake_error = factory.make_name("error")
        self.patch(clusterservice, "maaslog")
        mock_deferToThread = self.patch_autospec(
            clusterservice, "deferToThread"
        )
        mock_deferToThread.return_value = fail(Exception(fake_error))
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        prefix_filter = factory.make_name("prefix_filter")
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "powerkvm",
                "hostname": hostname,
                "password": password,
                "accept_all": accept_all,
                "domain": domain,
                "prefix_filter": prefix_filter,
            },
        )
        clusterservice.maaslog.error.assert_any_call(
            "Failed to probe and enlist %s nodes: %s", "virsh", fake_error
        )

    def test_chassis_type_proxmox_calls_probe_proxmoxand_enlist(self):
        mock_proxmox = self.patch_autospec(
            clusterservice, "probe_proxmox_and_enlist"
        )
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        username = factory.make_name("username")
        password = factory.make_name("password")
        token_name = factory.make_name("token_name")
        token_secret = factory.make_name("token_secret")
        verify_ssl = factory.pick_bool()
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        prefix_filter = factory.make_name("prefix_filter")
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "proxmox",
                "hostname": hostname,
                "username": username,
                "password": password,
                "token_name": token_name,
                "token_secret": token_secret,
                "verify_ssl": verify_ssl,
                "accept_all": accept_all,
                "domain": domain,
                "prefix_filter": prefix_filter,
            },
        )
        mock_proxmox.assert_called_once_with(
            user,
            hostname,
            username,
            password,
            token_name,
            token_secret,
            verify_ssl,
            accept_all,
            domain,
            prefix_filter,
        )

    def test_chassis_type_proxmox_logs_error_to_maaslog(self):
        fake_error = factory.make_name("error")
        self.patch(clusterservice, "maaslog")
        mock_proxmox = self.patch_autospec(
            clusterservice, "probe_proxmox_and_enlist"
        )
        mock_proxmox.return_value = fail(Exception(fake_error))
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        username = factory.make_name("username")
        password = factory.make_name("password")
        token_name = factory.make_name("token_name")
        token_secret = factory.make_name("token_secret")
        verify_ssl = factory.pick_bool()
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        prefix_filter = factory.make_name("prefix_filter")
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "proxmox",
                "hostname": hostname,
                "username": username,
                "password": password,
                "token_name": token_name,
                "token_secret": token_secret,
                "verify_ssl": verify_ssl,
                "accept_all": accept_all,
                "domain": domain,
                "prefix_filter": prefix_filter,
            },
        )
        clusterservice.maaslog.error.assert_any_call(
            "Failed to probe and enlist %s nodes: %s",
            "proxmox",
            fake_error,
        )

    def test_chassis_type_hmcz_calls_probe_hmcz_and_enlist(self):
        mock_probe_hmcz_and_enlist = self.patch_autospec(
            clusterservice, "probe_hmcz_and_enlist"
        )
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        username = factory.make_name("username")
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        prefix_filter = factory.make_name("prefix_filter")
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "hmcz",
                "hostname": hostname,
                "username": username,
                "password": password,
                "accept_all": accept_all,
                "domain": domain,
                "prefix_filter": prefix_filter,
            },
        )
        mock_probe_hmcz_and_enlist.assert_called_once_with(
            user,
            hostname,
            username,
            password,
            accept_all,
            domain,
            prefix_filter,
            None,
        )

    def test_chassis_type_hmcz_logs_error_to_maaslog(self):
        fake_error = factory.make_name("error")
        self.patch(clusterservice, "maaslog")
        mock_probe_hmcz_and_enlist = self.patch_autospec(
            clusterservice, "probe_hmcz_and_enlist"
        )
        mock_probe_hmcz_and_enlist.return_value = fail(Exception(fake_error))
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        username = factory.make_name("username")
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        prefix_filter = factory.make_name("prefix_filter")
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "hmcz",
                "hostname": hostname,
                "username": username,
                "password": password,
                "accept_all": accept_all,
                "domain": domain,
                "prefix_filter": prefix_filter,
            },
        )
        clusterservice.maaslog.error.assert_any_call(
            "Failed to probe and enlist %s nodes: %s", "hmcz", fake_error
        )

    def test_chassis_type_vmware_calls_probe_vmware_and_enlist(self):
        mock_deferToThread = self.patch_autospec(
            clusterservice, "deferToThread"
        )
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        username = factory.make_name("username")
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        prefix_filter = factory.make_name("prefix_filter")
        port = random.choice([80, 443, 8080, 8443])
        protocol = random.choice(["http", "https"])
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "vmware",
                "hostname": hostname,
                "username": username,
                "password": password,
                "accept_all": accept_all,
                "domain": domain,
                "prefix_filter": prefix_filter,
                "port": port,
                "protocol": protocol,
            },
        )
        mock_deferToThread.assert_called_once_with(
            clusterservice.probe_vmware_and_enlist,
            user,
            hostname,
            username,
            password,
            port,
            protocol,
            prefix_filter,
            accept_all,
            domain,
        )

    def test_chassis_type_vmware_logs_error_to_maaslog(self):
        fake_error = factory.make_name("error")
        self.patch(clusterservice, "maaslog")
        mock_deferToThread = self.patch_autospec(
            clusterservice, "deferToThread"
        )
        mock_deferToThread.return_value = fail(Exception(fake_error))
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        username = factory.make_name("username")
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        prefix_filter = factory.make_name("prefix_filter")
        port = random.choice([80, 443, 8080, 8443])
        protocol = random.choice(["http", "https"])
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "vmware",
                "hostname": hostname,
                "username": username,
                "password": password,
                "accept_all": accept_all,
                "domain": domain,
                "prefix_filter": prefix_filter,
                "port": port,
                "protocol": protocol,
            },
        )
        clusterservice.maaslog.error.assert_any_call(
            "Failed to probe and enlist %s nodes: %s", "VMware", fake_error
        )

    def test_chassis_type_recs_calls_probe_and_enlist_recs(self):
        mock_deferToThread = self.patch_autospec(
            clusterservice, "deferToThread"
        )
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        username = factory.make_name("username")
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        port = random.randint(2000, 4000)
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "recs_box",
                "hostname": hostname,
                "username": username,
                "password": password,
                "accept_all": accept_all,
                "domain": domain,
                "port": port,
            },
        )
        mock_deferToThread.assert_called_once_with(
            clusterservice.probe_and_enlist_recs,
            user,
            hostname,
            port,
            username,
            password,
            accept_all,
            domain,
        )

    def test_chassis_type_recs_logs_error_to_maaslog(self):
        fake_error = factory.make_name("error")
        self.patch(clusterservice, "maaslog")
        mock_deferToThread = self.patch_autospec(
            clusterservice, "deferToThread"
        )
        mock_deferToThread.return_value = fail(Exception(fake_error))
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        username = factory.make_name("username")
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        port = random.randint(2000, 4000)
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "recs_box",
                "hostname": hostname,
                "username": username,
                "password": password,
                "accept_all": accept_all,
                "domain": domain,
                "port": port,
            },
        )
        clusterservice.maaslog.error.assert_any_call(
            "Failed to probe and enlist %s nodes: %s",
            "RECS|Box",
            fake_error,
        )

    def test_chassis_type_seamicro15k_calls_probe_seamicro15k_and_enlist(self):
        mock_deferToThread = self.patch_autospec(
            clusterservice, "deferToThread"
        )
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        username = factory.make_name("username")
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        power_control = random.choice(["ipmi", "restapi", "restapi2"])
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "seamicro15k",
                "hostname": hostname,
                "username": username,
                "password": password,
                "accept_all": accept_all,
                "domain": domain,
                "power_control": power_control,
            },
        )
        mock_deferToThread.assert_called_once_with(
            clusterservice.probe_seamicro15k_and_enlist,
            user,
            hostname,
            username,
            password,
            power_control,
            accept_all,
            domain,
        )

    def test_chassis_type_seamicro15k_logs_error_to_maaslog(self):
        fake_error = factory.make_name("error")
        self.patch(clusterservice, "maaslog")
        mock_deferToThread = self.patch_autospec(
            clusterservice, "deferToThread"
        )
        mock_deferToThread.return_value = fail(Exception(fake_error))
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        username = factory.make_name("username")
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        power_control = random.choice(["ipmi", "restapi", "restapi2"])
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "seamicro15k",
                "hostname": hostname,
                "username": username,
                "password": password,
                "accept_all": accept_all,
                "domain": domain,
                "power_control": power_control,
            },
        )
        clusterservice.maaslog.error.assert_any_call(
            "Failed to probe and enlist %s nodes: %s",
            "SeaMicro 15000",
            fake_error,
        )

    def test_chassis_type_mscm_calls_probe_mscm_and_enlist(self):
        mock_deferToThread = self.patch_autospec(
            clusterservice, "deferToThread"
        )
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        username = factory.make_name("username")
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "mscm",
                "hostname": hostname,
                "username": username,
                "password": password,
                "accept_all": accept_all,
                "domain": domain,
            },
        )
        mock_deferToThread.assert_called_once_with(
            clusterservice.probe_and_enlist_mscm,
            user,
            hostname,
            username,
            password,
            accept_all,
            domain,
        )

    def test_chassis_type_mscm_logs_error_to_maaslog(self):
        fake_error = factory.make_name("error")
        self.patch(clusterservice, "maaslog")
        mock_deferToThread = self.patch_autospec(
            clusterservice, "deferToThread"
        )
        mock_deferToThread.return_value = fail(Exception(fake_error))
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        username = factory.make_name("username")
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "mscm",
                "hostname": hostname,
                "username": username,
                "password": password,
                "accept_all": accept_all,
                "domain": domain,
            },
        )
        clusterservice.maaslog.error.assert_any_call(
            "Failed to probe and enlist %s nodes: %s",
            "Moonshot",
            fake_error,
        )

    def test_chassis_type_msftocs_calls_probe_msftocs_and_enlist(self):
        mock_deferToThread = self.patch_autospec(
            clusterservice, "deferToThread"
        )
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        username = factory.make_name("username")
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        port = random.randint(2000, 4000)
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "msftocs",
                "hostname": hostname,
                "username": username,
                "password": password,
                "accept_all": accept_all,
                "domain": domain,
                "port": port,
            },
        )
        mock_deferToThread.assert_called_once_with(
            clusterservice.probe_and_enlist_msftocs,
            user,
            hostname,
            port,
            username,
            password,
            accept_all,
            domain,
        )

    def test_chassis_type_msftocs_logs_error_to_maaslog(self):
        fake_error = factory.make_name("error")
        self.patch(clusterservice, "maaslog")
        mock_deferToThread = self.patch_autospec(
            clusterservice, "deferToThread"
        )
        mock_deferToThread.return_value = fail(Exception(fake_error))
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        username = factory.make_name("username")
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        port = random.randint(2000, 4000)
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "msftocs",
                "hostname": hostname,
                "username": username,
                "password": password,
                "accept_all": accept_all,
                "domain": domain,
                "port": port,
            },
        )
        clusterservice.maaslog.error.assert_any_call(
            "Failed to probe and enlist %s nodes: %s",
            "MicrosoftOCS",
            fake_error,
        )

    def test_chassis_type_ucsm_calls_probe_ucsm_and_enlist(self):
        mock_deferToThread = self.patch_autospec(
            clusterservice, "deferToThread"
        )
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        username = factory.make_name("username")
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "ucsm",
                "hostname": hostname,
                "username": username,
                "password": password,
                "accept_all": accept_all,
                "domain": domain,
            },
        )
        mock_deferToThread.assert_called_once_with(
            clusterservice.probe_and_enlist_ucsm,
            user,
            hostname,
            username,
            password,
            accept_all,
            domain,
        )

    def test_chassis_type_ucsm_logs_error_to_maaslog(self):
        fake_error = factory.make_name("error")
        self.patch(clusterservice, "maaslog")
        mock_deferToThread = self.patch_autospec(
            clusterservice, "deferToThread"
        )
        mock_deferToThread.return_value = fail(Exception(fake_error))
        user = factory.make_name("user")
        hostname = factory.make_hostname()
        username = factory.make_name("username")
        password = factory.make_name("password")
        accept_all = factory.pick_bool()
        domain = factory.make_name("domain")
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "ucsm",
                "hostname": hostname,
                "username": username,
                "password": password,
                "accept_all": accept_all,
                "domain": domain,
            },
        )
        clusterservice.maaslog.error.assert_any_call(
            "Failed to probe and enlist %s nodes: %s", "UCS", fake_error
        )

    def test_chassis_type_unknown_logs_error_to_maaslog(self):
        self.patch(clusterservice, "maaslog")
        user = factory.make_name("user")
        chassis_type = factory.make_name("chassis_type")
        call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": chassis_type,
                "hostname": factory.make_hostname(),
            },
        )
        clusterservice.maaslog.error.assert_any_call(
            f"Unknown chassis type {chassis_type}"
        )

    def test_returns_nothing(self):
        self.patch_autospec(clusterservice, "deferToThread")
        user = factory.make_name("user")
        response = call_responder(
            Cluster(),
            cluster.AddChassis,
            {
                "user": user,
                "chassis_type": "virsh",
                "hostname": factory.make_hostname(),
            },
        )
        self.assertEqual({}, response.result)


class TestClusterProtocol_DiscoverPodProjects(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.DiscoverPodProjects.commandName
        )
        self.assertIsNotNone(responder)

    def test_calls_discover_pod_projects(self):
        mock_discover_pod_projects = self.patch_autospec(
            pods, "discover_pod_projects"
        )
        mock_discover_pod_projects.return_value = succeed(
            {
                "projects": [
                    DiscoveredPodProject(
                        name="p1",
                        description="Project 1",
                    ),
                    DiscoveredPodProject(
                        name="p2",
                        description="Project 2",
                    ),
                ]
            }
        )
        pod_type = factory.make_name("pod_type")
        context = {}
        call_responder(
            Cluster(),
            cluster.DiscoverPodProjects,
            {
                "type": pod_type,
                "context": context,
            },
        )
        mock_discover_pod_projects.assert_called_once_with(pod_type, context)


class TestClusterProtocol_DiscoverPod(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(cluster.DiscoverPod.commandName)
        self.assertIsNotNone(responder)

    def test_calls_discover_pod(self):
        mock_discover_pod = self.patch_autospec(pods, "discover_pod")
        mock_discover_pod.return_value = succeed(
            {
                "pod": DiscoveredPod(
                    architectures=["amd64/generic"],
                    cores=random.randint(1, 8),
                    cpu_speed=random.randint(1000, 3000),
                    memory=random.randint(1024, 8192),
                    local_storage=0,
                    hints=DiscoveredPodHints(
                        cores=random.randint(1, 8),
                        cpu_speed=random.randint(1000, 2000),
                        memory=random.randint(1024, 8192),
                        local_storage=0,
                    ),
                    machines=[],
                )
            }
        )
        pod_type = factory.make_name("pod_type")
        context = {"data": factory.make_name("data")}
        pod_id = random.randint(1, 100)
        name = factory.make_name("pod")
        call_responder(
            Cluster(),
            cluster.DiscoverPod,
            {
                "type": pod_type,
                "context": context,
                "pod_id": pod_id,
                "name": name,
            },
        )
        mock_discover_pod.assert_called_once_with(
            pod_type, context, pod_id=pod_id, name=name
        )


class TestClusterProtocol_SendPodCommissioningResults(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.SendPodCommissioningResults.commandName
        )
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_calls_send_pod_commissioning_results(self):
        mock_send_pod_commissioning_results = self.patch(
            pods, "send_pod_commissioning_results"
        )
        mock_send_pod_commissioning_results.return_value = succeed({})
        pod_type = factory.make_name("pod_type")
        context = {"data": factory.make_name("data")}
        pod_id = random.randint(1, 100)
        name = factory.make_name("pod")
        system_id = factory.make_name("system_id")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        metadata_url = urlparse(factory.make_url())
        yield call_responder(
            Cluster(),
            cluster.SendPodCommissioningResults,
            {
                "type": pod_type,
                "context": context,
                "pod_id": pod_id,
                "name": name,
                "system_id": system_id,
                "consumer_key": consumer_key,
                "token_key": token_key,
                "token_secret": token_secret,
                "metadata_url": metadata_url,
            },
        )
        mock_send_pod_commissioning_results.assert_called_once_with(
            pod_type,
            context,
            pod_id,
            name,
            system_id,
            consumer_key,
            token_key,
            token_secret,
            metadata_url,
        )


class TestClusterProtocol_ComposeMachine(MAASTestCase):
    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.ComposeMachine.commandName
        )
        self.assertIsNotNone(responder)

    def test_calls_compose_machine(self):
        mock_compose_machine = self.patch_autospec(pods, "compose_machine")
        mock_compose_machine.return_value = succeed(
            {
                "machine": DiscoveredMachine(
                    hostname=factory.make_name("hostname"),
                    architecture="amd64/generic",
                    cores=random.randint(1, 8),
                    cpu_speed=random.randint(1000, 3000),
                    memory=random.randint(1024, 8192),
                    block_devices=[],
                    interfaces=[],
                ),
                "hints": DiscoveredPodHints(
                    cores=random.randint(1, 8),
                    cpu_speed=random.randint(1000, 2000),
                    memory=random.randint(1024, 8192),
                    local_storage=0,
                ),
            }
        )
        pod_type = factory.make_name("pod_type")
        context = {"data": factory.make_name("data")}
        request = RequestedMachine(
            hostname=factory.make_name("hostname"),
            architecture="amd64/generic",
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 3000),
            memory=random.randint(1024, 8192),
            block_devices=[
                RequestedMachineBlockDevice(size=random.randint(8, 16))
            ],
            interfaces=[RequestedMachineInterface()],
        )
        pod_id = random.randint(1, 100)
        name = factory.make_name("pod")
        call_responder(
            Cluster(),
            cluster.ComposeMachine,
            {
                "type": pod_type,
                "context": context,
                "request": request,
                "pod_id": pod_id,
                "name": name,
            },
        )
        mock_compose_machine.assert_called_once_with(
            pod_type, context, request, pod_id=pod_id, name=name
        )


class TestClusterProtocol_DecomposeMachine(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.DecomposeMachine.commandName
        )
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_calls_decompose_machine(self):
        mock_decompose_machine = self.patch_autospec(pods, "decompose_machine")
        mock_decompose_machine.return_value = succeed(
            {
                "hints": DiscoveredPodHints(
                    cores=1, cpu_speed=2, memory=3, local_storage=4
                )
            }
        )
        pod_type = factory.make_name("pod_type")
        context = {"data": factory.make_name("data")}
        pod_id = random.randint(1, 100)
        name = factory.make_name("pod")
        yield call_responder(
            Cluster(),
            cluster.DecomposeMachine,
            {
                "type": pod_type,
                "context": context,
                "pod_id": pod_id,
                "name": name,
            },
        )
        mock_decompose_machine.assert_called_once_with(
            pod_type, context, pod_id=pod_id, name=name
        )


class TestClusterProtocol_DisableAndShutoffRackd(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    assertRaises = TestCase.assertRaises

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(
            cluster.DisableAndShutoffRackd.commandName
        )
        self.assertIsNotNone(responder)

    def test_issues_restart_systemd(self):
        mock_call_and_check = self.patch(clusterservice, "call_and_check")
        response = call_responder(
            Cluster(), cluster.DisableAndShutoffRackd, {}
        )
        self.assertEqual({}, response.result)
        mock_call_and_check.assert_called_once_with(
            ["sudo", "systemctl", "restart", "maas-rackd"]
        )

    def test_remove_shared_secret(self):
        root_path = Path(self.useFixture(TempDir()).path)
        shared_secret_path = root_path / "secret"
        self.patch(
            utils_env.MAAS_SHARED_SECRET, "_path", lambda: shared_secret_path
        )
        self.patch(clusterservice, "call_and_check")
        shared_secret_path.write_text("secret")
        response = call_responder(
            Cluster(), cluster.DisableAndShutoffRackd, {}
        )
        self.assertEqual(response.result, {})
        self.assertFalse(shared_secret_path.exists())

    def test_issues_restart_snap(self):
        self.patch(clusterservice, "running_in_snap").return_value = True
        mock_call_and_check = self.patch(clusterservice, "call_and_check")
        response = call_responder(
            Cluster(), cluster.DisableAndShutoffRackd, {}
        )
        self.assertEqual({}, response.result)
        mock_call_and_check.assert_called_once_with(
            ["snapctl", "restart", "maas.pebble"]
        )

    @inlineCallbacks
    def test_raises_error_on_failure_systemd(self):
        mock_call_and_check = self.patch(clusterservice, "call_and_check")
        mock_call_and_check.side_effect = ExternalProcessError(
            1, "systemctl", "failure"
        )
        with self.assertRaises(exceptions.CannotDisableAndShutoffRackd):
            yield call_responder(Cluster(), cluster.DisableAndShutoffRackd, {})

    @inlineCallbacks
    def test_raises_error_on_failure_snap(self):
        mock_call_and_check = self.patch(clusterservice, "call_and_check")
        mock_call_and_check.side_effect = ExternalProcessError(
            random.randint(1, 255), "maas", "failure"
        )
        with self.assertRaises(exceptions.CannotDisableAndShutoffRackd):
            yield call_responder(Cluster(), cluster.DisableAndShutoffRackd, {})

    def test_snap_ignores_signal_error_code_on_restart(self):
        self.patch(clusterservice, "running_in_snap").return_value = True
        mock_call_and_check = self.patch(clusterservice, "call_and_check")
        mock_call_and_check.side_effect = ExternalProcessError(
            -15, "maas", "failure"
        )
        response = call_responder(
            Cluster(), cluster.DisableAndShutoffRackd, {}
        )
        self.assertEqual({}, response.result)
        self.assertEqual(1, mock_call_and_check.call_count)


class TestClusterProtocol_CheckIPs(MAASTestCaseThatWaitsForDeferredThreads):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_is_registered(self):
        protocol = Cluster()
        responder = protocol.locateResponder(cluster.CheckIPs.commandName)
        self.assertIsNotNone(responder)

    @inlineCallbacks
    def test_reports_results(self):
        ip_addresses = [
            {
                # Always exists, returns exit code of `0`.
                "ip_address": "127.0.0.1"
            },
            {
                # Broadcast that `ping` by default doesn't allow ping to
                # occur so the command returns exit code of `2`.
                "ip_address": "255.255.255.255"
            },
        ]

        # Fake `find_mac_via_arp` so its always returns a MAC address.
        fake_mac = factory.make_mac_address()
        mock_find_mac_via_arp = self.patch(clusterservice, "find_mac_via_arp")
        mock_find_mac_via_arp.return_value = fake_mac

        result = yield call_responder(
            Cluster(), cluster.CheckIPs, {"ip_addresses": ip_addresses}
        )

        self.assertEqual(
            result,
            {
                "ip_addresses": [
                    {
                        "ip_address": "127.0.0.1",
                        "used": True,
                        "interface": None,
                        "mac_address": fake_mac,
                    },
                    {
                        "ip_address": "255.255.255.255",
                        "used": False,
                        "interface": None,
                        "mac_address": None,
                    },
                ]
            },
        )
