# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Celery tasks."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os
import random

from maasserver.enum import ARCHITECTURE
from maastesting.celery import CeleryFixture
from maastesting.factory import factory
from maastesting.fakemethod import FakeMethod
from maastesting.matchers import ContainsAll
from maastesting.testcase import TestCase
from provisioningserver import tasks
from provisioningserver.dns.config import (
    conf,
    MAAS_NAMED_CONF_NAME,
    MAAS_NAMED_RNDC_CONF_NAME,
    MAAS_RNDC_CONF_NAME,
    )
from provisioningserver.enum import POWER_TYPE
from provisioningserver.power.poweraction import PowerActionFail
from provisioningserver.tasks import (
    power_off,
    power_on,
    reload_dns_config,
    reload_zone_config,
    setup_rndc_configuration,
    write_dns_config,
    write_dns_zone_config,
    write_full_dns_config,
    write_tftp_config_for_node,
    )
from testresources import FixtureResource
from testtools.matchers import (
    AllMatch,
    Equals,
    FileContains,
    FileExists,
    MatchesListwise,
    )

# An arbitrary MAC address.  Not using a properly random one here since
# we might accidentally affect real machines on the network.
arbitrary_mac = "AA:BB:CC:DD:EE:FF"


class TestPowerTasks(TestCase):

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def test_ether_wake_power_on_with_not_enough_template_args(self):
        # In eager test mode the assertion is raised immediately rather
        # than being stored in the AsyncResult, so we need to test for
        # that instead of using result.get().
        self.assertRaises(
            PowerActionFail, power_on.delay, POWER_TYPE.WAKE_ON_LAN)

    def test_ether_wake_power_on(self):
        result = power_on.delay(POWER_TYPE.WAKE_ON_LAN, mac=arbitrary_mac)
        self.assertTrue(result.successful())

    def test_ether_wake_does_not_support_power_off(self):
        self.assertRaises(
            PowerActionFail, power_off.delay,
            POWER_TYPE.WAKE_ON_LAN, mac=arbitrary_mac)


class TestTFTPTasks(TestCase):

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def test_write_tftp_config_for_node_writes_files(self):
        arch = ARCHITECTURE.i386
        mac = factory.getRandomMACAddress()
        mac2 = factory.getRandomMACAddress()
        tftproot = self.make_dir()
        kernel = factory.getRandomString()
        menutitle = factory.getRandomString()
        append = factory.getRandomString()

        result = write_tftp_config_for_node.delay(
            arch, (mac, mac2), tftproot=tftproot, menutitle=menutitle,
            kernelimage=kernel, append=append)

        self.assertTrue(result.successful(), result)
        expected_file1 = os.path.join(
            tftproot, 'maas', arch, "generic", "pxelinux.cfg",
            mac.replace(":", "-"))
        expected_file2 = os.path.join(
            tftproot, 'maas', arch, "generic", "pxelinux.cfg",
            mac2.replace(":", "-"))
        self.assertThat(
            [expected_file1, expected_file2],
            AllMatch(
                FileContains(
                    matcher=ContainsAll((kernel, menutitle, append)))))


class TestDNSTasks(TestCase):

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def setUp(self):
        super(TestDNSTasks, self).setUp()
        # Patch DNS_CONFIG_DIR so that the configuration files will be
        # written in a temporary directory.
        self.dns_conf_dir = self.make_dir()
        self.patch(conf, 'DNS_CONFIG_DIR', self.dns_conf_dir)
        # Record the calls to 'execute_rndc_command' (instead of
        # executing real rndc commands).
        self.rndc_recorder = FakeMethod()
        self.patch(tasks, 'execute_rndc_command', self.rndc_recorder)

    def test_write_dns_config_writes_file(self):
        zone_names = [random.randint(1, 100), random.randint(1, 100)]
        result = write_dns_config.delay(inactive=False, zone_names=zone_names)

        self.assertThat(
            (
                result.successful(),
                os.path.join(self.dns_conf_dir, MAAS_NAMED_CONF_NAME),
                self.rndc_recorder.calls,
            ),
            MatchesListwise(
                (
                    Equals(True),
                    FileExists(),
                    Equals([(('reload',), {})]),
                )),
            result)

    def test_write_dns_config_with_inactive_True(self):
        result = write_dns_config.delay(inactive=True)

        self.assertThat(
            (
                result.successful(),
                os.path.join(self.dns_conf_dir, MAAS_NAMED_CONF_NAME),
                self.rndc_recorder.calls,
            ),
            MatchesListwise(
                (
                    Equals(True),
                    FileContains(''),
                    Equals([(('reload',), {})]),
                )),
            result)

    def test_write_dns_zone_config_writes_file(self):
        zone_name = factory.getRandomString()
        result = write_dns_zone_config.delay(
            zone_name=zone_name, domain=factory.getRandomString(),
            serial=random.randint(1, 100), hosts=[])

        self.assertThat(
            (
                result.successful(),
                os.path.join(self.dns_conf_dir, 'zone.%s' % zone_name),
                self.rndc_recorder.calls,
            ),
            MatchesListwise(
                (
                    Equals(True),
                    FileExists(),
                    Equals([(('reload', zone_name), {})]),
                )),
            result)

    def test_setup_rndc_configuration_writes_files(self):
        result = setup_rndc_configuration.delay()

        self.assertThat(
            (
                result.successful(),
                os.path.join(self.dns_conf_dir, MAAS_RNDC_CONF_NAME),
                os.path.join(
                    self.dns_conf_dir, MAAS_NAMED_RNDC_CONF_NAME),
                self.rndc_recorder.calls,
            ),
            MatchesListwise(
                (
                    Equals(True),
                    FileExists(),
                    FileExists(),
                    Equals([(('reload',), {})]),
                )),
            result)

    def test_reload_dns_config_issues_reload_command(self):
        result = reload_dns_config.delay()

        self.assertThat(
            (result.successful(), self.rndc_recorder.calls),
            MatchesListwise(
                (
                    Equals(True),
                    Equals([(('reload',), {})]),
                )))

    def test_reload_zone_config_issues_zone_reload_command(self):
        zone_name = factory.getRandomString()
        result = reload_zone_config.delay(zone_name)

        self.assertThat(
            (result.successful(), self.rndc_recorder.calls),
            MatchesListwise(
                (
                    Equals(True),
                    Equals([(('reload', zone_name), {})]),
                )))

    def test_write_full_dns_config_sets_up_config(self):
        # write_full_dns_config writes the config file, writes
        # the zone files, and reloads the dns service.
        hostname = factory.getRandomString()
        ip = factory.getRandomIPAddress()
        zone_name = factory.getRandomString()
        domain = factory.getRandomString()
        zones = {
            zone_name: {
                'serial': random.randint(1, 100),
                'hosts': [{'hostname': hostname, 'ip': ip}],
                'domain': domain,
            }
        }
        result = write_full_dns_config.delay(zones=zones)

        self.assertThat(
            (
                result.successful(),
                self.rndc_recorder.calls,
                os.path.join(
                    self.dns_conf_dir, 'zone.%s' % zone_name),
                os.path.join(
                    self.dns_conf_dir, MAAS_NAMED_CONF_NAME),
            ),
            MatchesListwise(
                (
                    Equals(True),
                    Equals([(('reload',), {})]),
                    FileExists(),
                    FileExists(),
                )))
