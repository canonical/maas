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
from subprocess import CalledProcessError

from maastesting.celery import CeleryFixture
from maastesting.factory import factory
from maastesting.fakemethod import FakeMethod
from maastesting.matchers import ContainsAll
from maastesting.testcase import TestCase
from netaddr import IPNetwork
from provisioningserver import tasks
from provisioningserver.auth import get_recorded_api_credentials
from provisioningserver.dhcp import leases
from provisioningserver.dns.config import (
    conf,
    DNSZoneConfig,
    MAAS_NAMED_CONF_NAME,
    MAAS_NAMED_RNDC_CONF_NAME,
    MAAS_RNDC_CONF_NAME,
    )
from provisioningserver.enum import POWER_TYPE
from provisioningserver.power.poweraction import PowerActionFail
from provisioningserver.tasks import (
    add_new_dhcp_host_map,
    Omshell,
    power_off,
    power_on,
    refresh_secrets,
    remove_dhcp_host_map,
    restart_dhcp_server,
    rndc_command,
    setup_rndc_configuration,
    write_dhcp_config,
    write_dns_config,
    write_dns_zone_config,
    write_full_dns_config,
    )
from provisioningserver.testing import network_infos
from testresources import FixtureResource
from testtools.matchers import (
    Equals,
    FileContains,
    FileExists,
    MatchesListwise,
    )

# An arbitrary MAC address.  Not using a properly random one here since
# we might accidentally affect real machines on the network.
arbitrary_mac = "AA:BB:CC:DD:EE:FF"


class TestRefreshSecrets(TestCase):
    """Tests for the `refresh_secrets` task."""

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def test_does_not_require_arguments(self):
        refresh_secrets()
        # Nothing is refreshed, but there is no error either.
        pass

    def test_calls_refresh_function(self):
        value = factory.make_name('new-value')
        refresh_function = FakeMethod()
        self.patch(tasks, 'refresh_functions', {'my_item': refresh_function})
        refresh_secrets(my_item=value)
        self.assertEqual([(value, )], refresh_function.extract_args())

    def test_refreshes_even_if_None(self):
        refresh_function = FakeMethod()
        self.patch(tasks, 'refresh_functions', {'my_item': refresh_function})
        refresh_secrets(my_item=None)
        self.assertEqual([(None, )], refresh_function.extract_args())

    def test_does_not_refresh_if_omitted(self):
        refresh_function = FakeMethod()
        self.patch(tasks, 'refresh_functions', {'my_item': refresh_function})
        refresh_secrets()
        self.assertEqual([], refresh_function.extract_args())

    def test_breaks_on_unknown_item(self):
        self.assertRaises(AssertionError, refresh_secrets, not_an_item=None)

    def test_works_as_a_task(self):
        self.assertTrue(refresh_secrets.delay().successful())

    def test_updates_api_credentials(self):
        credentials = (
            factory.make_name('key'),
            factory.make_name('token'),
            factory.make_name('secret'),
            )
        refresh_secrets(api_credentials=':'.join(credentials))
        self.assertEqual(credentials, get_recorded_api_credentials())

    def test_updates_omapi_shared_key(self):
        self.patch(leases, 'recorded_omapi_shared_key', None)
        key = factory.make_name('omapi-shared-key')
        refresh_secrets(omapi_shared_key=key)
        self.assertEqual(key, leases.recorded_omapi_shared_key)


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


