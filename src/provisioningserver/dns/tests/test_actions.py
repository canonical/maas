# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`provisioningserver.dns.actions`."""

import os
from os.path import join
import random
from random import randint
from subprocess import CalledProcessError
from textwrap import dedent
from unittest.mock import call, sentinel

from fixtures import FakeLogger
from netaddr import IPNetwork

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.dns import actions
from provisioningserver.dns.actions import (
    get_nsupdate_key_path,
    NSUpdateCommand,
)
from provisioningserver.dns.config import (
    DynamicDNSUpdate,
    MAAS_NAMED_CONF_NAME,
    MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME,
)
from provisioningserver.dns.testing import (
    patch_dns_config_path,
    patch_zone_file_config_path,
)
from provisioningserver.dns.tests.test_zoneconfig import HostnameIPMapping
from provisioningserver.dns.zoneconfig import (
    DNSForwardZoneConfig,
    DNSReverseZoneConfig,
)
from provisioningserver.utils.shell import ExternalProcessError


class TestReconfigure(MAASTestCase):
    """Tests for :py:func:`actions.bind_reconfigure`."""

    def test_executes_rndc_command(self):
        self.patch_autospec(actions, "execute_rndc_command")
        actions.bind_reconfigure()
        actions.execute_rndc_command.assert_called_once_with(("reconfig",))

    def test_logs_subprocess_error(self):
        erc = self.patch_autospec(actions, "execute_rndc_command")
        erc.side_effect = factory.make_CalledProcessError()
        with FakeLogger("maas") as logger:
            self.assertRaises(CalledProcessError, actions.bind_reconfigure)
        self.assertRegex(
            logger.output,
            r"^Reloading BIND configuration failed: Command [^\s]+ returned non-zero exit status",
        )

    def test_upgrades_subprocess_error(self):
        erc = self.patch_autospec(actions, "execute_rndc_command")
        erc.side_effect = factory.make_CalledProcessError()
        self.assertRaises(ExternalProcessError, actions.bind_reconfigure)


class TestFreezeZone(MAASTestCase):
    """Tests for :py:func:`actions.bind_freeze_zone`."""

    def test_executes_rndc_command(self):
        self.patch_autospec(actions, "execute_rndc_command")
        zone = factory.make_name()
        actions.bind_freeze_zone(zone=zone)
        actions.execute_rndc_command.assert_called_once_with(
            ("freeze", zone), timeout=2
        )


class TestThawZone(MAASTestCase):
    """Tests for :py:func:`actions.bind_freeze_zone`."""

    def test_executes_rndc_command(self):
        self.patch_autospec(actions, "execute_rndc_command")
        zone = factory.make_name()
        actions.bind_thaw_zone(zone=zone)
        actions.execute_rndc_command.assert_called_once_with(
            ("thaw", zone), timeout=2
        )


class TestReload(MAASTestCase):
    """Tests for :py:func:`actions.bind_reload`."""

    def test_executes_rndc_command(self):
        self.patch_autospec(actions, "execute_rndc_command")
        actions.bind_reload()
        actions.execute_rndc_command.assert_called_once_with(
            ("reload",), timeout=2
        )

    def test_logs_subprocess_error(self):
        erc = self.patch_autospec(actions, "execute_rndc_command")
        erc.side_effect = factory.make_CalledProcessError()
        with FakeLogger("maas") as logger:
            self.assertFalse(actions.bind_reload())
        self.assertRegex(
            logger.output,
            r"^Reloading BIND failed \(is it running\?\): Command [^\s]+ returned non-zero exit status",
        )

    def test_false_on_subprocess_error(self):
        erc = self.patch_autospec(actions, "execute_rndc_command")
        erc.side_effect = factory.make_CalledProcessError()
        self.assertFalse(actions.bind_reload())


class TestReloadWithRetries(MAASTestCase):
    """Tests for :py:func:`actions.bind_reload_with_retries`."""

    def test_calls_bind_reload_count_times(self):
        self.patch_autospec(actions, "sleep")  # Disable.
        bind_reload = self.patch_autospec(actions, "bind_reload")
        bind_reload.return_value = False
        attempts = randint(3, 13)
        actions.bind_reload_with_retries(attempts=attempts)
        expected_calls = [call(timeout=2)] * attempts
        actions.bind_reload.assert_has_calls(expected_calls)

    def test_returns_on_success(self):
        self.patch_autospec(actions, "sleep")  # Disable.
        bind_reload = self.patch(actions, "bind_reload")
        bind_reload_return_values = [False, False, True]
        bind_reload.side_effect = lambda *args, **kwargs: (
            bind_reload_return_values.pop(0)
        )

        actions.bind_reload_with_retries(attempts=5)
        expected_calls = [call(timeout=2), call(timeout=2), call(timeout=2)]
        actions.bind_reload.assert_has_calls(expected_calls)

    def test_sleeps_interval_seconds_between_attempts(self):
        self.patch_autospec(actions, "sleep")  # Disable.
        bind_reload = self.patch_autospec(actions, "bind_reload")
        bind_reload.return_value = False
        attempts = randint(3, 13)
        actions.bind_reload_with_retries(
            attempts=attempts, interval=sentinel.interval
        )
        expected_sleep_calls = [call(sentinel.interval)] * (attempts - 1)
        actions.sleep.assert_has_calls(expected_sleep_calls)


