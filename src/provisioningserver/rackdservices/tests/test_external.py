# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.rackdservices.external`."""


import random
from unittest.mock import Mock

import attr
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.fixtures import MAASRootFixture
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from maastesting.twisted import always_succeed_with, TwistedLoggerFixture
from provisioningserver import services
from provisioningserver.rackdservices import external
from provisioningserver.rpc import clusterservice, common, exceptions, region
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from provisioningserver.service_monitor import service_monitor
from provisioningserver.testing.config import ClusterConfigurationFixture
from provisioningserver.utils.service_monitor import SERVICE_STATE
from provisioningserver.utils.testing import MAASIDFixture, MAASUUIDFixture

TIMEOUT = get_testing_timeout()


def prepareRegion(
    test,
    *,
    is_region=False,
    is_rack=True,
    servers=None,
    peers=None,
    trusted_networks=None,
    proxy_enabled=True,
    proxy_port=8000,
    proxy_allowed_cidrs=None,
    proxy_prefer_v4_proxy=False,
    syslog_port=5247,
):
    """Set up a mock region controller.

    It responds to `GetControllerType`, `GetTimeConfiguration`,
    `GetDNSConfiguration`, `GetProxyConfiguration`, and
    `GetSyslogConfiguration`.

    :return: The running RPC service, and the protocol instance.
    """
    fixture = test.useFixture(MockLiveClusterToRegionRPCFixture())
    protocol, connecting = fixture.makeEventLoop(
        region.GetControllerType,
        region.GetTimeConfiguration,
        region.GetDNSConfiguration,
        region.GetProxyConfiguration,
        region.GetSyslogConfiguration,
    )
    protocol.RegisterRackController.side_effect = always_succeed_with(
        {"system_id": factory.make_name("maas-id")}
    )
    protocol.GetControllerType.side_effect = always_succeed_with(
        {"is_region": is_region, "is_rack": is_rack}
    )
    protocol.GetTimeConfiguration.side_effect = always_succeed_with(
        {
            "servers": [] if servers is None else servers,
            "peers": [] if peers is None else peers,
        }
    )
    protocol.GetDNSConfiguration.side_effect = always_succeed_with(
        {
            "trusted_networks": (
                [] if trusted_networks is None else trusted_networks
            )
        }
    )
    if proxy_allowed_cidrs is None:
        proxy_allowed_cidrs = []
    protocol.GetProxyConfiguration.side_effect = always_succeed_with(
        {
            "enabled": proxy_enabled,
            "port": proxy_port,
            "allowed_cidrs": proxy_allowed_cidrs,
            "prefer_v4_proxy": proxy_prefer_v4_proxy,
        }
    )
    protocol.GetSyslogConfiguration.side_effect = always_succeed_with(
        {
            "port": syslog_port,
            "promtail_port": 5555,
        }
    )

    def connected(teardown):
        test.addCleanup(teardown)
        return services.getServiceNamed("rpc"), protocol

    return connecting.addCallback(connected)


def make_startable_RackExternalService(test, *args, **kwargs):
    service = external.RackExternalService(*args, **kwargs)
    service._orig_tryUpdate = service._tryUpdate
    test.patch(service, "_tryUpdate").return_value = always_succeed_with(None)
    service.call = (service._tryUpdate, tuple(), {})
    return service


@attr.s
class StubClusterClientService:
    """A stub `ClusterClientService` service that's never connected."""

    def getClientNow(self):
        raise exceptions.NoConnectionsAvailable()


