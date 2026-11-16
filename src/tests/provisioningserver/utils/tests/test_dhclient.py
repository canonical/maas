# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for dhclient helpers."""

import os
import random
from textwrap import dedent

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import dhclient as dhclient_module
from provisioningserver.utils.dhclient import (
    get_dhclient_info,
    get_lastest_fixed_address,
)
from provisioningserver.utils.fs import atomic_write


class TestGetLatestFixedAddress(MAASTestCase):
    IPV4_LEASE_FILE = dedent(
        """\
        lease {
          interface "eno1";
          fixed-address 192.168.1.111;
        }
        lease {
          interface "eno1";
          fixed-address 192.168.1.112;
        }
        lease {
          interface "eno1";
          fixed-address 192.168.1.113;
        }
        """
    )

    IPV6_LEASE_FILE = dedent(
        """\
        lease {
          interface "eno1";
          fixed-address6 2001:db8:a0b:12f0::1;
        }
        lease {
          interface "eno1";
          fixed-address6 2001:db8:a0b:12f0::2;
        }
        lease {
          interface "eno1";
          fixed-address6 2001:db8:a0b:12f0::3;
        }
        """
    )

    def test_missing(self):
        self.assertIsNone(
            get_lastest_fixed_address(factory.make_name("lease"))
        )

    def test_empty(self):
        path = self.make_file(contents="")
        self.assertIsNone(get_lastest_fixed_address(path))

    def test_random(self):
        path = self.make_file()
        self.assertIsNone(get_lastest_fixed_address(path))

    def test_ipv4(self):
        path = self.make_file(contents=self.IPV4_LEASE_FILE)
        self.assertEqual("192.168.1.113", get_lastest_fixed_address(path))

    def test_ipv6(self):
        path = self.make_file(contents=self.IPV6_LEASE_FILE)
        self.assertEqual(
            "2001:db8:a0b:12f0::3", get_lastest_fixed_address(path)
        )


class TestGetDhclientInfo(MAASTestCase):
    def test_returns_interface_name_with_address(self):
        proc_path = self.make_dir()
        leases_path = self.make_dir()
        running_pids = {random.randint(2, 999) for _ in range(3)}
        self.patch(
            dhclient_module, "get_running_pids_with_command"
        ).return_value = running_pids
        interfaces = {}
        for pid in running_pids:
            interface_name = factory.make_name("eth")
            address = factory.make_ipv4_address()
            interfaces[interface_name] = address
            lease_path = os.path.join(leases_path, "%s.lease" % interface_name)
            lease_data = dedent(
                """\
                lease {
                  interface "%s";
                  fixed-address %s;
                }
                """
            ) % (interface_name, address)
            atomic_write(lease_data.encode("ascii"), lease_path)
            cmdline_path = os.path.join(proc_path, str(pid), "cmdline")
            cmdline = [
                "/sbin/dhclient",
                "-d",
                "-q",
                "-pf",
                "/run/dhclient-%s.pid" % interface_name,
                "-lf",
                lease_path,
                "-cf",
                "/var/lib/dhclient/dhclient-%s.conf" % interface_name,
                interface_name,
            ]
            cmdline = "\x00".join(cmdline) + "\x00"
            os.mkdir(os.path.join(proc_path, str(pid)))
            atomic_write(cmdline.encode("ascii"), cmdline_path)
        self.assertEqual(interfaces, get_dhclient_info(proc_path=proc_path))
