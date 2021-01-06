# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for networks monitor."""


from crochet import wait_for
from fixtures import FakeLogger
from testtools.matchers import Contains, Equals, HasLength, IsInstance
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, succeed

from maasserver.models.interface import PhysicalInterface
from maasserver.regiondservices.networks_monitoring import (
    RegionNetworksMonitoringService,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.threads import deferToDatabase
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.utils.testing import MAASIDFixture


class TestRegionNetworksMonitoringService(MAASTransactionServerTestCase):
    """Tests for `RegionNetworksMonitoringService`."""

    @wait_for(30)
    @inlineCallbacks
    def test_updates_interfaces_in_database(self):
        region = yield deferToDatabase(factory.make_RegionController)
        region.owner = yield deferToDatabase(factory.make_admin)
        yield deferToDatabase(region.save)
        # Declare this region controller as the one running here.
        self.useFixture(MAASIDFixture(region.system_id))

        interfaces = {
            factory.make_name("eth"): {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            }
        }

        service = RegionNetworksMonitoringService(
            reactor, enable_beaconing=False
        )
        service.getInterfaces = lambda: succeed(interfaces)

        with FakeLogger("maas") as logger:
            service.startService()
            yield service.stopService()

        # Nothing was logged.
        self.assertIn(
            "Networks monitoring service: Process ID ", logger.output
        )

        def get_interfaces():
            return list(region.interface_set.all())

        interfaces_observed = yield deferToDatabase(get_interfaces)
        self.assertThat(interfaces_observed, HasLength(1))
        interface_observed = interfaces_observed[0]
        self.assertThat(interface_observed, IsInstance(PhysicalInterface))
        self.assertThat(interfaces, Contains(interface_observed.name))
        interface_expected = interfaces[interface_observed.name]
        self.assertThat(
            interface_observed.mac_address.raw,
            Equals(interface_expected["mac_address"]),
        )

    @wait_for(30)
    @inlineCallbacks
    def test_logs_error_when_running_region_controller_cannot_be_found(self):
        service = RegionNetworksMonitoringService(
            reactor, enable_beaconing=False
        )
        self.patch(service, "getInterfaces").return_value = {}

        with TwistedLoggerFixture() as logger:
            service.startService()
            yield service.stopService()

        self.assertIn(
            "Failed to update and/or record network interface configuration: "
            "RegionController matching query does not exist",
            logger.output,
        )
