# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for networks monitor."""

from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks, returnValue

from maasserver.regiondservices.networks_monitoring import (
    RegionNetworksMonitoringService,
)
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.utils import services
from provisioningserver.utils.testing import MAASIDFixture


class TestRegionNetworksMonitoringService(MAASTransactionServerTestCase):
    """Tests for `RegionNetworksMonitoringService`."""

    def setUp(self):
        super().setUp()
        self.mock_refresh = self.patch(services, "refresh")

    def wrap_deferred(self, obj, call_name):
        deferred = Deferred()

        orig_call = getattr(obj, call_name)

        @inlineCallbacks
        def wrapped_call():
            result = yield orig_call()
            if not deferred.called:
                deferred.callback(None)
            returnValue(result)

        setattr(obj, call_name, wrapped_call)
        return deferred

    @wait_for()
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

    @wait_for()
    @inlineCallbacks
    def test_get_refresh_details_running(self):
        example_url = factory.make_simple_http_url()
        self.useFixture(RegionConfigurationFixture(maas_url=example_url))
        region = yield deferToDatabase(factory.make_RegionController)
        region.owner = yield deferToDatabase(factory.make_admin)
        yield deferToDatabase(region.save)
        # Declare this region controller as the one running here.
        self.useFixture(MAASIDFixture(region.system_id))

        service = RegionNetworksMonitoringService(
            reactor,
            enable_beaconing=False,
        )

        deferred = self.wrap_deferred(service, "do_action")
        yield service.startService()
        yield deferred
        details = yield service.getRefreshDetails()
        region_token = yield deferToDatabase(region._get_token_for_controller)
        region_credentials = {
            "consumer_key": region_token.consumer.key,
            "token_key": region_token.key,
            "token_secret": region_token.secret,
        }
        self.assertEqual(
            (example_url, region.system_id, region_credentials), details
        )
