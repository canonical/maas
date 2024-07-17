# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE)

import dataclasses
from unittest.mock import sentinel

from twisted.internet.defer import inlineCallbacks, returnValue

from maastesting import get_testing_timeout
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver import services
from provisioningserver.rackdservices import version_update_check
from provisioningserver.rackdservices.version_update_check import (
    RackVersionUpdateCheckService,
    VersionUpdateCheckService,
)
from provisioningserver.rpc import clusterservice
from provisioningserver.rpc.region import UpdateControllerState
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from provisioningserver.utils.deb import DebVersion, DebVersionsInfo
from provisioningserver.utils.snap import (
    SnapChannel,
    SnapVersion,
    SnapVersionsInfo,
)


class SampleVersionUpdateCheckService(VersionUpdateCheckService):
    def __init__(self, clock=None):
        super().__init__(clock=clock)
        self.calls = []

    @inlineCallbacks
    def process_versions_info(self, versions_info):
        self.calls.append(versions_info)
        yield


class TestVersionUpdateCheckService(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(
        debug=True, timeout=get_testing_timeout()
    )

    @inlineCallbacks
    def test_process_version_info_not_called_without_versions(self):
        service = SampleVersionUpdateCheckService()
        self.patch(version_update_check, "get_versions_info").return_value = (
            None
        )
        yield service.do_action()
        self.assertEqual(service.calls, [])

    @inlineCallbacks
    def test_process_version_called_with_versions(self):
        service = SampleVersionUpdateCheckService()
        self.patch(version_update_check, "get_versions_info").return_value = (
            sentinel.versions_info
        )
        yield service.do_action()
        self.assertEqual(service.calls, [sentinel.versions_info])


class TestRackVersionUpdateCheckService(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(
        debug=True, timeout=get_testing_timeout()
    )

    @inlineCallbacks
    def create_fake_rpc_service(self):
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(UpdateControllerState)
        self.addCleanup((yield connecting))
        returnValue(protocol)

    def test_get_state_in_deb(self):
        service = RackVersionUpdateCheckService(None)
        versions_info = DebVersionsInfo(
            current=DebVersion(
                version="3.0.0~alpha1-111-g.deadbeef",
                origin="http://archive.ubuntu.com/ubuntu focal/main",
            ),
            update=DebVersion(
                version="3.0.0~alpha2-222-g.cafecafe",
                origin="http://archive.ubuntu.com/ubuntu focal/main",
            ),
        )
        self.assertEqual(
            service._get_state(versions_info),
            {
                "deb": dataclasses.asdict(versions_info),
            },
        )

    def test_get_versions_state_in_snap(self):
        service = RackVersionUpdateCheckService(None)
        versions_info = SnapVersionsInfo(
            current=SnapVersion(
                revision="1234", version="3.0.0~alpha1-111-g.deadbeef"
            ),
            channel=SnapChannel(track="3.0"),
            update=SnapVersion(
                revision="5678", version="3.0.0~alpha2-222-g.cafecafe"
            ),
        )
        self.assertEqual(
            service._get_state(versions_info),
            {
                "snap": dataclasses.asdict(versions_info),
            },
        )

    @inlineCallbacks
    def test_sends_version_state_update(self):
        protocol = yield self.create_fake_rpc_service()
        rpc_service = services.getServiceNamed("rpc")
        service = RackVersionUpdateCheckService(rpc_service)
        versions_info = SnapVersionsInfo(
            current=SnapVersion(
                revision="1234", version="3.0.0~alpha1-111-g.deadbeef"
            ),
            channel=SnapChannel(track="3.0"),
            update=SnapVersion(
                revision="5678", version="3.0.0~alpha2-222-g.cafecafe"
            ),
        )
        self.patch(version_update_check, "get_versions_info").return_value = (
            versions_info
        )
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

    @inlineCallbacks
    def test_process_version_info_not_called_without_client(self):
        protocol = yield self.create_fake_rpc_service()
        rpc_service = services.getServiceNamed("rpc")
        service = RackVersionUpdateCheckService(rpc_service)
        self.patch(version_update_check, "get_versions_info").return_value = (
            sentinel.version_info
        )

        self.patch(service._getRPCClient).return_value = None
        service.startService()
        yield service.stopService()
        protocol.UpdateControllerState.assert_not_called()
