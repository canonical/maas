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
from maastesting.matchers import ContainsAll
from maastesting.testcase import TestCase
from provisioningserver.dns import config
from provisioningserver.dns.config import (
    DNSConfig,
    DNSConfigFail,
    DNSZoneConfig,
    execute_rndc_command,
    generate_rndc,
    InactiveDNSConfig,
    setup_rndc,
    TEMPLATES_PATH,
    )
import tempita
from testtools.matchers import FileContains


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
            ('rndc.conf', '# Start of rndc.conf'),
            ('named.conf.rndc', 'controls {'))
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
        execute_rndc_command(command)
        rndc_conf_path = os.path.join(fake_dir, 'rndc.conf')
        expected_command = ['rndc', '-c', rndc_conf_path, command]
        self.assertSequenceEqual(
            [((expected_command,), {})],
            recorder.calls)


class TestDNSConfig(TestCase):
    """Tests for DNSConfig."""

    def test_DNSConfig_defaults(self):
        dnsconfig = DNSConfig()
        self.assertEqual(
            (
                os.path.join(TEMPLATES_PATH, 'named.conf.template'),
                os.path.join(conf.DNS_CONFIG_DIR, 'named.conf')
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
        zone_ids = [random.randint(0, 100)]
        reverse_zone_ids = [random.randint(0, 100)]
        dnsconfig = DNSConfig(
            zone_ids=zone_ids, reverse_zone_ids=reverse_zone_ids)
        dnsconfig.write_config()
        self.assertThat(
            os.path.join(target_dir, 'named.conf'),
            FileContains(
                matcher=ContainsAll(
                    [
                        'zone "%d"' % zone_ids[0],
                        'zone "%d.rev"' % reverse_zone_ids[0],
                        'named.conf.rndc',
                    ])))


class TestInactiveDNSConfig(TestCase):
    """Tests for InactiveDNSConfig."""

    def test_write_config_writes_empty_config(self):
        target_dir = self.make_dir()
        self.patch(InactiveDNSConfig, 'target_dir', target_dir)
        dnsconfig = InactiveDNSConfig()
        dnsconfig.write_config()
        self.assertThat(
            os.path.join(target_dir, 'named.conf'), FileContains(''))


class TestDNSZoneConfig(TestCase):
    """Tests for DNSZoneConfig."""

    def test_name_returns_zone_name(self):
        zone_id = random.randint(0, 100)
        dnszoneconfig = DNSZoneConfig(zone_id)
        self.assertEqual(dnszoneconfig.name, '%d' % zone_id)

    def test_DNSZoneConfig_fields(self):
        zone_id = random.randint(0, 100)
        dnszoneconfig = DNSZoneConfig(zone_id)
        self.assertEqual(
            (
                os.path.join(TEMPLATES_PATH, 'zone.template'),
                os.path.join(conf.DNS_CONFIG_DIR, 'zone.%d' % zone_id)
            ),
            (dnszoneconfig.template_path, dnszoneconfig.target_path))

    def test_write_config_writes_zone_config(self):
        target_dir = self.make_dir()
        self.patch(DNSConfig, 'target_dir', target_dir)
        zone_id = random.randint(0, 100)
        dnszoneconfig = DNSZoneConfig(zone_id)
        maas_server = factory.getRandomString()
        serial = random.randint(1, 100)
        hosts = [{
            'ip': factory.getRandomIPAddress(),
            'hostname': factory.getRandomString()}]
        dnszoneconfig.write_config(
            maas_server=maas_server, serial=serial, hosts=hosts)
        self.assertThat(
            os.path.join(target_dir, 'zone.%d' % zone_id),
            FileContains(
                matcher=ContainsAll(
                    [
                        'IN  NS  %s.' % maas_server,
                        '%s IN A %s' % (
                            hosts[0]['hostname'], hosts[0]['ip']),
                    ])))
