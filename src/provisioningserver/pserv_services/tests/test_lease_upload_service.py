# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for src/provisioningserver/pserv_services/lease_upload_service.py"""

__all__ = []

from datetime import datetime

from fixtures import FakeLogger
from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.twisted import TwistedLoggerFixture
from mock import (
    ANY,
    call,
    Mock,
    sentinel,
)
from provisioningserver import services
from provisioningserver.dhcp.leases import check_lease_changes
from provisioningserver.pserv_services import lease_upload_service
from provisioningserver.pserv_services.lease_upload_service import (
    convert_leases_to_mappings,
    convert_mappings_to_leases,
    LeaseUploadService,
)
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import UpdateLeases
from provisioningserver.rpc.testing import MockClusterToRegionRPCFixture
from provisioningserver.testing.testcase import PservTestCase
from testtools.deferredruntest import extract_result
from twisted.application.internet import TimerService
from twisted.internet import defer
from twisted.internet.task import Clock


def make_random_lease():
    ip = factory.make_ipv4_address()
    mac = factory.make_mac_address()
    return (ip, mac)


def make_random_mapping():
    ip = factory.make_ipv4_address()
    mac = factory.make_mac_address()
    mapping = {"ip": ip, "mac": mac}
    return mapping


class TestHelperFunctions(PservTestCase):

    def test_convert_leases_to_mappings_maps_correctly(self):
        mappings = list()
        for _ in range(3):
            mappings.append(make_random_mapping())

        # Convert to leases.
        leases = convert_mappings_to_leases(mappings)
        # Convert back and test against our original mappings.
        observed = convert_leases_to_mappings(leases)
        self.assertItemsEqual(mappings, observed)

    def test_convert_leases_to_mappings_converts_correctly(self):
        leases = list()
        for _ in range(3):
            leases.append(make_random_lease())

        # Convert to mappings.
        mappings = convert_leases_to_mappings(leases)
        # Convert back and test against our original leases.
        observed = convert_mappings_to_leases(mappings)
        self.assertEqual(observed, leases)


class TestPeriodicImageDownloadService(PservTestCase):

    def test_init(self):
        service = LeaseUploadService(
            sentinel.service, sentinel.clock, sentinel.uuid)
        self.assertIsInstance(service, TimerService)
        self.assertIs(service.clock, sentinel.clock)
        self.assertIs(service.uuid, sentinel.uuid)
        self.assertIs(service.client_service, sentinel.service)

    def patch_upload(self, service, return_value=None):
        patched = self.patch(service, '_get_client_and_start_upload')
        patched.return_value = defer.succeed(return_value)
        return patched

    def test_is_called_every_interval(self):
        clock = Clock()
        service = LeaseUploadService(
            sentinel.service, clock, sentinel.uuid)
        # Avoid actual uploads:
        start_upload = self.patch_upload(service)

        # There are no calls before the service is started.
        self.assertThat(start_upload, MockNotCalled())

        service.startService()

        # The first call is issued at startup.
        self.assertThat(start_upload, MockCalledOnceWith())

        # Wind clock forward one second less than the desired interval.
        clock.advance(service.check_interval - 1)
        # No more periodic calls made.
        self.assertThat(start_upload, MockCalledOnceWith())

        # Wind clock forward one second, past the interval.
        clock.advance(1)

        # Now there were two calls.
        self.assertThat(start_upload, MockCallsMatch(call(), call()))

        # Forward another interval, should be three calls.
        clock.advance(service.check_interval)
        self.assertThat(
            start_upload, MockCallsMatch(call(), call(), call()))

    def test_no_upload_if_no_rpc_connections(self):
        rpc_client = Mock()
        rpc_client.getClient.side_effect = NoConnectionsAvailable()

        clock = Clock()
        service = LeaseUploadService(
            rpc_client, clock, sentinel.uuid)
        start_upload = self.patch(service, '_start_upload')
        service.startService()
        # Wind clock past all the retries.  You can't do this in one big
        # lump, it seems.  The test looks like it passes, but the
        # maybe_start_upload() method never returns properly.
        clock.pump((5, 5, 5))
        self.assertThat(start_upload, MockNotCalled())

    def test_upload_is_initiated(self):
        # We're pretending to be the reactor in this thread. To ensure correct
        # operation from things like the @asynchronous decorators we need to
        # register as the IO thread.
        self.register_as_io_thread()

        # Create a fixture for the region side of the RPC.
        rpc_fixture = self.useFixture(MockClusterToRegionRPCFixture())
        rpc_service = services.getServiceNamed('rpc')
        server, io = rpc_fixture.makeEventLoop(UpdateLeases)
        server.UpdateLeases.return_value = defer.succeed({})

        # Create a mock response to "check_lease_changes()"
        fake_lease = [make_random_lease()]
        deferToThread = self.patch(lease_upload_service, 'deferToThread')
        deferToThread.return_value = defer.succeed(
            (datetime.now(), fake_lease),)
        mappings = convert_leases_to_mappings(fake_lease)

        # Start the service.
        uuid = factory.make_UUID()
        service = LeaseUploadService(rpc_service, Clock(), uuid)
        service.startService()

        # Gavin says that I need to pump my IO.  I don't know what this
        # means but it sounds important!
        io.pump()

        # Ensure it called out to a new thread to get and parse the leases.
        self.assertThat(deferToThread, MockCalledOnceWith(check_lease_changes))

        # Ensure it sent them to the region using RPC.
        self.assertThat(
            server.UpdateLeases,
            MockCalledOnceWith(ANY, uuid=uuid, mappings=mappings))

    def test_logs_other_errors(self):
        service = LeaseUploadService(
            sentinel.rpc, Clock(), sentinel.uuid)

        _get_client_and_start_upload = self.patch_autospec(
            service, "_get_client_and_start_upload")
        _get_client_and_start_upload.return_value = defer.fail(
            ZeroDivisionError("Such a shame I can't divide by zero"))

        with FakeLogger("maas") as maaslog, TwistedLoggerFixture():
            d = service.try_upload()

        self.assertEqual(None, extract_result(d))
        self.assertDocTestMatches(
            "Failed to upload leases: "
            "Such a shame I can't divide by zero",
            maaslog.output)
