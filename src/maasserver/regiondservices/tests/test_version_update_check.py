# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from maasserver.regiondservices.version_update_check import (
    RegionVersionUpdateCheckService,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from provisioningserver.rackdservices import version_update_check
from provisioningserver.utils.snap import (
    SnapChannel,
    SnapVersion,
    SnapVersionsInfo,
)
from provisioningserver.utils.testing import MAASIDFixture


class TestRegionVersionUpdateCheckService(MAASTransactionServerTestCase):
    @wait_for()
    @inlineCallbacks
    def test_update_version(self):
        region = yield deferToDatabase(factory.make_RegionController)
        # Declare this region controller as the one running here.
        self.useFixture(MAASIDFixture(region.system_id))

        versions_info = SnapVersionsInfo(
            current=SnapVersion(
                revision="1234", version="3.0.0~alpha1-111-g.deadbeef"
            ),
            channel=SnapChannel(track="3.0"),
            update=SnapVersion(
                revision="5678", version="3.0.0~alpha2-222-g.cafecafe"
            ),
        )
        self.patch(
            version_update_check, "get_versions_info"
        ).return_value = versions_info

        service = RegionVersionUpdateCheckService(reactor)
        yield service.startService()
        yield service.stopService()

        info = yield deferToDatabase(getattr, region, "info")
        self.assertEqual(info.version, "3.0.0~alpha1-111-g.deadbeef")
        self.assertEqual(info.snap_revision, "1234")
        self.assertEqual(info.update_version, "3.0.0~alpha2-222-g.cafecafe")
        self.assertEqual(info.snap_update_revision, "5678")
        self.assertEqual(info.update_origin, "3.0/stable")
