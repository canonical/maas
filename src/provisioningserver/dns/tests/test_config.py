# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test cases for dns.config"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os.path
import random

from celery.conf import conf
from maastesting.factory import factory
from maastesting.fakemethod import FakeMethod
from maastesting.matchers import (
    ContainsAll,
    MatchesAll,
    )
from maastesting.testcase import TestCase
from provisioningserver.dns import config
from provisioningserver.dns.config import (
    DNSConfig,
    DNSConfigFail,
    DNSZoneConfig,
    execute_rndc_command,
    generate_rndc,
    MAAS_NAMED_CONF_NAME,
    MAAS_NAMED_RNDC_CONF_NAME,
    MAAS_RNDC_CONF_NAME,
    setup_rndc,
    TEMPLATES_PATH,
    )
import tempita
from testtools.matchers import (
    Contains,
    EndsWith,
    FileContains,
    MatchesStructure,
    StartsWith,
    )


class TestRNDCUtilities(TestCase):

    def test_generate_rndc_returns_configurations(self):
        rndc_content, named_content = generate_rndc()
        # rndc_content and named_content look right.
        self.assertIn('# Start of rndc.conf', rndc_content)
        self.assertIn('controls {', named_content)
        # named_content does not include any comment.
        self.assertNotIn('\n#', named_content)

    def test_setup_rndc_writes_configurations(self):
        dns_conf_dir = self.make_dir()
        self.patch(conf, 'DNS_CONFIG_DIR', dns_conf_dir)
        setup_rndc()
        expected = (
            (MAAS_RNDC_CONF_NAME, '# Start of rndc.conf'),
            (MAAS_NAMED_RNDC_CONF_NAME, 'controls {'))
        for filename, content in expected:
            with open(os.path.join(dns_conf_dir, filename), "rb") as stream:
                conf_content = stream.read()
                self.assertIn(content, conf_content)

    def test_execute_rndc_command_executes_command(self):
        recorder = FakeMethod()
        fake_dir = factory.getRandomString()
        self.patch(config, 'check_call', recorder)
        self.patch(conf, 'DNS_CONFIG_DIR', fake_dir)
        command = factory.getRandomString()
        execute_rndc_command([command])
        rndc_conf_path = os.path.join(fake_dir, MAAS_RNDC_CONF_NAME)
        expected_command = ['rndc', '-c', rndc_conf_path, command]
        self.assertEqual((expected_command,), recorder.calls[0][0])


class TestDNSConfig(TestCase):
    """Tests for DNSConfig."""

    def test_DNSConfig_defaults(self):
        dnsconfig = DNSConfig()
        self.assertEqual(
            (
                os.path.join(TEMPLATES_PATH, 'named.conf.template'),
                os.path.join(conf.DNS_CONFIG_DIR, MAAS_NAMED_CONF_NAME)
            ),
            (dnsconfig.template_path, dnsconfig.target_path))

    def test_get_template_retrieves_template(self):
        dnsconfig = DNSConfig()
        template = dnsconfig.get_template()
        self.assertIsInstance(template, tempita.Template)
        self.assertThat(
            dnsconfig.template_path, FileContains(template.content))

    def test_render_template(self):
        dnsconfig = DNSConfig()
        random_content = factory.getRandomString()
        template = tempita.Template("{{test}}")
        rendered = dnsconfig.render_template(template, test=random_content)
        self.assertEqual(random_content, rendered)

    def test_render_template_raises_PXEConfigFail(self):
        dnsconfig = DNSConfig()
        template = tempita.Template("template: {{test}}")
        exception = self.assertRaises(
            DNSConfigFail, dnsconfig.render_template, template)
        self.assertIn("'test' is not defined", exception.message)

    def test_write_config_writes_config(self):
        target_dir = self.make_dir()
        self.patch(DNSConfig, 'target_dir', target_dir)
        zone_name = factory.getRandomString()
        zone = DNSZoneConfig(
            zone_name, bcast='192.168.0.255',
            mask='255.255.255.0',
            mapping={factory.getRandomString(): '192.168.0.5'})
        dnsconfig = DNSConfig(zones=[zone])
        dnsconfig.write_config()
        self.assertThat(
            os.path.join(target_dir, MAAS_NAMED_CONF_NAME),
            FileContains(
                matcher=ContainsAll(
                    [
                        'zone.%s' % zone_name,
                        'zone.rev.%s' % zone_name,
                        MAAS_NAMED_RNDC_CONF_NAME,
                    ])))

    def test_get_include_snippet_returns_snippet(self):
        target_dir = self.make_dir()
        self.patch(DNSConfig, 'target_dir', target_dir)
        dnsconfig = DNSConfig()
        snippet = dnsconfig.get_include_snippet()
        self.assertThat(
            snippet,
            MatchesAll(
                StartsWith('\n'),
                EndsWith('\n'),
                Contains(target_dir),
                Contains('include "%s"' % dnsconfig.target_path)))


