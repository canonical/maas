# Copyright 2021-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.boot.s390x`."""


import random

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.boot import s390x_partition as s390x_partition_module
from provisioningserver.boot.s390x import format_bootif
from provisioningserver.boot.s390x_partition import S390XPartitionBootMethod
from provisioningserver.tests.test_kernel_opts import make_kernel_parameters


class TestS390XPartitionBootMethod(MAASTestCase):
    def test_settings(self):
        s390x_partition = S390XPartitionBootMethod()

        self.assertEqual("s390x_partition", s390x_partition.name)
        self.assertEqual("s390x_partition", s390x_partition.bios_boot_method)
        self.assertEqual("s390x_partition", s390x_partition.template_subdir)
        self.assertEqual(
            "s390x_partition/maas", s390x_partition.bootloader_path
        )
        self.assertEqual("00:20", s390x_partition.arch_octet)
        self.assertIsNone(s390x_partition.user_class)

    def test_match_path_matches(self):
        s390x_partition = S390XPartitionBootMethod()
        mac = factory.make_mac_address()
        self.patch(s390x_partition_module, "get_remote_mac").return_value = mac

        self.assertEqual(
            {
                "arch": "s390x",
                "mac": mac,
            },
            s390x_partition.match_path(
                factory.make_name("backend"),
                s390x_partition.bootloader_path.encode(),
            ),
        )

    def test_match_path_doesnt_match(self):
        s390x_partition = S390XPartitionBootMethod()

        self.assertIsNone(
            s390x_partition.match_path(
                factory.make_name("backend"), factory.make_name("path")
            )
        )

    def test_get_reader_ephemeral(self):
        s390x_partition = S390XPartitionBootMethod()
        mac = factory.make_mac_address()
        params = make_kernel_parameters(
            self,
            arch="s390x",
            purpose=random.choice(
                ["commissioning", "enlist", "install", "xinstall"]
            ),
        )

        output = s390x_partition.get_reader(None, params, mac)
        output = output.read(output.size).decode()

        for regex in [
            rf"(?ms).*^\s+kernel={params.kernel}$",
            rf"(?ms).*^\s+initrd={params.initrd}$",
            rf"(?ms).*^\s+append=.*BOOTIF={format_bootif(mac)}+?$",
        ]:
            self.assertRegex(output, regex)

    def test_get_reader_ephemeral_no_mac(self):
        s390x_partition = S390XPartitionBootMethod()
        params = make_kernel_parameters(
            self,
            arch="s390x",
            purpose=random.choice(
                ["commissioning", "enlist", "install", "xinstall"]
            ),
        )

        output = s390x_partition.get_reader(None, params)
        output = output.read(output.size).decode()
        for regex in [
            rf"(?ms).*^\s+kernel={params.kernel}$",
            rf"(?ms).*^\s+initrd={params.initrd}$",
            r"(?ms).*^\s+append=.*$",
        ]:
            self.assertRegex(output, regex)

    def test_get_reader_poweroff(self):
        s390x_partition = S390XPartitionBootMethod()
        mac = factory.make_mac_address()
        params = make_kernel_parameters(
            self, arch="s390x", purpose=random.choice(["local", "poweroff"])
        )

        output = s390x_partition.get_reader(None, params, mac)
        output = [
            line
            for line in output.read(output.size).decode().splitlines()
            if line.split("#", 1)[0].strip()
        ]

        self.assertEqual([], output)

    def test_get_reader_poweroff_no_mac(self):
        s390x_partition = S390XPartitionBootMethod()
        params = make_kernel_parameters(
            self, arch="s390x", purpose=random.choice(["local", "poweroff"])
        )

        output = s390x_partition.get_reader(None, params)
        output = [
            line
            for line in output.read(output.size).decode().splitlines()
            if line.split("#", 1)[0].strip()
        ]

        self.assertEqual([], output)

    def test_get_reader_dhcp_relay_appends_bootif(self):
        s390x_partition = S390XPartitionBootMethod()
        mac = "00:16:3e:4a:03:01"
        params = make_kernel_parameters(
            self, arch="s390x", purpose="install", s390x_lease_mac_address=mac
        )

        output = s390x_partition.get_reader(None, params)
        output = output.read(output.size).decode()
        self.assertRegex(
            output,
            rf"(?ms).*^\s+append=.*BOOTIF={format_bootif(mac)}+?$",
        )
