# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for src/provisioningserver/rackdservices/lease_socket_service.py"""


import json
import os
import socket
import time
from unittest.mock import MagicMock, sentinel

from testtools.matchers import Not, PathExists
from twisted.application.service import Service
from twisted.internet import defer, reactor
from twisted.internet.protocol import DatagramProtocol
from twisted.internet.threads import deferToThread

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.rackdservices import lease_socket_service
from provisioningserver.rackdservices.lease_socket_service import (
    LeaseSocketService,
)
from provisioningserver.rpc import clusterservice, getRegionClient
from provisioningserver.rpc.region import UpdateLeases
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from provisioningserver.utils.twisted import DeferredValue, pause, retries


class TestLeaseSocketService(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(
        timeout=get_testing_timeout()
    )

    def setUp(self):
        super().setUp()
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

    def patch_socket_path(self):
        path = self.make_dir()
        socket_path = os.path.join(path, "dhcpd.sock")
        self.patch(
            lease_socket_service, "get_socket_path"
        ).return_value = socket_path
        return socket_path

    def patch_rpc_UpdateLeases(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(UpdateLeases)
        return protocol, connecting

    def send_notification(self, socket_path, payload):
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        conn.connect(socket_path)
        conn.send(json.dumps(payload).encode("utf-8"))
        conn.close()

    def create_lease_notification(self, ip=None):
        return {
            "action": "commit",
            "mac": factory.make_mac_address(),
            "ip_family": "ipv4",
            "ip": ip or factory.make_ipv4_address(),
            "timestamp": int(time.time()),
            "lease_time": 30,
            "hostname": factory.make_name("host"),
        }

    def test_init(self):
        socket_path = self.patch_socket_path()
        service = LeaseSocketService(sentinel.service, sentinel.reactor)
        self.assertIsInstance(service, Service)
        self.assertIsInstance(service, DatagramProtocol)
        self.assertIs(service.reactor, sentinel.reactor)
        self.assertIs(service.client_service, sentinel.service)
        self.assertEqual(socket_path, service.address)

    def test_startService_creates_socket(self):
        socket_path = self.patch_socket_path()
        service = LeaseSocketService(sentinel.service, reactor)
        service.startService()
        self.addCleanup(service.stopService)
        self.assertThat(socket_path, PathExists())

    @defer.inlineCallbacks
    def test_stopService_deletes_socket(self):
        socket_path = self.patch_socket_path()
        service = LeaseSocketService(sentinel.service, reactor)
        service.startService()
        yield service.stopService()
        self.assertThat(socket_path, Not(PathExists()))

    @defer.inlineCallbacks
    def test_notification_gets_added_to_notifications(self):
        socket_path = self.patch_socket_path()
        service = LeaseSocketService(sentinel.service, reactor)
        service.startService()
        self.addCleanup(service.stopService)

        # Stop the looping call to check that the notification gets added
        # to notifications.
        process_done = service.done
        service.processor.stop()
        yield process_done
        service.processor = MagicMock()

        # Create test payload to send.
        packet = self.create_lease_notification()

        # Send notification to the socket should appear in notifications.
        yield deferToThread(self.send_notification, socket_path, packet)

        # Loop until the notifications has a notification.
        for elapsed, remaining, wait in retries(5, 0.1, reactor):
            if len(service.notifications) > 0:
                break
            else:
                yield pause(wait, reactor)

        # Should have one notitication.
        self.assertEqual([packet], list(service.notifications))

    @defer.inlineCallbacks
    def test_processNotification_gets_called_with_notification(self):
        socket_path = self.patch_socket_path()
        service = LeaseSocketService(sentinel.service, reactor)
        dv = DeferredValue()

        # Mock processNotifcation to catch the call.
        def mock_processNotification(*args, **kwargs):
            dv.set(args)

        self.patch(service, "processNotification", mock_processNotification)

        # Start the service and stop it at the end of the test.
        service.startService()
        self.addCleanup(service.stopService)

        # Create test payload to send.
        packet1 = self.create_lease_notification()
        packet2 = self.create_lease_notification()
        payload = {
            "cluster_uuid": None,
            "updates": [packet1, packet2],
        }

        # Send notification to the socket and wait for notification.
        yield deferToThread(self.send_notification, socket_path, packet1)
        yield deferToThread(self.send_notification, socket_path, packet2)
        yield dv.get(timeout=10)

        # Payload should be the argument passed to processNotifcation
        self.assertEqual((payload,), dv.value)

    @defer.inlineCallbacks
    def test_processNotification_dont_allow_same_address(self):
        socket_path = self.patch_socket_path()
        service = LeaseSocketService(sentinel.service, reactor)
        dvs = [DeferredValue(), DeferredValue()]

        # Mock processNotifcation to catch the call.
        def mock_processNotification(*args, **kwargs):
            for dv in dvs:
                if not dv.isSet:
                    dv.set(args)
                    break

        self.patch(service, "processNotification", mock_processNotification)

        # Start the service and stop it at the end of the test.
        service.startService()
        self.addCleanup(service.stopService)

        # Create test payload to send.
        ip = factory.make_ipv4_address()
        packet1 = self.create_lease_notification(ip=ip)
        packet2 = self.create_lease_notification(ip=ip)

        # Send notifications to the socket and wait for notifications.
        yield deferToThread(self.send_notification, socket_path, packet1)
        yield deferToThread(self.send_notification, socket_path, packet2)
        yield dvs[0].get(timeout=10)
        yield dvs[1].get(timeout=10)

        # Packet should be the argument passed to processNotification in
        # order.
        self.assertEqual(
            (
                {
                    "cluster_uuid": None,
                    "updates": [packet1],
                },
            ),
            dvs[0].value,
        )
        self.assertEqual(
            (
                {
                    "cluster_uuid": None,
                    "updates": [packet2],
                },
            ),
            dvs[1].value,
        )

    @defer.inlineCallbacks
    def test_processNotification_send_to_region(self):
        protocol, connecting = self.patch_rpc_UpdateLeases()
        self.addCleanup((yield connecting))

        client = getRegionClient()
        rpc_service = MagicMock()
        rpc_service.getClientNow.return_value = defer.succeed(client)
        service = LeaseSocketService(rpc_service, reactor)

        # Notification to region.
        packet = self.create_lease_notification()
        payload = {
            "cluster_uuid": None,
            "updates": [packet],
        }
        yield service.processNotification(payload, clock=reactor)
        self.assertThat(
            protocol.UpdateLeases,
            MockCalledOnceWith(
                protocol,
                cluster_uuid=client.localIdent,
                updates=[packet],
            ),
        )
