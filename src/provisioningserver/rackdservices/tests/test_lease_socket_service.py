# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for src/provisioningserver/rackdservices/lease_socket_service.py"""


from functools import partial
import json
import os
import socket
import time
from unittest.mock import MagicMock, sentinel

from twisted.application.service import Service
from twisted.internet import defer, reactor
from twisted.internet.protocol import DatagramProtocol

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.rackdservices import lease_socket_service
from provisioningserver.rackdservices.lease_socket_service import (
    LeaseSocketService,
)
from provisioningserver.rackdservices.testing import (
    configure_lease_service_for_one_shot,
)
from provisioningserver.rpc import clusterservice, getRegionClient
from provisioningserver.rpc.region import UpdateLeases
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture


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
        self.assertTrue(os.path.exists(socket_path))

    @defer.inlineCallbacks
    def test_stopService_deletes_socket(self):
        socket_path = self.patch_socket_path()
        service = LeaseSocketService(sentinel.service, reactor)
        service.startService()
        yield service.stopService()
        self.assertFalse(os.path.exists(socket_path))

    @defer.inlineCallbacks
    def test_notification_gets_added_to_notifications(self):
        socket_path = self.patch_socket_path()
        service = LeaseSocketService(sentinel.service, reactor)

        packet = self.create_lease_notification()
        helper = configure_lease_service_for_one_shot(self, service)
        next(helper)
        yield next(helper)
        helper.send(partial(self.send_notification, socket_path, packet))

        notifications = yield from helper

        # Should have one notification.
        self.assertItemsEqual([packet], notifications)

    @defer.inlineCallbacks
    def test_processNotification_gets_called_with_notification(self):
        socket_path = self.patch_socket_path()
        service = LeaseSocketService(sentinel.service, reactor)

        helper = configure_lease_service_for_one_shot(self, service)
        next(helper)
        yield next(helper)

        # Create test payload to send.
        packet1 = self.create_lease_notification()
        packet2 = self.create_lease_notification()

        # Send notification to the socket and wait for notification.
        def _send_notifications():
            self.send_notification(socket_path, packet1)
            self.send_notification(socket_path, packet2)

        helper.send(_send_notifications)

        notifications = yield from helper

        self.assertItemsEqual([packet1, packet2], notifications)

    @defer.inlineCallbacks
    def test_processNotification_dont_allow_same_address(self):
        socket_path = self.patch_socket_path()
        service = LeaseSocketService(sentinel.service, reactor)

        helper = configure_lease_service_for_one_shot(self, service)
        next(helper)
        yield next(helper)

        # Create test payload to send.
        ip = factory.make_ipv4_address()
        packet1 = self.create_lease_notification(ip=ip)
        packet2 = self.create_lease_notification(ip=ip)

        # Send notifications to the socket and wait for notifications.
        def _send_notifications():
            self.send_notification(socket_path, packet1)
            self.send_notification(socket_path, packet2)

        helper.send(_send_notifications)

        notifications = yield from helper

        # Packet should be the argument passed to processNotification in
        # order.
        self.assertEqual([packet1, packet2], list(notifications))

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
            "updates": [packet],
        }
        yield service.processNotification(payload, clock=reactor)
        protocol.UpdateLeases.assert_called_once_with(
            protocol, updates=[packet]
        )

    @defer.inlineCallbacks
    def test_processNotifications_region_not_being_called_with_no_updates(
        self,
    ):
        service = LeaseSocketService(sentinel.service, reactor)
        service.processNotification = MagicMock()

        yield service.processNotifications(clock=reactor)
        service.processNotification.assert_not_called()
