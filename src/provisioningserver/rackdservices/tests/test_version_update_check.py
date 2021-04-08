# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE)

import dataclasses

from twisted.internet.defer import inlineCallbacks, returnValue

from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver import services
from provisioningserver.rackdservices import version_update_check
from provisioningserver.rackdservices.version_update_check import (
    VersionUpdateCheckService,
)
from provisioningserver.rpc import clusterservice, region
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from provisioningserver.utils.snap import (
    SnapChannel,
    SnapVersion,
    SnapVersionsInfo,
)


class TestVersionUpdateCheckService(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(debug=True, timeout=5)

    @inlineCallbacks
    def create_fake_rpc_service(self):
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.UpdateControllerState
        )
        self.addCleanup((yield connecting))
        returnValue(protocol)

    def test_get_versions_state_in_snap(self):
        service = VersionUpdateCheckService(None)
        versions_info = SnapVersionsInfo(
            current=SnapVersion(
                revision="1234", version="3.0.0-alpha1-111-g.deadbeef"
            ),
            channel=SnapChannel(track="3.0"),
            update=SnapVersion(
                revision="5678", version="3.0.0-alpha2-222-g.cafecafe"
            ),
        )
        self.patch(
            version_update_check, "get_snap_versions_info"
        ).return_value = versions_info
        self.assertEqual(
            service._get_versions_state(),
            {
                "snap": dataclasses.asdict(versions_info),
            },
        )

    def test_get_versions_state_not_in_snap(self):
        service = VersionUpdateCheckService(None)
        self.patch(
            version_update_check, "get_snap_versions_info"
        ).return_value = None
        self.assertNotIn("snap", service._get_versions_state())

    @inlineCallbacks
    def test_sends_version_state_update(self):
        protocol = yield self.create_fake_rpc_service()
        rpc_service = services.getServiceNamed("rpc")
        service = VersionUpdateCheckService(rpc_service)
        versions_info = SnapVersionsInfo(
            current=SnapVersion(
                revision="1234", version="3.0.0-alpha1-111-g.deadbeef"
            ),
            channel=SnapChannel(track="3.0"),
            update=SnapVersion(
                revision="5678", version="3.0.0-alpha2-222-g.cafecafe"
            ),
        )
        self.patch(
            version_update_check, "get_snap_versions_info"
        ).return_value = versions_info
        service.startService()
        yield service.stopService()
        protocol.UpdateControllerState.assert_called_once_with(
            protocol,
            system_id=rpc_service.getClient().localIdent,
            scope="versions",
            state={
                "snap": dataclasses.asdict(versions_info),
            },
        )
