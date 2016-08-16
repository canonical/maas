# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.regiondservices.ntp`."""

__all__ = []

from unittest.mock import sentinel

from crochet import wait_for
from maasserver.models.config import Config
from maasserver.models.node import RegionController
from maasserver.regiondservices import ntp
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maastesting.fixtures import MAASRootFixture
from maastesting.matchers import (
    DocTestMatches,
    MockCalledOnceWith,
)
from maastesting.testcase import MAASTestCase
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.utils.testing import MAASIDFixture
from testtools.matchers import (
    Equals,
    Is,
    IsInstance,
    MatchesStructure,
)
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks


wait_for_reactor = wait_for(30)  # 30 seconds.


def make_endpoints(region):
    process = factory.make_RegionControllerProcess(region)
    return [
        factory.make_RegionControllerProcessEndpoint(process)
        for _ in range(3)
    ]


class TestRegionNetworkTimeProtocolService_Basic(MAASTestCase):
    """Basic tests for `RegionNetworkTimeProtocolService`."""

    def test_service_uses__tryUpdate_as_periodic_function(self):
        service = ntp.RegionNetworkTimeProtocolService(reactor)
        self.assertThat(service.call, Equals((service._tryUpdate, (), {})))

    def test_service_iterates_every_30_seconds(self):
        service = ntp.RegionNetworkTimeProtocolService(reactor)
        self.assertThat(service.step, Equals(30.0))


class TestRegionNetworkTimeProtocolService(MAASTransactionServerTestCase):
    """Tests for `RegionNetworkTimeProtocolService`."""

    def setUp(self):
        super(TestRegionNetworkTimeProtocolService, self).setUp()
        maas_id_fixture = MAASIDFixture(factory.make_name("maas-id"))
        self.maas_id = self.useFixture(maas_id_fixture).system_id
        self.useFixture(MAASRootFixture())

    @transactional
    def make_example_configuration(self):
        # Configure example time references.
        ntp_servers = {factory.make_name("ntp-server") for _ in range(5)}
        Config.objects.set_config("ntp_servers", " ".join(ntp_servers))
        # Populate the database with example peers.
        region = factory.make_RegionController()
        endpoints = make_endpoints(region)
        # Create a configuration object.
        return ntp._Configuration(
            ntp_servers, {frozenset(e.address for e in endpoints)})

    @wait_for_reactor
    @inlineCallbacks
    def test__tryUpdate_updates_ntp_server(self):
        service = ntp.RegionNetworkTimeProtocolService(reactor)
        configuration = yield deferToDatabase(self.make_example_configuration)
        self.patch_autospec(ntp, "configure")
        yield service._tryUpdate()
        self.assertThat(
            ntp.configure, MockCalledOnceWith(
                configuration.references, configuration.peers))
        # If the configuration has not changed then a second call to
        # _tryUpdate does not result in another call to _applyConfiguration.
        yield service._tryUpdate()
        self.assertThat(
            ntp.configure, MockCalledOnceWith(
                configuration.references, configuration.peers))


class TestRegionNetworkTimeProtocolService_Errors(
        MAASTransactionServerTestCase):
    """Tests for error handing in `RegionNetworkTimeProtocolService`."""

    scenarios = (
        ("_getConfiguration", dict(method="_getConfiguration")),
        ("_maybeApplyConfiguration", dict(method="_maybeApplyConfiguration")),
        ("_applyConfiguration", dict(method="_applyConfiguration")),
        ("_configurationApplied", dict(method="_configurationApplied")),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__tryUpdate_logs_errors_from_broken_method(self):
        service = ntp.RegionNetworkTimeProtocolService(reactor)
        broken_method = self.patch_autospec(service, self.method)
        broken_method.side_effect = factory.make_exception()

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


class TestRegionNetworkTimeProtocolService_Database(MAASServerTestCase):
    """Database tests for `RegionNetworkTimeProtocolService`."""

    def setUp(self):
        super(TestRegionNetworkTimeProtocolService_Database, self).setUp()
        maas_id_fixture = MAASIDFixture(factory.make_name("maas-id"))
        self.maas_id = self.useFixture(maas_id_fixture).system_id

    def test__getPeers_calls_through_to_RegionController(self):
        service = ntp.RegionNetworkTimeProtocolService(reactor)

        get_active_peer_addresses = self.patch_autospec(
            RegionController.objects, "get_active_peer_addresses")
        get_active_peer_addresses.return_value = sentinel.peers

        self.assertThat(service._getPeers(), Is(sentinel.peers))
        self.assertThat(get_active_peer_addresses, MockCalledOnceWith())

    def test__getReferences_returns_frozenset_of_ntp_servers(self):
        service = ntp.RegionNetworkTimeProtocolService(reactor)

        # Configure example time references.
        ntp_servers = {factory.make_name("ntp-server") for _ in range(5)}
        Config.objects.set_config("ntp_servers", " ".join(ntp_servers))

        observed = service._getReferences()
        expected = frozenset(ntp_servers)

        self.assertThat(observed, IsInstance(frozenset))
        self.assertThat(observed, Equals(expected))

    def test__getConfiguration_returns_configuration_object(self):
        service = ntp.RegionNetworkTimeProtocolService(reactor)

        # Configure example time references.
        ntp_servers = {factory.make_name("ntp-server") for _ in range(5)}
        Config.objects.set_config("ntp_servers", " ".join(ntp_servers))

        # Populate the database with example peers.
        region = factory.make_RegionController()
        endpoints = make_endpoints(region)

        observed = service._getConfiguration()
        self.assertThat(observed, IsInstance(ntp._Configuration))

        expected_references = frozenset(ntp_servers)
        expected_peers = frozenset({frozenset(e.address for e in endpoints)})

        self.assertThat(observed, MatchesStructure.byEquality(
            references=expected_references, peers=expected_peers))
