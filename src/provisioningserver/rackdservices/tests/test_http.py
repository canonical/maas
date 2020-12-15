# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.rackdservices.http`."""


import random
from unittest.mock import ANY, Mock

import attr
from testtools.matchers import (
    Contains,
    Equals,
    FileContains,
    IsInstance,
    MatchesStructure,
)
from tftp.errors import AccessViolation, FileNotFound
from twisted.application.service import Service
from twisted.internet import reactor
from twisted.internet.defer import fail, inlineCallbacks, succeed
from twisted.web.http_headers import Headers
from twisted.web.server import NOT_DONE_YET, Request
from twisted.web.test.test_web import DummyChannel, DummyRequest

from maastesting.factory import factory
from maastesting.fixtures import MAASRootFixture
from maastesting.matchers import DocTestMatches, MockCalledOnceWith
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from maastesting.twisted import always_succeed_with, TwistedLoggerFixture
from provisioningserver import services
from provisioningserver.boot import BytesReader
from provisioningserver.events import EVENT_TYPES
from provisioningserver.rackdservices import http
from provisioningserver.rpc import common, exceptions
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture


def prepareRegion(test):
    """Set up a mock region controller.

    :return: The running RPC service, and the protocol instance.
    """
    fixture = test.useFixture(MockLiveClusterToRegionRPCFixture())
    protocol, connecting = fixture.makeEventLoop()
    protocol.RegisterRackController.side_effect = always_succeed_with(
        {"system_id": factory.make_name("maas-id")}
    )

    def connected(teardown):
        test.addCleanup(teardown)
        return services.getServiceNamed("rpc"), protocol

    return connecting.addCallback(connected)


@attr.s
class StubClusterClientService:
    """A stub `ClusterClientService` service that's never connected."""

    def getClientNow(self):
        raise exceptions.NoConnectionsAvailable()