class TestReloadZone(MAASTestCase):
    """Tests for :py:func:`actions.bind_reload_zones`."""

    def test_executes_rndc_command(self):
        self.patch_autospec(actions, "execute_rndc_command")
        self.assertTrue(actions.bind_reload_zones(sentinel.zone))
        actions.execute_rndc_command.assert_called_once_with(
            ("reload", sentinel.zone)
        )

    def test_logs_subprocess_error(self):
        erc = self.patch_autospec(actions, "execute_rndc_command")
        erc.side_effect = factory.make_CalledProcessError()
        with FakeLogger("maas") as logger:
            self.assertFalse(actions.bind_reload_zones(sentinel.zone))
        self.assertRegex(
            logger.output,
            r"^Reloading BIND zone sentinel.zone failed \(is it running\?\): Command [^\s]+ returned non-zero exit status",
        )

    def test_false_on_subprocess_error(self):
        erc = self.patch_autospec(actions, "execute_rndc_command")
        erc.side_effect = factory.make_CalledProcessError()
        self.assertFalse(actions.bind_reload_zones(sentinel.zone))


class TestConfiguration(MAASTestCase):
    """Tests for the `bind_write_*` functions."""

    def setUp(self):
        super().setUp()
        # Ensure that files are written to a temporary directory.
        self.dns_conf_dir = self.make_dir()
        patch_dns_config_path(self, self.dns_conf_dir)
        # Patch out calls to 'execute_rndc_command'.
        self.patch_autospec(actions, "execute_rndc_command")

    def test_bind_write_configuration_writes_file(self):
        domain = factory.make_string()
        zones = [
            DNSReverseZoneConfig(
                domain,
                serial=random.randint(1, 100),
                network=factory.make_ipv4_network(),
            ),
            DNSReverseZoneConfig(
                domain,
                serial=random.randint(1, 100),
                network=factory.make_ipv6_network(),
            ),
        ]
        actions.bind_write_configuration(zones=zones, trusted_networks=[])
        self.assertTrue(
            os.path.exists(
                os.path.join(self.dns_conf_dir, MAAS_NAMED_CONF_NAME)
            )
        )

    def test_bind_write_configuration_writes_file_with_acl(self):
        trusted_networks = [
            factory.make_ipv4_network(),
            factory.make_ipv6_network(),
        ]
        actions.bind_write_configuration(
            zones=[], trusted_networks=trusted_networks
        )
        expected_file = os.path.join(self.dns_conf_dir, MAAS_NAMED_CONF_NAME)
        self.assertTrue(os.path.exists(expected_file))
        expected_content = dedent(
            """\
        acl "trusted" {
            %s;
            %s;
            localnets;
            localhost;
        };
        """
        )
        expected_content %= tuple(trusted_networks)
        with open(expected_file, "r") as fh:
            contents = fh.read()
        self.assertIn(expected_content, contents)

    def test_bind_write_zones_writes_file(self):
        zone_file_dir = patch_zone_file_config_path(self)
        domain = factory.make_string()
        network = IPNetwork("192.168.0.3/24")
        dns_ip_list = [factory.pick_ip_in_network(network)]
        ip = factory.pick_ip_in_network(network)
        ttl = random.randint(10, 1000)
        forward_zone = DNSForwardZoneConfig(
            domain,
            serial=random.randint(1, 100),
            mapping={
                factory.make_string(): HostnameIPMapping(None, ttl, {ip})
            },
            dns_ip_list=dns_ip_list,
        )
        reverse_zone = DNSReverseZoneConfig(
            domain, serial=random.randint(1, 100), network=network
        )
        actions.bind_write_zones(zones=[forward_zone, reverse_zone])

        forward_file_name = "zone.%s" % domain
        reverse_file_name = "zone.0.168.192.in-addr.arpa"
        self.assertTrue(os.path.exists(join(zone_file_dir, forward_file_name)))
        self.assertTrue(os.path.exists(join(zone_file_dir, reverse_file_name)))

    def test_bind_write_options_sets_up_config(self):
        # bind_write_configuration_and_zones writes the config file, writes
        # the zone files, and reloads the dns service.
        upstream_dns = [
            factory.make_ipv4_address(),
            factory.make_ipv4_address(),
        ]
        dnssec_validation = random.choice(["auto", "yes", "no"])
        expected_dnssec_validation = dnssec_validation
        actions.bind_write_options(
            upstream_dns=upstream_dns, dnssec_validation=dnssec_validation
        )
        expected_options_file = join(
            self.dns_conf_dir, MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME
        )
        self.assertTrue(os.path.exists(expected_options_file))
        expected_options_content = dedent(
            """\
        forwarders {
            %s;
            %s;
        };

        dnssec-validation %s;
        empty-zones-enable no;
        allow-query { any; };
        allow-recursion { trusted; };
        allow-query-cache { trusted; };
        """
        )
        expected_options_content %= tuple(upstream_dns) + (
            expected_dnssec_validation,
        )
        with open(expected_options_file, "r") as fh:
            contents = fh.read()
        self.assertIn(expected_options_content, contents)


