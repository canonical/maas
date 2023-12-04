# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.syslog.config`."""


import os
from pathlib import Path

from fixtures import EnvironmentVariableFixture

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.syslog import config
from provisioningserver.utils import snap


class TestGetConfigDir(MAASTestCase):
    """Tests for `get_syslog_config_path`."""

    def test_returns_default(self):
        self.assertEqual(
            "/var/lib/maas/rsyslog.conf", config.get_syslog_config_path()
        )

    def test_env_overrides_default(self):
        os.environ["MAAS_SYSLOG_CONFIG_DIR"] = factory.make_name("env")
        self.assertEqual(
            os.sep.join(
                [
                    os.environ["MAAS_SYSLOG_CONFIG_DIR"],
                    config.MAAS_SYSLOG_CONF_NAME,
                ]
            ),
            config.get_syslog_config_path(),
        )
        del os.environ["MAAS_SYSLOG_CONFIG_DIR"]


class TestWriteConfig(MAASTestCase):
    """Tests for `write_config`."""

    def setUp(self):
        super().setUp()
        self.tmpdir = self.make_dir()
        self.syslog_path = Path(self.tmpdir) / config.MAAS_SYSLOG_CONF_NAME
        self.useFixture(
            EnvironmentVariableFixture("MAAS_SYSLOG_CONFIG_DIR", self.tmpdir)
        )

    def assertLinesContain(self, match, lines):
        for line in lines:
            if match in line:
                return
        self.fail(f"{match} was not present in: {lines}")

    def test_packaging_maas_user_group_with_drop(self):
        config.write_config(False)
        needles = [
            "$FileOwner maas",
            "$FileGroup maas",
            "$PrivDropToUser maas",
            "$PrivDropToGroup maas",
        ]
        contents = self.syslog_path.read_text()
        for needle in needles:
            self.assertIn(needle, contents)

    def test_snap_root_user_group_no_drop(self):
        self.patch(snap, "running_in_snap").return_value = True
        config.write_config(False)
        needles = ["$FileOwner root", "$FileGroup root"]
        contents = self.syslog_path.read_text()
        for needle in needles:
            self.assertIn(needle, contents)

    def test_udp_and_tcp(self):
        config.write_config(False)
        needles = [
            'input(type="imtcp" port="5247")',
            'input(type="imudp" port="5247")',
        ]
        contents = self.syslog_path.read_text()
        for needle in needles:
            self.assertIn(needle, contents)

    def test_udp_and_tcp_both_use_different_port(self):
        port = factory.pick_port()
        config.write_config(False, port=port)
        needles = [
            f'input(type="imtcp" port="{port}")',
            f'input(type="imudp" port="{port}")',
        ]
        contents = self.syslog_path.read_text()
        for needle in needles:
            self.assertIn(needle, contents)

    def test_adds_tcp_stop(self):
        cidr = factory.make_ipv4_network()
        config.write_config([cidr])
        needle = ':inputname, isequal, "imtcp" stop'
        contents = self.syslog_path.read_text()
        self.assertIn(needle, contents)

    def test_write_local(self):
        config.write_config(True)
        needles = [
            'set $!remote!SYSLOG_IDENTIFIER = "maas-enlist";',
            'set $!remote!SYSLOG_IDENTIFIER = "maas-machine";',
        ]
        contents = self.syslog_path.read_text()
        for needle in needles:
            self.assertIn(needle, contents)

    def test_no_write_local(self):
        config.write_config(False)
        expected_misses = [
            'set $!remote!SYSLOG_IDENTIFIER = "maas-enlist";',
            'set $!remote!SYSLOG_IDENTIFIER = "maas-machine";',
        ]
        contents = self.syslog_path.read_text()
        for miss in expected_misses:
            self.assertNotIn(miss, contents)
        # maas.log is still local when no write local.
        self.assertIn('if $syslogtag contains "maas" then', contents)

    def test_forwarders(self):
        forwarders = [
            {
                "ip": factory.make_ip_address(),
                "name": factory.make_name("name"),
            }
            for _ in range(3)
        ]
        config.write_config(False, forwarders)
        with self.syslog_path.open() as syslog_file:
            lines = [line.strip() for line in syslog_file.readlines()]
            for host in forwarders:
                self.assertLinesContain('target="%s"' % host["ip"], lines)
                self.assertLinesContain(
                    'queue.filename="%s"' % host["name"], lines
                )

    def test_forwarders_diff_port(self):
        port = factory.pick_port()
        forwarders = [
            {
                "ip": factory.make_ip_address(),
                "name": factory.make_name("name"),
            }
            for _ in range(3)
        ]
        config.write_config(False, forwarders, port=port)
        with self.syslog_path.open() as syslog_file:
            lines = [line.strip() for line in syslog_file.readlines()]
            for host in forwarders:
                self.assertLinesContain('target="%s"' % host["ip"], lines)
                self.assertLinesContain('port="%d"' % port, lines)

    def test_write_local_and_forwarders(self):
        forwarders = [
            {
                "ip": factory.make_ip_address(),
                "name": factory.make_name("name"),
            }
            for _ in range(3)
        ]
        config.write_config(True, forwarders)
        with self.syslog_path.open() as syslog_file:
            lines = [line.strip() for line in syslog_file.readlines()]
            self.assertIn(
                'set $!remote!SYSLOG_IDENTIFIER = "maas-enlist";', lines
            )
            self.assertIn(
                'set $!remote!SYSLOG_IDENTIFIER = "maas-machine";', lines
            )
            for host in forwarders:
                self.assertLinesContain('target="%s"' % host["ip"], lines)
                self.assertLinesContain(
                    'queue.filename="%s"' % host["name"], lines
                )