class TestRackExternalService(MAASTestCase):
    """Tests for `RackExternalService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

    def test_service_uses__tryUpdate_as_periodic_function(self):
        service = external.RackExternalService(
            StubClusterClientService(), reactor
        )
        self.assertEqual((service._tryUpdate, (), {}), service.call)

    def test_service_iterates_on_low_interval(self):
        service = external.RackExternalService(
            StubClusterClientService(), reactor
        )
        self.assertEqual(service.INTERVAL_LOW, service.step)

    @inlineCallbacks
    def test_getConfiguration_updates_interval_to_high(self):
        rpc_service, protocol = yield prepareRegion(self)
        service = make_startable_RackExternalService(
            self, rpc_service, reactor, []
        )

        yield service.startService()
        self.addCleanup((yield service.stopService))

        yield service._orig_tryUpdate()

        self.assertEqual(service.INTERVAL_HIGH, service.step)
        self.assertEqual(service.INTERVAL_HIGH, service._loop.interval)

    @inlineCallbacks
    def test_is_silent_and_does_nothing_when_region_is_not_available(self):
        # Patch the logger in the clusterservice so no log messages are printed
        # because the tests run in debug mode.
        self.patch(common.log, "debug")
        self.useFixture(MAASRootFixture())
        ntp = external.RackNTP()
        service = make_startable_RackExternalService(
            self, StubClusterClientService(), reactor, [("NTP", ntp)]
        )
        self.patch_autospec(ntp, "_tryUpdate")

        yield service.startService()
        self.addCleanup((yield service.stopService))

        with TwistedLoggerFixture() as logger:
            yield service._tryUpdate()

        self.assertEqual("", logger.output)
        ntp._tryUpdate.assert_not_called()

    @inlineCallbacks
    def test_is_silent_and_does_nothing_when_rack_is_not_recognised(self):
        # Patch the logger in the clusterservice so no log messages are printed
        # because the tests run in debug mode.
        self.patch(common.log, "debug")
        self.useFixture(MAASRootFixture())
        rpc_service, protocol = yield prepareRegion(self)
        protocol.GetControllerType.side_effect = exceptions.NoSuchNode
        ntp = external.RackNTP()
        service = make_startable_RackExternalService(
            self, StubClusterClientService(), reactor, [("NTP", ntp)]
        )
        self.patch_autospec(ntp, "_tryUpdate")

        yield service.startService()
        self.addCleanup((yield service.stopService))

        with TwistedLoggerFixture() as logger:
            yield service._tryUpdate()

        self.assertEqual("", logger.output)
        ntp._tryUpdate.assert_not_called()


class TestRackNTP(MAASTestCase):
    """Tests for `RackNTP` in `RackExternalService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

    def make_RackNTP_ExternalService(self, rpc_service, reactor):
        ntp = external.RackNTP()
        service = make_startable_RackExternalService(
            self, rpc_service, reactor, [("NTP", ntp)]
        )
        return service, ntp

    def make_servers_and_peers(self):
        return (
            frozenset(
                {
                    factory.make_ipv4_address(),
                    factory.make_ipv6_address(),
                    factory.make_hostname(),
                }
            ),
            frozenset(
                {factory.make_ipv4_address(), factory.make_ipv6_address()}
            ),
        )

    @inlineCallbacks
    def test_getConfiguration_returns_configuration_object(self):
        is_region, is_rack = factory.pick_bool(), factory.pick_bool()
        servers, peers = self.make_servers_and_peers()
        rpc_service, protocol = yield prepareRegion(
            self,
            is_region=is_region,
            is_rack=is_rack,
            servers=servers,
            peers=peers,
        )
        service, ntp = self.make_RackNTP_ExternalService(rpc_service, reactor)
        config = yield service._getConfiguration()
        observed = ntp._getConfiguration(
            config.controller_type, config.time_configuration
        )

        self.assertIsInstance(observed, external._NTPConfiguration)
        self.assertEqual(observed.references, servers)
        self.assertEqual(observed.peers, peers)
        self.assertEqual(observed.is_region, is_region)
        self.assertEqual(observed.is_rack, is_rack)

    @inlineCallbacks
    def test_tryUpdate_updates_ntp_server(self):
        self.useFixture(MAASRootFixture())
        servers, peers = self.make_servers_and_peers()
        rpc_service, _ = yield prepareRegion(
            self, servers=servers, peers=peers
        )
        service, ntp = self.make_RackNTP_ExternalService(rpc_service, reactor)
        configure_rack = self.patch_autospec(external, "configure_rack")
        restartService = self.patch_autospec(service_monitor, "restartService")

        config = yield service._getConfiguration()
        yield ntp._tryUpdate(config)
        configure_rack.assert_called_once_with(servers, peers)
        restartService.assert_called_once_with("ntp_rack")
        # If the configuration has not changed then a second call to
        # `_tryUpdate` does not result in another call to `configure`.
        yield ntp._tryUpdate(config)
        configure_rack.assert_called_once_with(servers, peers)
        restartService.assert_called_once_with("ntp_rack")

    @inlineCallbacks
    def test_is_silent_does_nothing_but_saves_config_when_is_region(self):
        # Patch the logger in the clusterservice so no log messages are printed
        # because the tests run in debug mode.
        self.patch(common.log, "debug")
        self.useFixture(MAASRootFixture())
        rpc_service, _ = yield prepareRegion(self, is_region=True)
        service, ntp = self.make_RackNTP_ExternalService(rpc_service, reactor)
        self.patch_autospec(external, "configure_rack")  # No-op configuration.

        # There is no most recently applied configuration.
        self.assertIsNone(ntp._configuration)

        yield service.startService()
        self.addCleanup((yield service.stopService))

        with TwistedLoggerFixture() as logger:
            yield service._orig_tryUpdate()

        # The most recently applied configuration is set, though it was not
        # actually "applied" because this host was configured as a region+rack
        # controller, and the rack should not attempt to manage the NTP server
        # on a region+rack.
        self.assertIsInstance(ntp._configuration, external._NTPConfiguration)
        # The configuration was not applied.
        external.configure_rack.assert_not_called()
        # Nothing was logged; there's no need for lots of chatter.
        self.assertEqual("", logger.output)

    @inlineCallbacks
    def test_sets_ntp_rack_service_to_any_when_is_region(self):
        # Patch the logger in the clusterservice so no log messages are printed
        # because the tests run in debug mode.
        self.patch(common.log, "debug")
        self.useFixture(MAASRootFixture())
        rpc_service, _ = yield prepareRegion(self, is_region=True)
        service, ntp = self.make_RackNTP_ExternalService(rpc_service, reactor)
        self.patch_autospec(ntp, "_configure")  # No-op configuration.

        # There is no most recently applied configuration.
        self.assertIsNone(ntp._configuration)

        with TwistedLoggerFixture() as logger:
            yield service.startService()
            self.addCleanup((yield service.stopService))
            yield service._orig_tryUpdate()

        # Ensure that the service was set to any.
        service = service_monitor.getServiceByName("ntp_rack")
        self.assertEqual(
            (SERVICE_STATE.ANY, "managed by the region"),
            service.getExpectedState(),
        )
        # The most recently applied configuration is set, though it was not
        # actually "applied" because this host was configured as a region+rack
        # controller, and the rack should not attempt to manage the DNS server
        # on a region+rack.
        self.assertIsInstance(ntp._configuration, external._NTPConfiguration)
        # The configuration was not applied.
        ntp._configure.assert_not_called()
        # Nothing was logged; there's no need for lots of chatter.
        self.assertEqual("", logger.output)


class TestRackNetworkTimeProtocolService_Errors(MAASTestCase):
    """Tests for error handing in `RackExternalService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    scenarios = (
        ("_getConfiguration", dict(method="_getConfiguration")),
        ("_maybeApplyConfiguration", dict(method="_maybeApplyConfiguration")),
        ("_applyConfiguration", dict(method="_applyConfiguration")),
        ("_configurationApplied", dict(method="_configurationApplied")),
    )

    def setUp(self):
        super().setUp()
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

    @inlineCallbacks
    def test_tryUpdate_logs_errors_from_broken_method(self):
        # Patch the logger in the clusterservice so no log messages are printed
        # because the tests run in debug mode.
        self.patch(common.log, "debug")

        rpc_service, _ = yield prepareRegion(self)
        self.patch_autospec(external, "configure_rack")  # No-op configuration.

        ntp = external.RackNTP()
        service = make_startable_RackExternalService(
            self, rpc_service, reactor, [("NTP", ntp)]
        )
        broken_method = self.patch_autospec(ntp, self.method)
        broken_method.side_effect = factory.make_exception()

        # Ensure that we never actually execute against systemd.
        self.patch_autospec(service_monitor, "restartService")

        yield service.startService()
        self.addCleanup((yield service.stopService))

        self.useFixture(MAASRootFixture())
        with TwistedLoggerFixture() as logger:
            yield service._orig_tryUpdate()
        self.assertIn("Failed to update NTP configuration", logger.output)


