# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.rackdservices.http`."""

__all__ = []

import random
from unittest.mock import (
    ANY,
    Mock,
)

import attr
from maastesting.factory import factory
from maastesting.fixtures import MAASRootFixture
from maastesting.matchers import (
    DocTestMatches,
    MockCalledOnceWith,
)
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from maastesting.twisted import (
    always_succeed_with,
    TwistedLoggerFixture,
)
from provisioningserver import services
from provisioningserver.events import EVENT_TYPES
from provisioningserver.rackdservices import http
from provisioningserver.rpc import (
    common,
    exceptions,
)
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from testtools.matchers import (
    Contains,
    Equals,
    FileContains,
    IsInstance,
    MatchesStructure,
)
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.web.http_headers import Headers
from twisted.web.server import Request
from twisted.web.test.test_web import DummyChannel


def prepareRegion(test):
    """Set up a mock region controller.

    :return: The running RPC service, and the protocol instance.
    """
    fixture = test.useFixture(MockLiveClusterToRegionRPCFixture())
    protocol, connecting = fixture.makeEventLoop()
    protocol.RegisterRackController.side_effect = always_succeed_with(
        {"system_id": factory.make_name("maas-id")})

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
            self.make_dir(), StubClusterClientService(), reactor)
        self.assertThat(service.call, Equals((service._tryUpdate, (), {})))

    def test_service_iterates_on_low_interval(self):
        service = http.RackHTTPService(
            self.make_dir(), StubClusterClientService(), reactor)
        self.assertThat(service.step, Equals(service.INTERVAL_LOW))

    def extract_regions(self, rpc_service):
        return frozenset({
            client.address[0]
            for _, client in rpc_service.connections.items()
        })

    def make_startable_RackHTTPService(self, *args, **kwargs):
        service = http.RackHTTPService(*args, **kwargs)
        service._orig_tryUpdate = service._tryUpdate
        self.patch(service, "_tryUpdate").return_value = (
            always_succeed_with(None))
        service.call = (service._tryUpdate, tuple(), {})
        return service

    @inlineCallbacks
    def test__getConfiguration_returns_configuration_object(self):
        rpc_service, protocol = yield prepareRegion(self)
        region_ips = self.extract_regions(rpc_service)
        service = self.make_startable_RackHTTPService(
            self.make_dir(), rpc_service, reactor)
        yield service.startService()
        self.addCleanup((yield service.stopService))
        observed = yield service._getConfiguration()

        self.assertThat(observed, IsInstance(http._Configuration))
        self.assertThat(
            observed, MatchesStructure.byEquality(upstream_http=region_ips))

    @inlineCallbacks
    def test__tryUpdate_writes_nginx_config_reloads_nginx(self):
        self.useFixture(MAASRootFixture())
        rpc_service, _ = yield prepareRegion(self)
        region_ips = self.extract_regions(rpc_service)
        resource_root = self.make_dir() + '/'
        service = self.make_startable_RackHTTPService(
            resource_root, rpc_service, reactor)

        # Mock service_monitor to catch reloadService.
        mock_reloadService = self.patch(http.service_monitor, 'reloadService')
        mock_reloadService.return_value = always_succeed_with(None)

        yield service.startService()
        self.addCleanup((yield service.stopService))
        yield service._orig_tryUpdate()

        # Verify the contents of the written config.
        target_path = http.compose_http_config_path('rackd.nginx.conf')
        self.assertThat(
            target_path,
            FileContains(matcher=Contains('alias %s;' % resource_root)))
        for region_ip in region_ips:
            self.assertThat(
                target_path, FileContains(
                    matcher=Contains('server %s:5240;' % region_ip)))
        self.assertThat(
            target_path,
            FileContains(
                matcher=Contains(
                    'proxy_pass http://maas-regions/MAAS/;')))
        self.assertThat(mock_reloadService, MockCalledOnceWith('http'))

        # If the configuration has not changed then a second call to
        # `_tryUpdate` does not result in another call to `_configure`.
        yield service._orig_tryUpdate()
        self.assertThat(mock_reloadService, MockCalledOnceWith('http'))

    @inlineCallbacks
    def test__getConfiguration_updates_interval_to_high(self):
        rpc_service, protocol = yield prepareRegion(self)
        service = http.RackHTTPService(self.make_dir(), rpc_service, reactor)
        yield service.startService()
        self.addCleanup((yield service.stopService))
        yield service._getConfiguration()

        self.assertThat(service.step, Equals(service.INTERVAL_HIGH))
        self.assertThat(service._loop.interval, Equals(service.INTERVAL_HIGH))

    def test__genRegionIps_groups_by_region(self):
        mock_rpc = Mock()
        mock_rpc.connections = {}
        for _ in range(3):
            region_name = factory.make_name('region')
            for _ in range(3):
                pid = random.randint(0, 10000)
                eventloop = '%s:pid=%s' % (region_name, pid)
                ip = factory.make_ip_address()
                mock_conn = Mock()
                mock_conn.address = (ip, random.randint(5240, 5250))
                mock_rpc.connections[eventloop] = mock_conn

        service = http.RackHTTPService(self.make_dir(), mock_rpc, reactor)
        region_ips = list(service._genRegionIps())
        self.assertEquals(3, len(region_ips))

    def test__genRegionIps_always_returns_same_result(self):
        mock_rpc = Mock()
        mock_rpc.connections = {}
        for _ in range(3):
            region_name = factory.make_name('region')
            for _ in range(3):
                pid = random.randint(0, 10000)
                eventloop = '%s:pid=%s' % (region_name, pid)
                ip = factory.make_ip_address()
                mock_conn = Mock()
                mock_conn.address = (ip, random.randint(5240, 5250))
                mock_rpc.connections[eventloop] = mock_conn

        service = http.RackHTTPService(self.make_dir(), mock_rpc, reactor)
        region_ips = frozenset(service._genRegionIps())
        for _ in range(3):
            self.assertEquals(region_ips, frozenset(service._genRegionIps()))

    def test__genRegionIps_formats_ipv6(self):
        mock_rpc = Mock()
        mock_rpc.connections = {}
        ip_addresses = set()
        for _ in range(3):
            region_name = factory.make_name('region')
            pid = random.randint(0, 10000)
            eventloop = '%s:pid=%s' % (region_name, pid)
            ip = factory.make_ipv6_address()
            ip_addresses.add('[%s]' % ip)
            mock_conn = Mock()
            mock_conn.address = (ip, random.randint(5240, 5250))
            mock_rpc.connections[eventloop] = mock_conn

        service = http.RackHTTPService(self.make_dir(), mock_rpc, reactor)
        region_ips = set(service._genRegionIps())
        self.assertEquals(ip_addresses, region_ips)


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
        self.patch(service, "_tryUpdate").return_value = (
            always_succeed_with(None))
        service.call = (service._tryUpdate, tuple(), {})
        return service

    @inlineCallbacks
    def test__tryUpdate_logs_errors_from_broken_method(self):
        # Patch the logger in the clusterservice so no log messages are printed
        # because the tests run in debug mode.
        self.patch(common.log, 'debug')

        # Mock service_monitor to catch reloadService.
        mock_reloadService = self.patch(http.service_monitor, 'reloadService')
        mock_reloadService.return_value = always_succeed_with(None)

        rpc_service, _ = yield prepareRegion(self)
        service = self.make_startable_RackHTTPService(
            self.make_dir(), rpc_service, reactor)
        self.patch_autospec(service, "_configure")  # No-op configuration.
        broken_method = self.patch_autospec(service, self.method)
        broken_method.side_effect = factory.make_exception()

        self.useFixture(MAASRootFixture())
        with TwistedLoggerFixture() as logger:
            yield service.startService()
            self.addCleanup((yield service.stopService))
            yield service._orig_tryUpdate()

        self.assertThat(
            logger.output, DocTestMatches(
                """
                Failed to update HTTP configuration.
                Traceback (most recent call last):
                ...
                maastesting.factory.TestException#...
                """))


class TestHTTPLogResource(MAASTestCase):

    def test_render_GET_logs_node_event_with_original_path_ip(self):
        path = factory.make_name('path')
        ip = factory.make_ip_address()
        request = Request(DummyChannel(), False)
        request.requestHeaders = Headers({
            'X-Original-URI': [path],
            'X-Original-Remote-IP': [ip],
        })

        log_info = self.patch(http.log, 'info')
        mock_deferLater = self.patch(http, 'deferLater')
        mock_deferLater.side_effect = always_succeed_with(None)

        resource = http.HTTPLogResource()
        resource.render_GET(request)

        self.assertThat(
            log_info,
            MockCalledOnceWith(
                "{path} requested by {remote_host}",
                path=path, remote_host=ip))
        self.assertThat(
            mock_deferLater,
            MockCalledOnceWith(
                ANY, 0, http.send_node_event_ip_address,
                event_type=EVENT_TYPES.NODE_HTTP_REQUEST,
                ip_address=ip, description=path))
