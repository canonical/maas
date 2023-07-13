# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for maas-dhcp-support notify command."""


from functools import partial
import os
import random
from unittest.mock import sentinel

from twisted.internet import defer, reactor

from maastesting import dev_root, get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.rackdservices import lease_socket_service
from provisioningserver.rackdservices.testing import (
    configure_lease_service_for_one_shot,
)
from provisioningserver.utils.shell import call_and_check

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
        service = lease_socket_service.LeaseSocketService(
            sentinel.service, reactor
        )
        helper = configure_lease_service_for_one_shot(self, service)
        # Get to the point of the done callback
        next(helper)
        return socket_path, service, helper

    @defer.inlineCallbacks
    def test_sends_notification_over_socket_for_processing(self):
        action = "commit"
        mac = factory.make_mac_address()
        ip_family = "ipv4"
        ip = factory.make_ipv4_address()
        lease_time = random.randint(30, 1000)
        hostname = factory.make_name("host")

        socket_path, service, helper = self.catch_packet_on_socket()

        send_notification = partial(
            call_and_check,
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
            ],
        )

        # Wait for the service to be done
        yield next(helper)

        helper.send(send_notification)
        notifications = yield from helper
        self.assertEqual(len(notifications), 1)
        update = notifications[0]
        self.assertEqual(action, update["action"])
        self.assertEqual(mac, update["mac"])
        self.assertEqual(ip_family, update["ip_family"])
        self.assertEqual(ip, update["ip"])
        self.assertEqual(lease_time, update["lease_time"])
        self.assertEqual(hostname, update["hostname"])