class TestRackDNS(MAASTestCase):
    """Tests for `RackDNS` for `RackExternalService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

    def make_trusted_networks(self):
        return frozenset(
            {factory.make_ipv4_address(), factory.make_ipv6_address()}
        )

    def extract_regions(self, rpc_service):
        return frozenset(
            {
                client.address[0]
                for _, clients in rpc_service.connections.items()
                for client in clients
            }
        )

    def make_RackDNS_ExternalService(self, rpc_service, reactor):
        dns = external.RackDNS()
        service = make_startable_RackExternalService(
            self, rpc_service, reactor, [("DNS", dns)]
        )
        return service, dns

    @inlineCallbacks
    def test_getConfiguration_returns_configuration_object(self):
        is_region, is_rack = factory.pick_bool(), factory.pick_bool()
        trusted_networks = self.make_trusted_networks()
        rpc_service, protocol = yield prepareRegion(
            self,
            is_region=is_region,
            is_rack=is_rack,
            trusted_networks=trusted_networks,
        )
        region_ips = self.extract_regions(rpc_service)
        service, dns = self.make_RackDNS_ExternalService(rpc_service, reactor)
        yield service.startService()
        self.addCleanup((yield service.stopService))

        config = yield service._getConfiguration()
        observed = dns._getConfiguration(
            config.controller_type,
            config.dns_configuration,
            config.connections,
        )

        self.assertIsInstance(observed, external._DNSConfiguration)
        self.assertEqual(observed.upstream_dns, region_ips)
        self.assertEqual(observed.trusted_networks, trusted_networks)
        self.assertEqual(observed.is_region, is_region)
        self.assertEqual(observed.is_rack, is_rack)

    @inlineCallbacks
    def test_tryUpdate_updates_dns_server(self):
        self.useFixture(MAASRootFixture())
        trusted_networks = self.make_trusted_networks()
        rpc_service, _ = yield prepareRegion(
            self, trusted_networks=trusted_networks
        )
        region_ips = self.extract_regions(rpc_service)
        service, _ = self.make_RackDNS_ExternalService(rpc_service, reactor)

        mock_ensureService = self.patch_autospec(
            service_monitor, "ensureService"
        )
        mock_ensureService.side_effect = always_succeed_with(None)

        bind_write_options = self.patch_autospec(
            external, "bind_write_options"
        )
        bind_write_configuration = self.patch_autospec(
            external, "bind_write_configuration"
        )
        bind_reload_with_retries = self.patch_autospec(
            external, "bind_reload_with_retries"
        )

        yield service.startService()
        self.addCleanup((yield service.stopService))

        yield service._orig_tryUpdate()

        bind_write_options.assert_called_once_with(
            upstream_dns=sorted(region_ips), dnssec_validation="no"
        )
        bind_write_configuration.assert_called_once_with(
            [], sorted(trusted_networks)
        )
        mock_ensureService.assert_called_once_with("dns_rack")
        bind_reload_with_retries.assert_called_once_with()
        # If the configuration has not changed then a second call to
        # `_tryUpdate` does not result in another call to `_configure`.
        yield service._orig_tryUpdate()
        bind_write_options.assert_called_once_with(
            upstream_dns=list(sorted(region_ips)), dnssec_validation="no"
        )
        bind_write_configuration.assert_called_once_with(
            [], list(sorted(trusted_networks))
        )
        mock_ensureService.assert_called_once_with("dns_rack")
        bind_reload_with_retries.assert_called_once_with()

    @inlineCallbacks
    def test_is_silent_does_nothing_but_saves_config_when_is_region(self):
        # Patch the logger in the clusterservice so no log messages are printed
        # because the tests run in debug mode.
        self.patch(common.log, "debug")
        self.useFixture(MAASRootFixture())
        rpc_service, _ = yield prepareRegion(self, is_region=True)
        service, dns = self.make_RackDNS_ExternalService(rpc_service, reactor)
        self.patch_autospec(dns, "_configure")  # No-op configuration.

        # There is no most recently applied configuration.
        self.assertIsNone(dns._configuration)

        with TwistedLoggerFixture() as logger:
            yield service.startService()
            self.addCleanup((yield service.stopService))
            yield service._orig_tryUpdate()

        # The most recently applied configuration is set, though it was not
        # actually "applied" because this host was configured as a region+rack
        # controller, and the rack should not attempt to manage the DNS server
        # on a region+rack.
        self.assertIsInstance(dns._configuration, external._DNSConfiguration)
        # The configuration was not applied.
        dns._configure.assert_not_called()
        # Nothing was logged; there's no need for lots of chatter.
        self.assertEqual("", logger.output)

    @inlineCallbacks
    def test_sets_dns_rack_service_to_any_when_is_region(self):
        # Patch the logger in the clusterservice so no log messages are printed
        # because the tests run in debug mode.
        self.patch(common.log, "debug")
        self.useFixture(MAASRootFixture())
        rpc_service, _ = yield prepareRegion(self, is_region=True)
        service, dns = self.make_RackDNS_ExternalService(rpc_service, reactor)
        self.patch_autospec(dns, "_configure")  # No-op configuration.

        # There is no most recently applied configuration.
        self.assertIsNone(dns._configuration)

        with TwistedLoggerFixture() as logger:
            yield service.startService()
            self.addCleanup((yield service.stopService))
            yield service._orig_tryUpdate()

        # Ensure that the service was set to any.
        service = service_monitor.getServiceByName("dns_rack")
        self.assertEqual(
            (SERVICE_STATE.ANY, "managed by the region"),
            service.getExpectedState(),
        )
        # The most recently applied configuration is set, though it was not
        # actually "applied" because this host was configured as a region+rack
        # controller, and the rack should not attempt to manage the DNS server
        # on a region+rack.
        self.assertIsInstance(dns._configuration, external._DNSConfiguration)
        # The configuration was not applied.
        dns._configure.assert_not_called()
        # Nothing was logged; there's no need for lots of chatter.
        self.assertEqual("", logger.output)

    def test_genRegionIps_groups_by_region(self):
        mock_rpc = Mock()
        mock_rpc.connections = {}
        for _ in range(3):
            region_name = factory.make_name("region")
            for _ in range(3):
                pid = random.randint(0, 10000)
                eventloop = f"{region_name}:pid={pid}"
                ip = factory.make_ip_address()
                mock_conn = Mock()
                mock_conn.address = (ip, factory.pick_port(5240, 5250))
                mock_rpc.connections[eventloop] = {mock_conn}

        dns = external.RackDNS()
        region_ips = list(dns._genRegionIps(mock_rpc.connections))
        self.assertEqual(3, len(region_ips))

    def test_genRegionIps_always_returns_same_result(self):
        mock_rpc = Mock()
        mock_rpc.connections = {}
        for _ in range(3):
            region_name = factory.make_name("region")
            for _ in range(3):
                pid = random.randint(0, 10000)
                eventloop = f"{region_name}:pid={pid}"
                ip = factory.make_ip_address()
                mock_conn = Mock()
                mock_conn.address = (ip, factory.pick_port(5240, 5250))
                mock_rpc.connections[eventloop] = {mock_conn}

        dns = external.RackDNS()
        region_ips = frozenset(dns._genRegionIps(mock_rpc.connections))
        for _ in range(3):
            self.assertEqual(
                region_ips, frozenset(dns._genRegionIps(mock_rpc.connections))
            )


class TestRackProxy(MAASTestCase):
    """Tests for `RackProxy` for `RackExternalService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

    def make_cidrs(self):
        return frozenset(
            {
                str(factory.make_ipv4_network()),
                str(factory.make_ipv6_network()),
            }
        )

    def extract_regions(self, rpc_service):
        return frozenset(
            {
                client.address[0]
                for _, clients in rpc_service.connections.items()
                for client in clients
            }
        )

    def make_RackProxy_ExternalService(self, rpc_service, reactor):
        proxy = external.RackProxy()
        service = make_startable_RackExternalService(
            self, rpc_service, reactor, [("proxy", proxy)]
        )
        return service, proxy

    @inlineCallbacks
    def test_getConfiguration_returns_configuration_object(self):
        is_region, is_rack = factory.pick_bool(), factory.pick_bool()
        allowed_cidrs = self.make_cidrs()
        proxy_enabled = factory.pick_bool()
        proxy_prefer_v4_proxy = factory.pick_bool()
        proxy_port = factory.pick_port()
        rpc_service, protocol = yield prepareRegion(
            self,
            is_region=is_region,
            is_rack=is_rack,
            proxy_enabled=proxy_enabled,
            proxy_allowed_cidrs=allowed_cidrs,
            proxy_port=proxy_port,
            proxy_prefer_v4_proxy=proxy_prefer_v4_proxy,
        )
        region_ips = self.extract_regions(rpc_service)
        service, proxy = self.make_RackProxy_ExternalService(
            rpc_service, reactor
        )
        yield service.startService()
        self.addCleanup((yield service.stopService))

        config = yield service._getConfiguration()
        observed = proxy._getConfiguration(
            config.controller_type,
            config.proxy_configuration,
            config.connections,
        )

        self.assertIsInstance(observed, external._ProxyConfiguration)
        self.assertEqual(observed.enabled, proxy_enabled)
        self.assertEqual(observed.port, proxy_port)
        self.assertEqual(observed.allowed_cidrs, allowed_cidrs)
        self.assertEqual(observed.prefer_v4_proxy, proxy_prefer_v4_proxy)
        self.assertEqual(observed.upstream_proxies, region_ips)
        self.assertEqual(observed.is_region, is_region)
        self.assertEqual(observed.is_rack, is_rack)

    @inlineCallbacks
    def test_tryUpdate_updates_proxy_server(self):
        self.useFixture(MAASRootFixture())
        allowed_cidrs = self.make_cidrs()
        proxy_prefer_v4_proxy = factory.pick_bool()
        proxy_port = factory.pick_port()
        rpc_service, _ = yield prepareRegion(
            self,
            proxy_allowed_cidrs=allowed_cidrs,
            proxy_port=proxy_port,
            proxy_prefer_v4_proxy=proxy_prefer_v4_proxy,
        )
        region_ips = self.extract_regions(rpc_service)
        service, _ = self.make_RackProxy_ExternalService(rpc_service, reactor)

        write_config = self.patch_autospec(
            external.proxy_config, "write_config"
        )
        service_monitor = self.patch_autospec(external, "service_monitor")

        yield service.startService()
        self.addCleanup((yield service.stopService))

        yield service._orig_tryUpdate()

        expected_peers = sorted(
            f"http://{ip}:{proxy_port}" for ip in region_ips
        )
        write_config.assert_called_once_with(
            allowed_cidrs,
            peer_proxies=expected_peers,
            prefer_v4_proxy=proxy_prefer_v4_proxy,
            maas_proxy_port=proxy_port,
        )
        service_monitor.reloadService.assert_called_once_with("proxy_rack")
        # If the configuration has not changed then a second call to
        # `_tryUpdate` does not result in another call to `_configure`.
        yield service._orig_tryUpdate()
        write_config.assert_called_once_with(
            allowed_cidrs,
            peer_proxies=expected_peers,
            prefer_v4_proxy=proxy_prefer_v4_proxy,
            maas_proxy_port=proxy_port,
        )
        service_monitor.reloadService.assert_called_once_with("proxy_rack")

    @inlineCallbacks
    def test_sets_proxy_rack_service_to_any_when_is_region(self):
        # Patch the logger in the clusterservice so no log messages are printed
        # because the tests run in debug mode.
        self.patch(common.log, "debug")
        self.useFixture(MAASRootFixture())
        rpc_service, _ = yield prepareRegion(self, is_region=True)
        service, proxy = self.make_RackProxy_ExternalService(
            rpc_service, reactor
        )
        self.patch_autospec(proxy, "_configure")  # No-op configuration.

        # There is no most recently applied configuration.
        self.assertIsNone(proxy._configuration)

        with TwistedLoggerFixture() as logger:
            yield service.startService()
            self.addCleanup((yield service.stopService))
            yield service._orig_tryUpdate()

        # Ensure that the service was set to any.
        service = service_monitor.getServiceByName("proxy_rack")
        self.assertEqual(
            (SERVICE_STATE.ANY, "managed by the region"),
            service.getExpectedState(),
        )
        # The most recently applied configuration is set, though it was not
        # actually "applied" because this host was configured as a region+rack
        # controller, and the rack should not attempt to manage the DNS server
        # on a region+rack.
        self.assertIsInstance(
            proxy._configuration, external._ProxyConfiguration
        )
        # The configuration was not applied.
        proxy._configure.assert_not_called()
        # Nothing was logged; there's no need for lots of chatter.
        self.assertEqual("", logger.output)


class TestRackSyslog(MAASTestCase):
    """Tests for `RackSyslog` for `RackExternalService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

    def extract_regions(self, rpc_service):
        return frozenset(
            {
                (eventloop, client.address[0])
                for eventloop, clients in rpc_service.connections.items()
                for client in clients
            }
        )

    def make_RackSyslog_ExternalService(self, rpc_service, reactor):
        syslog = external.RackSyslog()
        service = make_startable_RackExternalService(
            self, rpc_service, reactor, [("syslog", syslog)]
        )
        return service, syslog

    @inlineCallbacks
    def test_getConfiguration_returns_configuration_object(self):
        port = factory.pick_port()
        is_region, is_rack = factory.pick_bool(), factory.pick_bool()
        rpc_service, protocol = yield prepareRegion(
            self, is_region=is_region, is_rack=is_rack, syslog_port=port
        )
        forwarders = self.extract_regions(rpc_service)
        service, syslog = self.make_RackSyslog_ExternalService(
            rpc_service, reactor
        )
        yield service.startService()
        self.addCleanup((yield service.stopService))

        config = yield service._getConfiguration()
        observed = syslog._getConfiguration(
            config.controller_type,
            config.syslog_configuration,
            config.connections,
        )

        self.assertIsInstance(observed, external._SyslogConfiguration)
        self.assertEqual(observed.port, port)
        self.assertEqual(observed.forwarders, forwarders)
        self.assertEqual(observed.promtail_port, 5555)
        self.assertEqual(observed.is_region, is_region)
        self.assertEqual(observed.is_rack, is_rack)

    @inlineCallbacks
    def test_tryUpdate_updates_syslog_server(self):
        self.useFixture(MAASRootFixture())
        port = factory.pick_port()
        rpc_service, _ = yield prepareRegion(self, syslog_port=port)
        forwarders = self.extract_regions(rpc_service)
        service, _ = self.make_RackSyslog_ExternalService(rpc_service, reactor)

        write_config = self.patch_autospec(
            external.syslog_config, "write_config"
        )
        service_monitor = self.patch_autospec(external, "service_monitor")

        yield service.startService()
        self.addCleanup((yield service.stopService))

        yield service._orig_tryUpdate()

        expected_forwards = [
            {"name": name, "ip": ip} for name, ip in forwarders
        ]
        write_config.assert_called_once_with(
            False,
            forwarders=expected_forwards,
            port=port,
            promtail_port=5555,
        )
        service_monitor.restartService.assert_called_once_with("syslog_rack")
        # If the configuration has not changed then a second call to
        # `_tryUpdate` does not result in another call to `_configure`.
        yield service._orig_tryUpdate()
        write_config.assert_called_once_with(
            False,
            forwarders=expected_forwards,
            port=port,
            promtail_port=5555,
        )
        service_monitor.restartService.assert_called_once_with("syslog_rack")

    @inlineCallbacks
    def test_sets_syslog_rack_service_to_any_when_is_region(self):
        # Patch the logger in the clusterservice so no log messages are printed
        # because the tests run in debug mode.
        self.patch(common.log, "debug")
        self.useFixture(MAASRootFixture())
        rpc_service, _ = yield prepareRegion(self, is_region=True)
        service, syslog = self.make_RackSyslog_ExternalService(
            rpc_service, reactor
        )
        self.patch_autospec(syslog, "_configure")  # No-op configuration.

        # There is no most recently applied configuration.
        self.assertIsNone(syslog._configuration)

        with TwistedLoggerFixture() as logger:
            yield service.startService()
            self.addCleanup((yield service.stopService))
            yield service._orig_tryUpdate()

        # Ensure that the service was set to any.
        service = service_monitor.getServiceByName("syslog_rack")
        self.assertEqual(
            (SERVICE_STATE.ANY, "managed by the region"),
            service.getExpectedState(),
        )
        # The most recently applied configuration is set, though it was not
        # actually "applied" because this host was configured as a region+rack
        # controller, and the rack should not attempt to manage the DNS server
        # on a region+rack.
        self.assertIsInstance(
            syslog._configuration, external._SyslogConfiguration
        )
        # The configuration was not applied.
        syslog._configure.assert_not_called()
        # Nothing was logged; there's no need for lots of chatter.
        self.assertEqual("", logger.output)


