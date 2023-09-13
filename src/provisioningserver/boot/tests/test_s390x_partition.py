# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.boot.s390x`."""


import random
import re

from testtools.matchers import MatchesAll, MatchesRegex

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.boot import s390x_partition as s390x_partition_module
from provisioningserver.boot.s390x import format_bootif
from provisioningserver.boot.s390x_partition import S390XPartitionBootMethod
from provisioningserver.boot.tftppath import compose_image_path
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
        image_dir = compose_image_path(
            osystem=params.kernel_osystem,
            arch=params.arch,
            subarch=params.subarch,
            release=params.kernel_release,
            label=params.kernel_label,
        )

        self.assertThat(
            output,
            MatchesAll(
                MatchesRegex(
                    r".*^\s+kernel=%s/%s$"
                    % (re.escape(image_dir), params.kernel),
                    re.MULTILINE | re.DOTALL,
                ),
                MatchesRegex(
                    r".*^\s+initrd=%s/%s$"
                    % (re.escape(image_dir), params.initrd),
                    re.MULTILINE | re.DOTALL,
                ),
                MatchesRegex(
                    r".*^\s+append=.*BOOTIF=%s$" % format_bootif(mac),
                    re.MULTILINE | re.DOTALL,
                ),
            ),
        )

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
        image_dir = compose_image_path(
            osystem=params.kernel_osystem,
            arch=params.arch,
            subarch=params.subarch,
            release=params.kernel_release,
            label=params.kernel_label,
        )

        self.assertThat(
            output,
            MatchesAll(
                MatchesRegex(
                    r".*^\s+kernel=%s/%s$"
                    % (re.escape(image_dir), params.kernel),
                    re.MULTILINE | re.DOTALL,
                ),
                MatchesRegex(
                    r".*^\s+initrd=%s/%s$"
                    % (re.escape(image_dir), params.initrd),
                    re.MULTILINE | re.DOTALL,
                ),
                MatchesRegex(r".*^\s+append=.*$", re.MULTILINE | re.DOTALL),
            ),
        )

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
