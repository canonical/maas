# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for networks monitor."""


from crochet import wait_for
from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks

from maasserver.regiondservices.networks_monitoring import (
    RegionNetworksMonitoringService,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.threads import deferToDatabase
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.utils import services
from provisioningserver.utils.testing import MAASIDFixture


class TestRegionNetworksMonitoringService(MAASTransactionServerTestCase):
    """Tests for `RegionNetworksMonitoringService`."""

    def setUp(self):
        super().setUp()
        self.mock_refresh = self.patch(services, "refresh")

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

    @wait_for(30)
    @inlineCallbacks
    def test_get_refresh_details_running(self):
        region = yield deferToDatabase(factory.make_RegionController)
        region.owner = yield deferToDatabase(factory.make_admin)
        yield deferToDatabase(region.save)
        # Declare this region controller as the one running here.
        self.useFixture(MAASIDFixture(region.system_id))

        update_deferred = Deferred()
        service = RegionNetworksMonitoringService(
            reactor,
            enable_beaconing=False,
            update_interfaces_deferred=update_deferred,
        )
        yield service.startService()
        yield update_deferred
        details = yield service.getRefreshDetails()
        region_token = yield deferToDatabase(region._get_token_for_controller)
        region_credentials = {
            "consumer_key": region_token.consumer.key,
            "token_key": region_token.key,
            "token_secret": region_token.secret,
        }
        self.assertEqual((None, region.system_id, region_credentials), details)