class TestRackAgent(MAASTestCase):
    """Tests for `RackAgent` for `RackExternalService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.useFixture(
            ClusterConfigurationFixture(
                debug=False,
                maas_url=[
                    "http://127.0.0.1:5240/MAAS",
                    "http://127.0.0.2:5240/MAAS",
                ],
            )
        )

    def test_getConfiguration_returns_configuration_object(self):
        maas_uuid = factory.make_UUID()
        system_id = factory.make_name("system-id")
        self.useFixture(MAASUUIDFixture(maas_uuid))
        self.useFixture(MAASIDFixture(system_id))

        agent = external.RackAgent()
        observed = agent._getConfiguration()

        self.assertEqual(observed.maas_uuid, maas_uuid)
        self.assertEqual(observed.system_id, system_id)
        self.assertEqual(observed.controllers, ["127.0.0.1", "127.0.0.2"])
        self.assertEqual(observed.log_level, "info")

    @inlineCallbacks
    def test_maybeApplyConfiguration_only_restarts_when_new_config(self):
        self.useFixture(MAASUUIDFixture(factory.make_UUID()))
        self.useFixture(MAASIDFixture(factory.make_name("system-id")))

        restartService = self.patch_autospec(service_monitor, "restartService")
        agent = external.RackAgent()
        agent._configure = Mock()
        self.assertIsNone(agent._configuration)

        config = agent._getConfiguration()

        yield agent._maybeApplyConfiguration(config)
        agent._configure.assert_called_once_with(config)
        restartService.assert_called_once_with("agent")
        self.assertIsNotNone(agent._configuration)

        agent._configure.reset_mock()
        restartService.reset_mock()
        yield agent._maybeApplyConfiguration(config)
        agent._configure.assert_not_called()
        restartService.assert_not_called()

    @inlineCallbacks
    def test_tryUpdate_uses_maybeApplyConfiguration(self):
        self.patch_autospec(service_monitor, "restartService")
        agent = external.RackAgent()
        config = agent._getConfiguration()
        agent._maybeApplyConfiguration = Mock()
        yield agent._tryUpdate(Mock())

        agent._maybeApplyConfiguration.assert_called_once_with(config)
