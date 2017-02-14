# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.rackdservices.ntp`."""

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
from provisioningserver.rackdservices import ntp
from provisioningserver.rpc import (
    exceptions,
    region,
)
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from provisioningserver.service_monitor import service_monitor
from testtools.matchers import (
    Equals,
    Is,
    IsInstance,
    MatchesStructure,
)
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks


def prepareRegion(
        test, *, is_region=False, is_rack=True, servers=None, peers=None):
    """Set up a mock region controller.

    It responds to `GetControllerType` and `GetTimeConfiguration`.

    :return: The running RPC service, and the protocol instance.
    """
    fixture = test.useFixture(MockLiveClusterToRegionRPCFixture())
    protocol, connecting = fixture.makeEventLoop(
        region.GetControllerType, region.GetTimeConfiguration)
    protocol.RegisterRackController.side_effect = always_succeed_with(
        {"system_id": factory.make_name("maas-id")})
    protocol.GetControllerType.side_effect = always_succeed_with(
        {"is_region": is_region, "is_rack": is_rack})
    protocol.GetTimeConfiguration.side_effect = always_succeed_with({
        "servers": [] if servers is None else servers,
        "peers": [] if peers is None else peers,
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


class TestRackNetworkTimeProtocolService(MAASTestCase):
    """Tests for `RackNetworkTimeProtocolService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5000)

    def test_service_uses__tryUpdate_as_periodic_function(self):
        service = ntp.RackNetworkTimeProtocolService(
            StubClusterClientService(), reactor)
        self.assertThat(service.call, Equals((service._tryUpdate, (), {})))

    def test_service_iterates_every_30_seconds(self):
        service = ntp.RackNetworkTimeProtocolService(
            StubClusterClientService(), reactor)
        self.assertThat(service.step, Equals(30.0))

    def make_servers_and_peers(self):
        return (
            frozenset({
                factory.make_ipv4_address(),
                factory.make_ipv6_address(),
                factory.make_hostname(),
            }),
            frozenset({
                factory.make_ipv4_address(),
                factory.make_ipv6_address(),
            }),
        )

    @inlineCallbacks
    def test__getConfiguration_returns_configuration_object(self):
        is_region, is_rack = factory.pick_bool(), factory.pick_bool()
        servers, peers = self.make_servers_and_peers()
        rpc_service, protocol = yield prepareRegion(
            self, is_region=is_region, is_rack=is_rack,
            servers=servers, peers=peers)
        service = ntp.RackNetworkTimeProtocolService(rpc_service, reactor)
        observed = yield service._getConfiguration()

        self.assertThat(observed, IsInstance(ntp._Configuration))
        self.assertThat(
            observed, MatchesStructure.byEquality(
                references=servers, peers=peers, is_region=is_region,
                is_rack=is_rack))

    @inlineCallbacks
    def test__tryUpdate_updates_ntp_server(self):
        self.useFixture(MAASRootFixture())
        servers, peers = self.make_servers_and_peers()
        rpc_service, _ = yield prepareRegion(
            self, servers=servers, peers=peers)
        service = ntp.RackNetworkTimeProtocolService(rpc_service, reactor)
        configure_rack = self.patch_autospec(ntp, "configure_rack")
        restartService = self.patch_autospec(service_monitor, "restartService")

        yield service._tryUpdate()
        self.assertThat(configure_rack, MockCalledOnceWith(servers, peers))
        self.assertThat(restartService, MockCalledOnceWith("ntp_rack"))
        # If the configuration has not changed then a second call to
        # `_tryUpdate` does not result in another call to `configure`.
        yield service._tryUpdate()
        self.assertThat(configure_rack, MockCalledOnceWith(servers, peers))
        self.assertThat(restartService, MockCalledOnceWith("ntp_rack"))

    @inlineCallbacks
    def test_is_silent_and_does_nothing_when_region_is_not_available(self):
        self.useFixture(MAASRootFixture())
        service = ntp.RackNetworkTimeProtocolService(
            StubClusterClientService(), reactor)
        self.patch_autospec(service, "_maybeApplyConfiguration")

        with TwistedLoggerFixture() as logger:
            yield service._tryUpdate()

        self.assertThat(logger.output, Equals(""))
        self.assertThat(service._maybeApplyConfiguration, MockNotCalled())

    @inlineCallbacks
    def test_is_silent_and_does_nothing_when_rack_is_not_recognised(self):
        self.useFixture(MAASRootFixture())
        rpc_service, protocol = yield prepareRegion(self)
        protocol.GetControllerType.side_effect = exceptions.NoSuchNode
        service = ntp.RackNetworkTimeProtocolService(rpc_service, reactor)
        self.patch_autospec(service, "_maybeApplyConfiguration")

        with TwistedLoggerFixture() as logger:
            yield service._tryUpdate()

        self.assertThat(logger.output, Equals(""))
        self.assertThat(service._maybeApplyConfiguration, MockNotCalled())

    @inlineCallbacks
    def test_is_silent_does_nothing_but_saves_config_when_is_region(self):
        self.useFixture(MAASRootFixture())
        rpc_service, _ = yield prepareRegion(self, is_region=True)
        service = ntp.RackNetworkTimeProtocolService(rpc_service, reactor)
        self.patch_autospec(ntp, "configure_rack")  # No-op configuration.

        # There is no most recently applied configuration.
        self.assertThat(service._configuration, Is(None))

        with TwistedLoggerFixture() as logger:
            yield service._tryUpdate()

        # The most recently applied configuration is set, though it was not
        # actually "applied" because this host was configured as a region+rack
        # controller, and the rack should not attempt to manage the NTP server
        # on a region+rack.
        self.assertThat(service._configuration, IsInstance(ntp._Configuration))
        # The configuration was not applied.
        self.assertThat(ntp.configure_rack, MockNotCalled())
        # Nothing was logged; there's no need for lots of chatter.
        self.assertThat(logger.output, Equals(""))


class TestRackNetworkTimeProtocolService_Errors(MAASTestCase):
    """Tests for error handing in `RackNetworkTimeProtocolService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    scenarios = (
        ("_getConfiguration", dict(method="_getConfiguration")),
        ("_maybeApplyConfiguration", dict(method="_maybeApplyConfiguration")),
        ("_applyConfiguration", dict(method="_applyConfiguration")),
        ("_configurationApplied", dict(method="_configurationApplied")),
    )

    @inlineCallbacks
    def test__tryUpdate_logs_errors_from_broken_method(self):
        rpc_service, _ = yield prepareRegion(self)
        self.patch_autospec(ntp, "configure_rack")  # No-op configuration.

        service = ntp.RackNetworkTimeProtocolService(rpc_service, reactor)
        broken_method = self.patch_autospec(service, self.method)
        broken_method.side_effect = factory.make_exception()

        # Ensure that we never actually execute against systemd.
        self.patch_autospec(service_monitor, "restartService")

        self.useFixture(MAASRootFixture())
        with TwistedLoggerFixture() as logger:
            yield service._tryUpdate()

        self.assertThat(
            logger.output, DocTestMatches(
                """
                Failed to update NTP configuration.
                Traceback (most recent call last):
                ...
                maastesting.factory.TestException#...
                """))
