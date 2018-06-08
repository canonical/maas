# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.rackdservices.dns`."""

__all__ = []

import attr
from maastesting.factory import factory
from maastesting.fixtures import MAASRootFixture
from maastesting.matchers import (
    DocTestMatches,
    MockCalledOnceWith,
    MockNotCalled,
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
from provisioningserver.rackdservices import dns
from provisioningserver.rpc import (
    common,
    exceptions,
    region,
)
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from testtools.matchers import (
    Equals,
    Is,
    IsInstance,
    MatchesStructure,
)
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks


def prepareRegion(
        test, *, is_region=False, is_rack=True, trusted_networks=None):
    """Set up a mock region controller.

    It responds to `GetControllerType` and `GetDNSConfiguration`.

    :return: The running RPC service, and the protocol instance.
    """
    fixture = test.useFixture(MockLiveClusterToRegionRPCFixture())
    protocol, connecting = fixture.makeEventLoop(
        region.GetControllerType, region.GetDNSConfiguration)
    protocol.RegisterRackController.side_effect = always_succeed_with(
        {"system_id": factory.make_name("maas-id")})
    protocol.GetControllerType.side_effect = always_succeed_with(
        {"is_region": is_region, "is_rack": is_rack})
    protocol.GetDNSConfiguration.side_effect = always_succeed_with({
        "trusted_networks": (
            [] if trusted_networks is None else trusted_networks),
    })

    def connected(teardown):
        test.addCleanup(teardown)
        return services.getServiceNamed("rpc"), protocol

    return connecting.addCallback(connected)


@attr.s
class StubClusterClientService:
    """A stub `ClusterClientService` service that's never connected."""

    def getClientNow(self):
        raise exceptions.NoConnectionsAvailable()


class TestRackDNSService(MAASTestCase):
    """Tests for `RackDNSService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5000)

    def test_service_uses__tryUpdate_as_periodic_function(self):
        service = dns.RackDNSService(
            StubClusterClientService(), reactor)
        self.assertThat(service.call, Equals((service._tryUpdate, (), {})))

    def test_service_iterates_every_30_seconds(self):
        service = dns.RackDNSService(
            StubClusterClientService(), reactor)
        self.assertThat(service.step, Equals(30.0))

    def make_trusted_networks(self):
        return frozenset({
            factory.make_ipv4_address(),
            factory.make_ipv6_address(),
        })

    def extract_regions(self, rpc_service):
        return frozenset({
            client.address[0]
            for _, client in rpc_service.connections.items()
        })

    @inlineCallbacks
    def test__getConfiguration_returns_configuration_object(self):
        is_region, is_rack = factory.pick_bool(), factory.pick_bool()
        trusted_networks = self.make_trusted_networks()
        rpc_service, protocol = yield prepareRegion(
            self, is_region=is_region, is_rack=is_rack,
            trusted_networks=trusted_networks)
        region_ips = self.extract_regions(rpc_service)
        service = dns.RackDNSService(rpc_service, reactor)
        observed = yield service._getConfiguration()

        self.assertThat(observed, IsInstance(dns._Configuration))
        self.assertThat(
            observed, MatchesStructure.byEquality(
                upstream_dns=region_ips, trusted_networks=trusted_networks,
                is_region=is_region, is_rack=is_rack))

    @inlineCallbacks
    def test__tryUpdate_updates_ntp_server(self):
        self.useFixture(MAASRootFixture())
        trusted_networks = self.make_trusted_networks()
        rpc_service, _ = yield prepareRegion(
            self, trusted_networks=trusted_networks)
        region_ips = self.extract_regions(rpc_service)
        service = dns.RackDNSService(rpc_service, reactor)

        bind_write_options = self.patch_autospec(
            dns, "bind_write_options")
        bind_write_configuration = self.patch_autospec(
            dns, "bind_write_configuration")
        bind_reload_with_retries = self.patch_autospec(
            dns, "bind_reload_with_retries")

        yield service._tryUpdate()
        self.assertThat(
            bind_write_options,
            MockCalledOnceWith(
                upstream_dns=list(sorted(region_ips)), dnssec_validation='no'))
        self.assertThat(
            bind_write_configuration,
            MockCalledOnceWith([], list(sorted(trusted_networks))))
        self.assertThat(
            bind_reload_with_retries, MockCalledOnceWith())
        # If the configuration has not changed then a second call to
        # `_tryUpdate` does not result in another call to `_configure`.
        yield service._tryUpdate()
        self.assertThat(
            bind_write_options,
            MockCalledOnceWith(
                upstream_dns=list(sorted(region_ips)), dnssec_validation='no'))
        self.assertThat(
            bind_write_configuration,
            MockCalledOnceWith([], list(sorted(trusted_networks))))
        self.assertThat(
            bind_reload_with_retries, MockCalledOnceWith())

    @inlineCallbacks
    def test_is_silent_and_does_nothing_when_region_is_not_available(self):
        # Patch the logger in the clusterservice so no log messages are printed
        # because the tests run in debug mode.
        self.patch(common.log, 'debug')
        self.useFixture(MAASRootFixture())
        service = dns.RackDNSService(
            StubClusterClientService(), reactor)
        self.patch_autospec(service, "_maybeApplyConfiguration")

        with TwistedLoggerFixture() as logger:
            yield service._tryUpdate()

        self.assertThat(logger.output, Equals(""))
        self.assertThat(service._maybeApplyConfiguration, MockNotCalled())

    @inlineCallbacks
    def test_is_silent_and_does_nothing_when_rack_is_not_recognised(self):
        # Patch the logger in the clusterservice so no log messages are printed
        # because the tests run in debug mode.
        self.patch(common.log, 'debug')
        self.useFixture(MAASRootFixture())
        rpc_service, protocol = yield prepareRegion(self)
        protocol.GetControllerType.side_effect = exceptions.NoSuchNode
        service = dns.RackDNSService(rpc_service, reactor)
        self.patch_autospec(service, "_maybeApplyConfiguration")

        with TwistedLoggerFixture() as logger:
            yield service._tryUpdate()

        self.assertThat(logger.output, Equals(""))
        self.assertThat(service._maybeApplyConfiguration, MockNotCalled())

    @inlineCallbacks
    def test_is_silent_does_nothing_but_saves_config_when_is_region(self):
        # Patch the logger in the clusterservice so no log messages are printed
        # because the tests run in debug mode.
        self.patch(common.log, 'debug')
        self.useFixture(MAASRootFixture())
        rpc_service, _ = yield prepareRegion(self, is_region=True)
        service = dns.RackDNSService(rpc_service, reactor)
        self.patch_autospec(service, "_configure")  # No-op configuration.

        # There is no most recently applied configuration.
        self.assertThat(service._configuration, Is(None))

        with TwistedLoggerFixture() as logger:
            yield service._tryUpdate()

        # The most recently applied configuration is set, though it was not
        # actually "applied" because this host was configured as a region+rack
        # controller, and the rack should not attempt to manage the DNS server
        # on a region+rack.
        self.assertThat(service._configuration, IsInstance(dns._Configuration))
        # The configuration was not applied.
        self.assertThat(service._configure, MockNotCalled())
        # Nothing was logged; there's no need for lots of chatter.
        self.assertThat(logger.output, Equals(""))


class TestRackDNSService_Errors(MAASTestCase):
    """Tests for error handing in `RackDNSService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    scenarios = (
        ("_getConfiguration", dict(method="_getConfiguration")),
        ("_maybeApplyConfiguration", dict(method="_maybeApplyConfiguration")),
        ("_applyConfiguration", dict(method="_applyConfiguration")),
        ("_configurationApplied", dict(method="_configurationApplied")),
    )

    @inlineCallbacks
    def test__tryUpdate_logs_errors_from_broken_method(self):
        # Patch the logger in the clusterservice so no log messages are printed
        # because the tests run in debug mode.
        self.patch(common.log, 'debug')

        rpc_service, _ = yield prepareRegion(self)
        service = dns.RackDNSService(rpc_service, reactor)
        self.patch_autospec(service, "_configure")  # No-op configuration.
        broken_method = self.patch_autospec(service, self.method)
        broken_method.side_effect = factory.make_exception()

        self.useFixture(MAASRootFixture())
        with TwistedLoggerFixture() as logger:
            yield service._tryUpdate()

        self.assertThat(
            logger.output, DocTestMatches(
                """
                Failed to update DNS configuration.
                Traceback (most recent call last):
                ...
                maastesting.factory.TestException#...
                """))
