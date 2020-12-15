# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.syslog.config`."""


import os
from pathlib import Path

from crochet import wait_for
from fixtures import EnvironmentVariableFixture
from testtools.matchers import Contains, FileContains, MatchesAll, Not

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.syslog import config
from provisioningserver.utils import snappy

wait_for_reactor = wait_for(30)  # 30 seconds.


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
        self.fail("%s was not present in: %s" % (match, lines))

    def test_packaging_maas_user_group_with_drop(self):
        config.write_config(False)
        matchers = [
            Contains("$FileOwner maas"),
            Contains("$FileGroup maas"),
            Contains("$PrivDropToUser maas"),
            Contains("$PrivDropToGroup maas"),
        ]
        self.assertThat(
            "%s/%s" % (self.tmpdir, config.MAAS_SYSLOG_CONF_NAME),
            FileContains(matcher=MatchesAll(*matchers)),
        )

    def test_snappy_root_user_group_no_drop(self):
        self.patch(snappy, "running_in_snap").return_value = True
        config.write_config(False)
        matchers = [Contains("$FileOwner root"), Contains("$FileGroup root")]
        self.assertThat(
            "%s/%s" % (self.tmpdir, config.MAAS_SYSLOG_CONF_NAME),
            FileContains(matcher=MatchesAll(*matchers)),
        )

    def test_udp_and_tcp(self):
        config.write_config(False)
        matcher_one = Contains('input(type="imtcp" port="5247")')
        matcher_two = Contains('input(type="imudp" port="5247")')
        self.assertThat(
            "%s/%s" % (self.tmpdir, config.MAAS_SYSLOG_CONF_NAME),
            FileContains(matcher=MatchesAll(matcher_one, matcher_two)),
        )

    def test_udp_and_tcp_both_use_different_port(self):
        port = factory.pick_port()
        config.write_config(False, port=port)
        matcher_one = Contains('input(type="imtcp" port="%d")' % port)
        matcher_two = Contains('input(type="imudp" port="%d")' % port)
        self.assertThat(
            "%s/%s" % (self.tmpdir, config.MAAS_SYSLOG_CONF_NAME),
            FileContains(matcher=MatchesAll(matcher_one, matcher_two)),
        )

    def test_adds_tcp_stop(self):
        cidr = factory.make_ipv4_network()
        config.write_config([cidr])
        matcher = Contains(':inputname, isequal, "imtcp" stop')
        self.assertThat(
            "%s/%s" % (self.tmpdir, config.MAAS_SYSLOG_CONF_NAME),
            FileContains(matcher=matcher),
        )

    def test_write_local(self):
        config.write_config(True)
        matcher_one = Contains(
            ':fromhost-ip, !isequal, "127.0.0.1" ?MAASenlist'
        )
        matcher_two = Contains(':fromhost-ip, !isequal, "127.0.0.1" ?MAASboot')
        self.assertThat(
            "%s/%s" % (self.tmpdir, config.MAAS_SYSLOG_CONF_NAME),
            FileContains(matcher=MatchesAll(matcher_one, matcher_two)),
        )

    def test_no_write_local(self):
        config.write_config(False)
        matcher_one = Not(
            Contains(':fromhost-ip, !isequal, "127.0.0.1" ?MAASenlist')
        )
        matcher_two = Not(
            Contains(':fromhost-ip, !isequal, "127.0.0.1" ?MAASboot')
        )
        # maas.log is still local when no write local.
        matcher_three = Contains(':syslogtag, contains, "maas"')
        self.assertThat(
            "%s/%s" % (self.tmpdir, config.MAAS_SYSLOG_CONF_NAME),
            FileContains(
                matcher=MatchesAll(matcher_one, matcher_two, matcher_three)
            ),
        )

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
                ':fromhost-ip, !isequal, "127.0.0.1" ?MAASenlist', lines
            )
            self.assertIn(
                ':fromhost-ip, !isequal, "127.0.0.1" ?MAASboot', lines
            )
            for host in forwarders:
                self.assertLinesContain('target="%s"' % host["ip"], lines)
                self.assertLinesContain(
                    'queue.filename="%s"' % host["name"], lines
                )
