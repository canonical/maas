# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for maas-dhcp-support notify command."""


import os
import random
from unittest.mock import sentinel

from twisted.internet import defer, reactor

from maastesting import dev_root, get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.rackdservices import lease_socket_service
from provisioningserver.rackdservices.lease_socket_service import (
    LeaseSocketService,
)
from provisioningserver.utils.shell import call_and_check
from provisioningserver.utils.twisted import DeferredValue

TIMEOUT = get_testing_timeout()


class TestDHCPNotify(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def patch_socket_path(self):
        path = self.make_dir()
        socket_path = os.path.join(path, "dhcpd.sock")
        self.patch(
            lease_socket_service, "get_socket_path"
        ).return_value = socket_path
        return socket_path

    def catch_packet_on_socket(self):
        socket_path = self.patch_socket_path()
        service = LeaseSocketService(sentinel.service, reactor)
        dv = DeferredValue()

        def mock_processNotification(*args, **kwargs):
            dv.set(args)

        self.patch(service, "processNotification", mock_processNotification)

        return socket_path, service, dv

    @defer.inlineCallbacks
    def test_sends_notification_over_socket_for_processing(self):
        action = "commit"
        mac = factory.make_mac_address()
        ip_family = "ipv4"
        ip = factory.make_ipv4_address()
        lease_time = random.randint(30, 1000)
        hostname = factory.make_name("host")

        socket_path, service, done = self.catch_packet_on_socket()
        service.startService()
        self.addCleanup(service.stopService)

        call_and_check(
            [
                f"{dev_root}/package-files/usr/sbin/maas-dhcp-helper",
                "notify",
                "--action",
                action,
                "--mac",
                mac,
                "--ip-family",
                ip_family,
                "--ip",
                ip,
                "--lease-time",
                str(lease_time),
                "--hostname",
                hostname,
                "--socket",
                socket_path,
            ]
        )
        yield done.get(timeout=TIMEOUT)

        self.assertEqual(1, len(done.value[0]["updates"]))
        update = done.value[0]["updates"][0]
        self.assertEqual(action, update["action"])
        self.assertEqual(mac, update["mac"])
        self.assertEqual(ip_family, update["ip_family"])
        self.assertEqual(ip, update["ip"])
        self.assertEqual(lease_time, update["lease_time"])
        self.assertEqual(hostname, update["hostname"])