class TestRackHTTPService(MAASTestCase):
    """Tests for `RackHTTPService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5000)

    def test_service_uses__tryUpdate_as_periodic_function(self):
        service = http.RackHTTPService(
            self.make_dir(), StubClusterClientService(), reactor
        )
        self.assertThat(service.call, Equals((service._tryUpdate, (), {})))

    def test_service_iterates_on_low_interval(self):
        service = http.RackHTTPService(
            self.make_dir(), StubClusterClientService(), reactor
        )
        self.assertThat(service.step, Equals(service.INTERVAL_LOW))

    def extract_regions(self, rpc_service):
        return frozenset(
            {
                client.address[0]
                for _, client in rpc_service.connections.items()
            }
        )

    def make_startable_RackHTTPService(self, *args, **kwargs):
        service = http.RackHTTPService(*args, **kwargs)
        service._orig_tryUpdate = service._tryUpdate
        self.patch(service, "_tryUpdate").return_value = always_succeed_with(
            None
        )
        service.call = (service._tryUpdate, tuple(), {})
        return service

    @inlineCallbacks
    def test_getConfiguration_returns_configuration_object(self):
        rpc_service, protocol = yield prepareRegion(self)
        region_ips = self.extract_regions(rpc_service)
        service = self.make_startable_RackHTTPService(
            self.make_dir(), rpc_service, reactor
        )
        yield service.startService()
        self.addCleanup((yield service.stopService))
        observed = yield service._getConfiguration()

        self.assertThat(observed, IsInstance(http._Configuration))
        self.assertThat(
            observed, MatchesStructure.byEquality(upstream_http=region_ips)
        )

    @inlineCallbacks
    def test_tryUpdate_writes_nginx_config_reloads_nginx(self):
        self.useFixture(MAASRootFixture())
        rpc_service, _ = yield prepareRegion(self)
        region_ips = self.extract_regions(rpc_service)
        resource_root = self.make_dir() + "/"
        service = self.make_startable_RackHTTPService(
            resource_root, rpc_service, reactor
        )

        # Mock service_monitor to catch reloadService.
        mock_reloadService = self.patch(http.service_monitor, "reloadService")
        mock_reloadService.return_value = always_succeed_with(None)

        yield service.startService()
        self.addCleanup((yield service.stopService))
        yield service._orig_tryUpdate()

        # Verify the contents of the written config.
        target_path = http.compose_http_config_path("rackd.nginx.conf")
        self.assertThat(
            target_path,
            FileContains(matcher=Contains("alias %s;" % resource_root)),
        )
        for region_ip in region_ips:
            self.assertThat(
                target_path,
                FileContains(matcher=Contains("server %s:5240;" % region_ip)),
            )
        self.assertThat(
            target_path,
            FileContains(
                matcher=Contains("proxy_pass http://maas-regions/MAAS/;")
            ),
        )
        self.assertThat(mock_reloadService, MockCalledOnceWith("http"))

        # If the configuration has not changed then a second call to
        # `_tryUpdate` does not result in another call to `_configure`.
        yield service._orig_tryUpdate()
        self.assertThat(mock_reloadService, MockCalledOnceWith("http"))

    @inlineCallbacks
    def test_getConfiguration_updates_interval_to_high(self):
        rpc_service, protocol = yield prepareRegion(self)
        service = http.RackHTTPService(self.make_dir(), rpc_service, reactor)
        yield service.startService()
        self.addCleanup((yield service.stopService))
        yield service._getConfiguration()

        self.assertThat(service.step, Equals(service.INTERVAL_HIGH))
        self.assertThat(service._loop.interval, Equals(service.INTERVAL_HIGH))

    def test_genRegionIps_groups_by_region(self):
        mock_rpc = Mock()
        mock_rpc.connections = {}
        for _ in range(3):
            region_name = factory.make_name("region")
            for _ in range(3):
                pid = random.randint(0, 10000)
                eventloop = "%s:pid=%s" % (region_name, pid)
                ip = factory.make_ip_address()
                mock_conn = Mock()
                mock_conn.address = (ip, random.randint(5240, 5250))
                mock_rpc.connections[eventloop] = mock_conn

        service = http.RackHTTPService(self.make_dir(), mock_rpc, reactor)
        region_ips = list(service._genRegionIps())
        self.assertEqual(3, len(region_ips))

    def test_genRegionIps_always_returns_same_result(self):
        mock_rpc = Mock()
        mock_rpc.connections = {}
        for _ in range(3):
            region_name = factory.make_name("region")
            for _ in range(3):
                pid = random.randint(0, 10000)
                eventloop = "%s:pid=%s" % (region_name, pid)
                ip = factory.make_ip_address()
                mock_conn = Mock()
                mock_conn.address = (ip, random.randint(5240, 5250))
                mock_rpc.connections[eventloop] = mock_conn

        service = http.RackHTTPService(self.make_dir(), mock_rpc, reactor)
        region_ips = frozenset(service._genRegionIps())
        for _ in range(3):
            self.assertEqual(region_ips, frozenset(service._genRegionIps()))

    def test_genRegionIps_formats_ipv6(self):
        mock_rpc = Mock()
        mock_rpc.connections = {}
        ip_addresses = set()
        for _ in range(3):
            region_name = factory.make_name("region")
            pid = random.randint(0, 10000)
            eventloop = "%s:pid=%s" % (region_name, pid)
            ip = factory.make_ipv6_address()
            ip_addresses.add("[%s]" % ip)
            mock_conn = Mock()
            mock_conn.address = (ip, random.randint(5240, 5250))
            mock_rpc.connections[eventloop] = mock_conn

        service = http.RackHTTPService(self.make_dir(), mock_rpc, reactor)
        region_ips = set(service._genRegionIps())
        self.assertEqual(ip_addresses, region_ips)


class TestRackHTTPService_Errors(MAASTestCase):
    """Tests for error handing in `RackHTTPService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    scenarios = (
        ("_getConfiguration", dict(method="_getConfiguration")),
        ("_maybeApplyConfiguration", dict(method="_maybeApplyConfiguration")),
        ("_applyConfiguration", dict(method="_applyConfiguration")),
        ("_configurationApplied", dict(method="_configurationApplied")),
    )

    def make_startable_RackHTTPService(self, *args, **kwargs):
        service = http.RackHTTPService(*args, **kwargs)
        service._orig_tryUpdate = service._tryUpdate
        self.patch(service, "_tryUpdate").return_value = always_succeed_with(
            None
        )
        service.call = (service._tryUpdate, tuple(), {})
        return service

    @inlineCallbacks
    def test_tryUpdate_logs_errors_from_broken_method(self):
        # Patch the logger in the clusterservice so no log messages are printed
        # because the tests run in debug mode.
        self.patch(common.log, "debug")

        # Mock service_monitor to catch reloadService.
        mock_reloadService = self.patch(http.service_monitor, "reloadService")
        mock_reloadService.return_value = always_succeed_with(None)

        rpc_service, _ = yield prepareRegion(self)
        service = self.make_startable_RackHTTPService(
            self.make_dir(), rpc_service, reactor
        )
        self.patch_autospec(service, "_configure")  # No-op configuration.
        broken_method = self.patch_autospec(service, self.method)
        broken_method.side_effect = factory.make_exception()

        self.useFixture(MAASRootFixture())
        with TwistedLoggerFixture() as logger:
            yield service.startService()
            self.addCleanup((yield service.stopService))
            yield service._orig_tryUpdate()

        self.assertThat(
            logger.output,
            DocTestMatches(
                """
                Failed to update HTTP configuration.
                Traceback (most recent call last):
                ...
                maastesting.factory.TestException#...
                """
            ),
        )


class TestHTTPLogResource(MAASTestCase):
    def test_render_GET_logs_node_event_with_original_path_ip(self):
        path = factory.make_name("path")
        ip = factory.make_ip_address()
        request = Request(DummyChannel(), False)
        request.requestHeaders = Headers(
            {"X-Original-URI": [path], "X-Original-Remote-IP": [ip]}
        )

        log_info = self.patch(http.log, "info")
        mock_deferLater = self.patch(http, "deferLater")
        mock_deferLater.side_effect = always_succeed_with(None)

        resource = http.HTTPLogResource()
        resource.render_GET(request)

        self.assertThat(
            log_info,
            MockCalledOnceWith(
                "{path} requested by {remote_host}", path=path, remote_host=ip
            ),
        )
        self.assertThat(
            mock_deferLater,
            MockCalledOnceWith(
                ANY,
                0,
                http.send_node_event_ip_address,
                event_type=EVENT_TYPES.NODE_HTTP_REQUEST,
                ip_address=ip,
                description=path,
            ),
        )

    def test_render_GET_logs_node_event_status_message(self):
        path = factory.make_name("squashfs")
        ip = factory.make_ip_address()
        request = Request(DummyChannel(), False)
        request.requestHeaders = Headers(
            {"X-Original-URI": [path], "X-Original-Remote-IP": [ip]}
        )

        mock_deferLater = self.patch(http, "deferLater")
        mock_deferLater.side_effect = always_succeed_with(None)
        mock_send_node_event_ip_address = self.patch(
            http, "send_node_event_ip_address"
        )

        resource = http.HTTPLogResource()
        resource.render_GET(request)

        self.assertThat(
            mock_deferLater,
            MockCalledOnceWith(
                ANY,
                0,
                http.send_node_event_ip_address,
                event_type=EVENT_TYPES.NODE_HTTP_REQUEST,
                ip_address=ip,
                description=path,
            ),
        )
        self.assertThat(
            mock_send_node_event_ip_address,
            MockCalledOnceWith(
                event_type=EVENT_TYPES.LOADING_EPHEMERAL, ip_address=ip
            ),
        )


class TestHTTPBootResource(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def setUp(self):
        super().setUp()
        self.tftp = Service()
        self.tftp.setName("tftp")
        self.tftp.backend = Mock()
        self.tftp.backend.get_reader = Mock()
        self.tftp.setServiceParent(services)

        def teardown():
            if self.tftp:
                self.tftp.disownServiceParent()
                self.tftp = None

        self.addCleanup(teardown)

    def render_GET(self, resource, request):
        result = resource.render_GET(request)
        if isinstance(result, bytes):
            request.write(result)
            request.finish()
            return succeed(None)
        elif result is NOT_DONE_YET:
            if request.finished:
                return succeed(None)
            else:
                return request.notifyFinish()
        else:
            raise ValueError("Unexpected return value: %r" % (result,))

    @inlineCallbacks
    def test_render_GET_503_when_no_tftp_service(self):
        # Remove the fake 'tftp' service.
        self.tftp.disownServiceParent()
        self.tftp = None

        path = factory.make_name("path")
        ip = factory.make_ip_address()
        request = DummyRequest([path.encode("utf-8")])
        request.requestHeaders = Headers(
            {
                "X-Server-Addr": ["192.168.1.1"],
                "X-Server-Port": ["5248"],
                "X-Forwarded-For": [ip],
                "X-Forwarded-Port": ["%s" % factory.pick_port()],
            }
        )

        self.patch(http.log, "info")
        mock_deferLater = self.patch(http, "deferLater")
        mock_deferLater.side_effect = always_succeed_with(None)

        resource = http.HTTPBootResource()
        yield self.render_GET(resource, request)

        self.assertEqual(503, request.responseCode)
        self.assertEqual(
            b"HTTP boot service not ready.", b"".join(request.written)
        )

    @inlineCallbacks
    def test_render_GET_400_when_no_local_addr(self):
        path = factory.make_name("path")
        ip = factory.make_ip_address()
        request = DummyRequest([path.encode("utf-8")])
        request.requestHeaders = Headers(
            {
                "X-Forwarded-For": [ip],
                "X-Forwarded-Port": ["%s" % factory.pick_port()],
            }
        )

        self.patch(http.log, "info")
        mock_deferLater = self.patch(http, "deferLater")
        mock_deferLater.side_effect = always_succeed_with(None)

        resource = http.HTTPBootResource()
        yield self.render_GET(resource, request)

        self.assertEqual(400, request.responseCode)
        self.assertEqual(
            b"Missing X-Server-Addr and X-Forwarded-For HTTP headers.",
            b"".join(request.written),
        )

    @inlineCallbacks
    def test_render_GET_400_when_no_remote_addr(self):
        path = factory.make_name("path")
        request = DummyRequest([path.encode("utf-8")])
        request.requestHeaders = Headers(
            {"X-Server-Addr": ["192.168.1.1"], "X-Server-Port": ["5248"]}
        )

        self.patch(http.log, "info")
        mock_deferLater = self.patch(http, "deferLater")
        mock_deferLater.side_effect = always_succeed_with(None)

        resource = http.HTTPBootResource()
        yield self.render_GET(resource, request)

        self.assertEqual(400, request.responseCode)
        self.assertEqual(
            b"Missing X-Server-Addr and X-Forwarded-For HTTP headers.",
            b"".join(request.written),
        )

    @inlineCallbacks
    def test_render_GET_403_access_violation(self):
        path = factory.make_name("path")
        ip = factory.make_ip_address()
        request = DummyRequest([path.encode("utf-8")])
        request.requestHeaders = Headers(
            {
                "X-Server-Addr": ["192.168.1.1"],
                "X-Server-Port": ["5248"],
                "X-Forwarded-For": [ip],
                "X-Forwarded-Port": ["%s" % factory.pick_port()],
            }
        )

        self.patch(http.log, "info")
        mock_deferLater = self.patch(http, "deferLater")
        mock_deferLater.side_effect = always_succeed_with(None)

        self.tftp.backend.get_reader.return_value = fail(AccessViolation())

        resource = http.HTTPBootResource()
        yield self.render_GET(resource, request)

        self.assertEqual(403, request.responseCode)
        self.assertEqual(b"", b"".join(request.written))

    @inlineCallbacks
    def test_render_GET_404_file_not_found(self):
        path = factory.make_name("path")
        ip = factory.make_ip_address()
        request = DummyRequest([path.encode("utf-8")])
        request.requestHeaders = Headers(
            {
                "X-Server-Addr": ["192.168.1.1"],
                "X-Server-Port": ["5248"],
                "X-Forwarded-For": [ip],
                "X-Forwarded-Port": ["%s" % factory.pick_port()],
            }
        )

        self.patch(http.log, "info")
        mock_deferLater = self.patch(http, "deferLater")
        mock_deferLater.side_effect = always_succeed_with(None)

        self.tftp.backend.get_reader.return_value = fail(FileNotFound(path))

        resource = http.HTTPBootResource()
        yield self.render_GET(resource, request)

        self.assertEqual(404, request.responseCode)
        self.assertEqual(b"", b"".join(request.written))

    @inlineCallbacks
    def test_render_GET_500_server_error(self):
        path = factory.make_name("path")
        ip = factory.make_ip_address()
        request = DummyRequest([path.encode("utf-8")])
        request.requestHeaders = Headers(
            {
                "X-Server-Addr": ["192.168.1.1"],
                "X-Server-Port": ["5248"],
                "X-Forwarded-For": [ip],
                "X-Forwarded-Port": ["%s" % factory.pick_port()],
            }
        )

        self.patch(http.log, "info")
        mock_deferLater = self.patch(http, "deferLater")
        mock_deferLater.side_effect = always_succeed_with(None)

        exc = factory.make_exception("internal error")
        self.tftp.backend.get_reader.return_value = fail(exc)

        resource = http.HTTPBootResource()
        yield self.render_GET(resource, request)

        self.assertEqual(500, request.responseCode)
        self.assertEqual(str(exc).encode("utf-8"), b"".join(request.written))

    @inlineCallbacks
    def test_render_GET_produces_from_reader(self):
        path = factory.make_name("path")
        ip = factory.make_ip_address()
        request = DummyRequest([path.encode("utf-8")])
        request.requestHeaders = Headers(
            {
                "X-Server-Addr": ["192.168.1.1"],
                "X-Server-Port": ["5248"],
                "X-Forwarded-For": [ip],
                "X-Forwarded-Port": ["%s" % factory.pick_port()],
            }
        )

        self.patch(http.log, "info")
        mock_deferLater = self.patch(http, "deferLater")
        mock_deferLater.side_effect = always_succeed_with(None)

        content = factory.make_string(size=100).encode("utf-8")
        reader = BytesReader(content)
        self.tftp.backend.get_reader.return_value = succeed(reader)

        resource = http.HTTPBootResource()
        yield self.render_GET(resource, request)

        self.assertEqual(
            [100], request.responseHeaders.getRawHeaders(b"Content-Length")
        )
        self.assertEqual(content, b"".join(request.written))

    @inlineCallbacks
    def test_render_GET_logs_node_event_with_original_path_ip(self):
        path = factory.make_name("path")
        ip = factory.make_ip_address()
        request = DummyRequest([path.encode("utf-8")])
        request.requestHeaders = Headers(
            {
                "X-Server-Addr": ["192.168.1.1"],
                "X-Server-Port": ["5248"],
                "X-Forwarded-For": [ip],
                "X-Forwarded-Port": ["%s" % factory.pick_port()],
            }
        )

        log_info = self.patch(http.log, "info")
        mock_deferLater = self.patch(http, "deferLater")
        mock_deferLater.side_effect = always_succeed_with(None)

        self.tftp.backend.get_reader.return_value = fail(AccessViolation())

        resource = http.HTTPBootResource()
        yield self.render_GET(resource, request)

        self.assertThat(
            log_info,
            MockCalledOnceWith(
                "{path} requested by {remoteHost}", path=path, remoteHost=ip
            ),
        )
        self.assertThat(
            mock_deferLater,
            MockCalledOnceWith(
                ANY,
                0,
                http.send_node_event_ip_address,
                event_type=EVENT_TYPES.NODE_HTTP_REQUEST,
                ip_address=ip,
                description=path,
            ),
        )