class TestDHCPTasks(TestCase):

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def assertRecordedStdin(self, recorder, *args):
        # Helper to check that the function recorder "recorder" has all
        # of the items mentioned in "args" which are extracted from
        # stdin.  We can just check that all the parameters that were
        # passed are being used.
        self.assertThat(
            recorder.extract_args()[0][0],
            ContainsAll(args))

    def test_add_new_dhcp_host_map(self):
        # We don't want to actually run omshell in the task, so we stub
        # out the wrapper class's _run method and record what it would
        # do.
        mac = factory.getRandomMACAddress()
        ip = factory.getRandomIPAddress()
        server_address = factory.getRandomString()
        key = factory.getRandomString()
        recorder = FakeMethod(result=(0, "hardware-type"))
        self.patch(Omshell, '_run', recorder)
        add_new_dhcp_host_map.delay({ip: mac}, server_address, key)

        self.assertRecordedStdin(recorder, ip, mac, server_address, key)

    def test_add_new_dhcp_host_map_failure(self):
        # Check that task failures are caught.  Nothing much happens in
        # the Task code right now though.
        mac = factory.getRandomMACAddress()
        ip = factory.getRandomIPAddress()
        server_address = factory.getRandomString()
        key = factory.getRandomString()
        self.patch(Omshell, '_run', FakeMethod(result=(0, "this_will_fail")))
        self.assertRaises(
            CalledProcessError, add_new_dhcp_host_map.delay,
            {mac: ip}, server_address, key)

    def test_add_new_dhcp_host_map_records_shared_key(self):
        key = factory.getRandomString()
        self.patch(Omshell, '_run', FakeMethod())
        add_new_dhcp_host_map({}, factory.make_name('server'), key)
        self.assertEqual(key, leases.recorded_omapi_shared_key)

    def test_remove_dhcp_host_map(self):
        # We don't want to actually run omshell in the task, so we stub
        # out the wrapper class's _run method and record what it would
        # do.
        ip = factory.getRandomIPAddress()
        server_address = factory.getRandomString()
        key = factory.getRandomString()
        recorder = FakeMethod(result=(0, "obj: <null>"))
        self.patch(Omshell, '_run', recorder)
        remove_dhcp_host_map.delay(ip, server_address, key)

        self.assertRecordedStdin(recorder, ip, server_address, key)

    def test_remove_dhcp_host_map_failure(self):
        # Check that task failures are caught.  Nothing much happens in
        # the Task code right now though.
        ip = factory.getRandomIPAddress()
        server_address = factory.getRandomString()
        key = factory.getRandomString()
        self.patch(Omshell, '_run', FakeMethod(result=(0, "this_will_fail")))
        self.assertRaises(
            CalledProcessError, remove_dhcp_host_map.delay,
            ip, server_address, key)

    def test_remove_dhcp_host_map_records_shared_key(self):
        key = factory.getRandomString()
        self.patch(Omshell, '_run', FakeMethod((0, "obj: <null>")))
        remove_dhcp_host_map(
            factory.getRandomIPAddress(), factory.make_name('server'), key)
        self.assertEqual(key, leases.recorded_omapi_shared_key)

    def test_write_dhcp_config_writes_config(self):
        conf_file = self.make_file(contents=factory.getRandomString())
        self.patch(tasks, 'DHCP_CONFIG_FILE', conf_file)
        recorder = FakeMethod()
        self.patch(tasks, 'check_call', recorder)
        param_names = [
             'omapi_shared_key', 'subnet', 'subnet_mask', 'next_server',
             'broadcast_ip', 'dns_servers', 'router_ip', 'ip_range_low',
             'ip_range_high']
        params = {param: factory.getRandomString() for param in param_names}
        write_dhcp_config(**params)
        self.assertThat(
            conf_file,
            FileContains(
                matcher=ContainsAll(
                    [
                        'class "pxe"',
                        "option subnet-mask",
                    ])))
        self.assertEqual(
            (1, (['sudo', 'service', 'isc-dhcp-server', 'restart'],)),
            (recorder.call_count, recorder.extract_args()[0]))

    def test_restart_dhcp_server_sends_command(self):
        recorder = FakeMethod()
        self.patch(tasks, 'check_call', recorder)
        restart_dhcp_server()
        self.assertEqual(
            (1, (['sudo', 'service', 'isc-dhcp-server', 'restart'],)),
            (recorder.call_count, recorder.extract_args()[0]))


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
        command = factory.getRandomString()
        result = write_dns_config.delay(
            zone_names=zone_names,
            callback=rndc_command.subtask(args=[command]))

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
                    Equals([((command,), {})]),
                )),
            result)

    def test_write_dns_zone_config_writes_file(self):
        command = factory.getRandomString()
        zone_name = factory.getRandomString()
        network = IPNetwork('192.168.0.3/24')
        ip = factory.getRandomIPInNetwork(network)
        zone = DNSZoneConfig(
            zone_name, serial=random.randint(1, 100),
            mapping={factory.getRandomString(): ip}, **network_infos(network))
        result = write_dns_zone_config.delay(
            zone=zone, callback=rndc_command.subtask(args=[command]))

        reverse_file_name = 'zone.rev.0.168.192.in-addr.arpa'
        self.assertThat(
            (
                result.successful(),
                os.path.join(self.dns_conf_dir, 'zone.%s' % zone_name),
                os.path.join(self.dns_conf_dir, reverse_file_name),
                self.rndc_recorder.calls,
            ),
            MatchesListwise(
                (
                    Equals(True),
                    FileExists(),
                    FileExists(),
                    Equals([((command, ), {})]),
                )),
            result)

    def test_setup_rndc_configuration_writes_files(self):
        command = factory.getRandomString()
        result = setup_rndc_configuration.delay(
            callback=rndc_command.subtask(args=[command]))

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
                    Equals([((command,), {})]),
                )),
            result)

    def test_rndc_command_execute_command(self):
        command = factory.getRandomString()
        result = rndc_command.delay(command)

        self.assertThat(
            (result.successful(), self.rndc_recorder.calls),
            MatchesListwise(
                (
                    Equals(True),
                    Equals([((command,), {})]),
                )))

    def test_write_full_dns_config_sets_up_config(self):
        # write_full_dns_config writes the config file, writes
        # the zone files, and reloads the dns service.
        zone_name = factory.getRandomString()
        network = IPNetwork('192.168.0.3/24')
        ip = factory.getRandomIPInNetwork(network)
        zones = [DNSZoneConfig(
            zone_name, serial=random.randint(1, 100),
            mapping={factory.getRandomString(): ip}, **network_infos(network))]
        command = factory.getRandomString()
        result = write_full_dns_config.delay(
            zones=zones,
            callback=rndc_command.subtask(args=[command]))

        reverse_file_name = 'zone.rev.0.168.192.in-addr.arpa'
        self.assertThat(
            (
                result.successful(),
                self.rndc_recorder.calls,
                os.path.join(self.dns_conf_dir, 'zone.%s' % zone_name),
                os.path.join(self.dns_conf_dir, reverse_file_name),
                os.path.join(self.dns_conf_dir, MAAS_NAMED_CONF_NAME),
            ),
            MatchesListwise(
                (
                    Equals(True),
                    Equals([((command,), {})]),
                    FileExists(),
                    FileExists(),
                    FileExists(),
                )))