class TestDNSZoneConfig(TestCase):
    """Tests for DNSZoneConfig."""

    def test_DNSZoneConfig_fields(self):
        zone_name = factory.getRandomString()
        serial = random.randint(1, 200)
        bcast = factory.getRandomIPAddress()
        mask = factory.getRandomIPAddress()
        hostname = factory.getRandomString()
        ip = factory.getRandomString()
        mapping = {hostname: ip}
        dns_zone_config = DNSZoneConfig(
            zone_name, serial, mapping, bcast, mask)
        self.assertThat(
            dns_zone_config,
            MatchesStructure.byEquality(
                zone_name=zone_name,
                serial=serial,
                mapping=mapping,
                bcast=bcast,
                mask=mask,
                )
            )

    def test_DNSZoneConfig_computes_dns_config_file_paths(self):
        zone_name = factory.getRandomString()
        dns_zone_config = DNSZoneConfig(zone_name)
        self.assertEqual(
            (
                os.path.join(TEMPLATES_PATH, 'zone.template'),
                os.path.join(conf.DNS_CONFIG_DIR, 'zone.%s' % zone_name),
                os.path.join(conf.DNS_CONFIG_DIR, 'zone.rev.%s' % zone_name)
            ),
            (
                dns_zone_config.template_path,
                dns_zone_config.target_path,
                dns_zone_config.target_reverse_path,
            ))

    def test_DNSZoneConfig_reverse_data_slash_24(self):
        # DNSZoneConfig calculates the reverse data correctly for
        # a /24 network.
        zone_name = factory.getRandomString()
        hostname = factory.getRandomString()
        dns_zone_config = DNSZoneConfig(
            zone_name, bcast='192.168.0.255',
            mask='255.255.255.0',
            mapping={hostname: '192.168.0.5'})
        self.assertEqual(
            (
                3,
                {'5': '%s.%s.' % (hostname, zone_name)},
                '0.168.192.in-addr.arpa',
            ),
            (
                dns_zone_config.byte_num,
                dns_zone_config.reverse_mapping,
                dns_zone_config.reverse_zone_name,
            ))

    def test_DNSZoneConfig_reverse_data_slash_22(self):
        # DNSZoneConfig calculates the reverse data correctly for
        # a /22 network.
        zone_name = factory.getRandomString()
        hostname = factory.getRandomString()
        dns_zone_config = DNSZoneConfig(
            zone_name, bcast='192.12.3.255',
            mask='255.255.252.0',
            mapping={hostname: '192.12.2.10'})
        self.assertEqual(
            (
                2,
                {'10.2': '%s.%s.' % (hostname, zone_name)},
                '12.192.in-addr.arpa',
            ),
            (
                dns_zone_config.byte_num,
                dns_zone_config.reverse_mapping,
                dns_zone_config.reverse_zone_name,
            ))

    def test_DNSZoneConfig_writes_dns_zone_config(self):
        target_dir = self.make_dir()
        self.patch(DNSConfig, 'target_dir', target_dir)
        zone_name = factory.getRandomString()
        hostname = factory.getRandomString()
        ip = factory.getRandomIPAddress()
        dns_zone_config = DNSZoneConfig(
            zone_name, serial=random.randint(1, 100),
            mapping={hostname: ip})
        dns_zone_config.write_config()
        self.assertThat(
            os.path.join(target_dir, 'zone.%s' % zone_name),
            FileContains(
                matcher=ContainsAll(
                    [
                        'IN  NS  %s.' % zone_name,
                        '%s IN A %s' % (hostname, ip),
                    ])))

    def test_DNSZoneConfig_writes_reverse_dns_zone_config(self):
        target_dir = self.make_dir()
        self.patch(DNSConfig, 'target_dir', target_dir)
        zone_name = factory.getRandomString()
        hostname = factory.getRandomString()
        ip = '192.12.2.10'
        dns_zone_config = DNSZoneConfig(
            zone_name, serial=random.randint(1, 100),
            bcast='192.12.3.255', mask='255.255.252.0',
            mapping={hostname: ip})
        dns_zone_config.write_reverse_config()
        self.assertThat(
            os.path.join(target_dir, 'zone.rev.%s' % zone_name),
            FileContains(
                matcher=ContainsAll(
                    ['%s IN PTR %s' % (
                        '10.2',
                        '%s.%s.' % (hostname, zone_name))])))
