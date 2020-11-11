# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for maas-dhcp-support notify command."""


import os
import random
from unittest.mock import sentinel

from testtools.matchers import Equals, IsInstance, MatchesDict
from twisted.internet import defer, reactor

from maastesting import root
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.rackdservices import lease_socket_service
from provisioningserver.rackdservices.lease_socket_service import (
    LeaseSocketService,
)
from provisioningserver.utils.shell import call_and_check
from provisioningserver.utils.twisted import DeferredValue


class TestDHCPNotify(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

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
                "%s/scripts/maas-dhcp-helper" % root,
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
        yield done.get(timeout=10)

        self.assertThat(
            done.value[0],
            MatchesDict(
                {
                    "action": Equals(action),
                    "mac": Equals(mac),
                    "ip_family": Equals(ip_family),
                    "ip": Equals(ip),
                    "timestamp": IsInstance(int),
                    "lease_time": Equals(lease_time),
                    "hostname": Equals(hostname),
                }
            ),
        )