class TestNSUpdateCommand(MAASTestCase):
    def test_format_update_deletion(self):
        domain = factory.make_name()
        update = DynamicDNSUpdate(
            operation="DELETE",
            zone=domain,
            name=f"{factory.make_name()}.{domain}",
            rectype="A",
        )
        cmd = NSUpdateCommand(
            domain,
            [update],
            serial=random.randint(1, 100),
            ttl=random.randint(1, 100),
        )
        self.assertEqual(
            f"update delete {update.name} A", cmd._format_update(update)
        )

    def test_format_update_addition(self):
        domain = factory.make_name()
        update = DynamicDNSUpdate(
            operation="INSERT",
            zone=domain,
            name=f"{factory.make_name()}.{domain}",
            rectype="A",
            answer=factory.make_ip_address(),
        )
        ttl = random.randint(1, 100)
        cmd = NSUpdateCommand(
            domain, [update], serial=random.randint(1, 100), ttl=ttl
        )
        self.assertEqual(
            f"update add {update.name} {ttl} A {update.answer}",
            cmd._format_update(update),
        )

    def test_nsupdate_sends_a_single_update(self):
        domain = factory.make_name()
        update = DynamicDNSUpdate(
            operation="INSERT",
            zone=domain,
            name=f"{factory.make_name()}.{domain}",
            rectype="A",
            answer=factory.make_ip_address(),
        )
        serial = random.randint(1, 100)
        ttl = random.randint(1, 100)
        cmd = NSUpdateCommand(domain, [update], serial=serial, ttl=ttl)
        run_command = self.patch(actions, "run_command")
        cmd.update()
        run_command.assert_called_once_with(
            "nsupdate",
            "-k",
            get_nsupdate_key_path(),
            stdin="\n".join(
                [
                    "server localhost",
                    f"zone {domain}",
                    f"update add {update.name} {ttl} A {update.answer}",
                    f"update add {domain} {ttl} SOA {domain}. nobody.example.com. {serial} 600 1800 604800 {ttl}",
                    "send\n",
                ]
            ).encode("ascii"),
        )

    def test_nsupdate_sends_a_bulk_update(self):
        domain = factory.make_name()
        deletions = [
            DynamicDNSUpdate(
                operation="DELETE",
                zone=domain,
                name=f"{factory.make_name()}.{domain}",
                rectype="A",
            )
            for _ in range(2)
        ]
        additions = [
            DynamicDNSUpdate(
                operation="INSERT",
                zone=domain,
                name=f"{factory.make_name()}.{domain}",
                rectype="A",
                answer=factory.make_ip_address(),
            )
            for _ in range(2)
        ]
        ttl = random.randint(1, 100)
        cmd = NSUpdateCommand(domain, deletions + additions, ttl=ttl)
        run_command = self.patch(actions, "run_command")
        cmd.update()
        expected_stdin = [
            "server localhost",
            f"zone {domain}",
            f"update delete {deletions[0].name} {deletions[0].rectype}",
            f"update delete {deletions[1].name} {deletions[1].rectype}",
            f"update add {additions[0].name} {ttl} {additions[0].rectype} {additions[0].answer}",
            f"update add {additions[1].name} {ttl} {additions[1].rectype} {additions[1].answer}",
            "send\n",
        ]
        run_command.assert_called_once_with(
            "nsupdate",
            "-k",
            get_nsupdate_key_path(),
            "-v",
            stdin="\n".join(expected_stdin).encode("ascii"),
        )
