# Copyright 2012-2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test cases for dns.config"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from collections import (
    Iterable,
    Sequence,
    )
import errno
import os.path
import random
from textwrap import dedent

from celery.conf import conf
from maastesting.factory import factory
from maastesting.fakemethod import FakeMethod
from maastesting.matchers import (
    ContainsAll,
    MatchesAll,
    )
from maastesting.testcase import MAASTestCase
from mock import Mock
from netaddr import (
    IPAddress,
    IPNetwork,
    )
from provisioningserver.dns import config
from provisioningserver.dns.config import (
    DEFAULT_CONTROLS,
    DNSConfig,
    DNSConfigDirectoryMissing,
    DNSConfigFail,
    DNSForwardZoneConfig,
    DNSReverseZoneConfig,
    execute_rndc_command,
    extract_suggested_named_conf,
    generate_rndc,
    MAAS_NAMED_CONF_NAME,
    MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME,
    MAAS_NAMED_RNDC_CONF_NAME,
    MAAS_RNDC_CONF_NAME,
    set_up_options_conf,
    setup_rndc,
    shortened_reversed_ip,
    TEMPLATES_DIR,
    uncomment_named_conf,
    )
from provisioningserver.dns.utils import generated_hostname
from provisioningserver.utils import locate_config
import tempita
from testtools.matchers import (
    Contains,
    EndsWith,
    FileContains,
    FileExists,
    IsInstance,
    MatchesStructure,
    Not,
    StartsWith,
    )
from twisted.python.filepath import FilePath


class TestRNDCUtilities(MAASTestCase):

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

    def test_set_up_options_conf_writes_configuration(self):
        dns_conf_dir = self.make_dir()
        self.patch(conf, 'DNS_CONFIG_DIR', dns_conf_dir)
        fake_dns = factory.getRandomIPAddress()
        set_up_options_conf(upstream_dns=fake_dns)
        target_file = os.path.join(
            dns_conf_dir, MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME)
        self.assertThat(
            target_file,
            FileContains(matcher=Contains(fake_dns)))

    def test_set_up_options_conf_handles_no_upstream_dns(self):
        dns_conf_dir = self.make_dir()
        self.patch(conf, 'DNS_CONFIG_DIR', dns_conf_dir)
        set_up_options_conf()
        target_file = os.path.join(
            dns_conf_dir, MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME)
        self.assertThat(target_file, FileExists())

    def test_set_up_options_conf_raises_on_bad_template(self):
        template = self.make_file(
            name="named.conf.options.inside.maas.template",
            contents=b"{{nonexistent}}")
        self.patch(config, "TEMPLATES_DIR", os.path.dirname(template))
        exception = self.assertRaises(DNSConfigFail, set_up_options_conf)
        self.assertIn("name 'nonexistent' is not defined", repr(exception))

    def test_rndc_config_includes_default_controls(self):
        dns_conf_dir = self.make_dir()
        self.patch(conf, 'DNS_CONFIG_DIR', dns_conf_dir)
        self.patch(conf, 'DNS_DEFAULT_CONTROLS', True)
        setup_rndc()
        rndc_file = os.path.join(dns_conf_dir, MAAS_NAMED_RNDC_CONF_NAME)
        with open(rndc_file, "rb") as stream:
            conf_content = stream.read()
            self.assertIn(DEFAULT_CONTROLS, conf_content)

    def test_execute_rndc_command_executes_command(self):
        recorder = FakeMethod()
        fake_dir = factory.getRandomString()
        self.patch(config, 'call_and_check', recorder)
        self.patch(conf, 'DNS_CONFIG_DIR', fake_dir)
        command = factory.getRandomString()
        execute_rndc_command([command])
        rndc_conf_path = os.path.join(fake_dir, MAAS_RNDC_CONF_NAME)
        expected_command = ['rndc', '-c', rndc_conf_path, command]
        self.assertEqual((expected_command,), recorder.calls[0][0])

    def test_extract_suggested_named_conf_extracts_section(self):
        named_part = factory.getRandomString()
        # Actual rndc-confgen output, mildly mangled for testing purposes.
        # Note the awkward line break.  The code works by matching that exact
        # line, so there's no leeway with the spacing.
        rndc_config = dedent("""\
            # Start of rndc.conf
            %(rndc_part)s
            # End of rndc.conf

            # %(start_marker)s
            %(named_part)s
            # End of named.conf
        """) % {
            'start_marker': (
                'Use with the following in named.conf, '
                'adjusting the allow list as needed:'),
            'rndc_part': factory.getRandomString(),
            'named_part': named_part,
            }
        # What you get is just the suggested named.conf that's embedded in
        # the rndc-confgen output, not including its header and footer.
        self.assertEqual(
            named_part + '\n',
            extract_suggested_named_conf(rndc_config))

    def test_extract_suggested_named_conf_notices_missing_boundary(self):
        # extract_suggested_named_conf raises an exception if it does not
        # find the expected boundary between the rndc and named parts of the
        # generated configuration.
        rndc_config = dedent("""\
            # Start of rndc.conf
            %s

            %s
            # End of named.conf
        """) % (factory.getRandomString(), factory.getRandomString())
        self.assertRaises(
            ValueError,
            extract_suggested_named_conf, rndc_config)

    def test_uncomment_named_conf_uncomments(self):
        rndc_conf = 'key "rndc_key" {}'
        self.assertEqual(rndc_conf, uncomment_named_conf("# %s" % rndc_conf))

    def test_uncomment_named_conf_uncomments_multiple_lines(self):
        # named.conf section, extracted from actual rndc-confgen output.
        # Note the weird %s: the config has a line ending in a space.
        named_comment = dedent("""\
            # key "rndc-key" {
            # \talgorithm hmac-md5;
            # \tsecret "FuvtYZbYYLLJQKtn3zembg==";
            # };
            # %s
            # controls {
            # \tinet 127.0.0.1 port 953
            # \t\tallow { 127.0.0.1; } keys { "rndc-key"; };
            # };
            """) % ""

        self.assertThat(uncomment_named_conf(named_comment), Contains(
            'key "rndc-key" {\n'
            '\talgorithm hmac-md5;\n'))


class TestDNSConfig(MAASTestCase):
    """Tests for DNSConfig."""

    def test_DNSConfig_defaults(self):
        dnsconfig = DNSConfig()
        self.assertEqual(
            (
                locate_config(TEMPLATES_DIR, 'named.conf.template'),
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

    def test_render_template_raises_DNSConfigFail(self):
        dnsconfig = DNSConfig()
        template = tempita.Template("template: {{test}}")
        exception = self.assertRaises(
            DNSConfigFail, dnsconfig.render_template, template)
        self.assertIn("'test' is not defined", unicode(exception))

    def test_write_config_DNSConfigDirectoryMissing_if_dir_missing(self):
        dnsconfig = DNSConfig()
        dir_name = self.make_dir()
        os.rmdir(dir_name)
        self.patch(DNSConfig, 'target_dir', dir_name)
        self.assertRaises(DNSConfigDirectoryMissing, dnsconfig.write_config)

    def test_write_config_errors_if_unexpected_exception(self):
        dnsconfig = DNSConfig()
        exception = IOError(errno.EBUSY, factory.getRandomString())
        self.patch(
            DNSConfig, 'inner_write_config', Mock(side_effect=exception))
        self.assertRaises(IOError, dnsconfig.write_config)

    def test_write_config_skips_writing_if_overwrite_false(self):
        # If DNSConfig is created with overwrite=False, it won't
        # overwrite an existing config file.
        target_dir = self.make_dir()
        self.patch(DNSConfig, 'target_dir', target_dir)
        random_content = factory.getRandomString()
        factory.make_file(
            location=target_dir, name=MAAS_NAMED_CONF_NAME,
            contents=random_content)
        dnsconfig = DNSConfig()
        dnsconfig.write_config(overwrite=False)
        self.assertThat(
            os.path.join(target_dir, MAAS_NAMED_CONF_NAME),
            FileContains(random_content))

    def test_write_config_writes_config_if_no_existing_file(self):
        # If DNSConfig is created with overwrite=False, the config file
        # will be written if no config file exists.
        target_dir = self.make_dir()
        self.patch(DNSConfig, 'target_dir', target_dir)
        dnsconfig = DNSConfig()
        dnsconfig.write_config(overwrite=False)
        self.assertThat(
            os.path.join(target_dir, MAAS_NAMED_CONF_NAME),
            FileExists())

    def test_write_config_writes_config(self):
        target_dir = self.make_dir()
        self.patch(DNSConfig, 'target_dir', target_dir)
        domain = factory.getRandomString()
        network = IPNetwork('192.168.0.3/24')
        ip = factory.getRandomIPInNetwork(network)
        forward_zone = DNSForwardZoneConfig(
            domain, mapping={factory.getRandomString(): ip},
            networks=[network])
        reverse_zone = DNSReverseZoneConfig(
            domain, mapping={factory.getRandomString(): ip},
            network=network)
        dnsconfig = DNSConfig((forward_zone, reverse_zone))
        dnsconfig.write_config()
        self.assertThat(
            os.path.join(target_dir, MAAS_NAMED_CONF_NAME),
            FileContains(
                matcher=ContainsAll(
                    [
                        'zone.%s' % domain,
                        'zone.0.168.192.in-addr.arpa',
                        MAAS_NAMED_RNDC_CONF_NAME,
                    ])))

    def test_write_config_makes_config_world_readable(self):
        target_dir = self.make_dir()
        self.patch(DNSConfig, 'target_dir', target_dir)
        DNSConfig().write_config()
        config_file = FilePath(os.path.join(target_dir, MAAS_NAMED_CONF_NAME))
        self.assertTrue(config_file.getPermissions().other.read)

    def test_get_include_snippet_returns_snippet(self):
        target_dir = self.make_dir()
        self.patch(DNSConfig, 'target_dir', target_dir)
        dnsconfig = DNSConfig()
        snippet = dnsconfig.get_include_snippet()
        self.assertThat(
            snippet,
            MatchesAll(
                Not(StartsWith('\n')),
                EndsWith('\n'),
                Contains(target_dir),
                Contains('include "%s"' % dnsconfig.target_path)))


class TestIPUtilities(MAASTestCase):

    def test_shortened_reversed_ip_2(self):
        self.assertEqual(
            '3.0',
            shortened_reversed_ip(IPAddress('192.156.0.3'), 2))

    def test_shortened_reversed_ip_0(self):
        self.assertEqual(
            '',
            shortened_reversed_ip(IPAddress('192.156.0.3'), 0))

    def test_shortened_reversed_ip_4(self):
        self.assertEqual(
            '3.0.156.192',
            shortened_reversed_ip(IPAddress('192.156.0.3'), 4))


class TestDNSForwardZoneConfig(MAASTestCase):
    """Tests for DNSForwardZoneConfig."""

    def test_fields(self):
        domain = factory.getRandomString()
        serial = random.randint(1, 200)
        hostname = factory.getRandomString()
        network = factory.getRandomNetwork()
        ip = factory.getRandomIPInNetwork(network)
        mapping = {hostname: ip}
        dns_zone_config = DNSForwardZoneConfig(
            domain, serial, mapping, networks=[network])
        self.assertThat(
            dns_zone_config,
            MatchesStructure.byEquality(
                domain=domain,
                serial=serial,
                mapping=mapping,
                networks=[network],
                )
            )

    def test_computes_dns_config_file_paths(self):
        domain = factory.make_name('zone')
        dns_zone_config = DNSForwardZoneConfig(domain)
        self.assertEqual(
            (
                locate_config(TEMPLATES_DIR, 'zone.template'),
                os.path.join(conf.DNS_CONFIG_DIR, 'zone.%s' % domain),
            ),
            (
                dns_zone_config.template_path,
                dns_zone_config.target_path,
            ))

    def test_forward_zone_get_cname_mapping_returns_iterator(self):
        name = factory.getRandomString()
        network = IPNetwork('192.12.0.1/30')
        dns_ip = factory.getRandomIPInNetwork(network)
        dns_zone_config = DNSForwardZoneConfig(
            name, networks=[network], dns_ip=dns_ip,
            mapping={
                factory.make_name('hostname'): factory.getRandomIPAddress()})
        self.assertThat(
            dns_zone_config.get_cname_mapping(),
            MatchesAll(
                IsInstance(Iterable), Not(IsInstance(Sequence))))

    def test_forward_zone_get_cname_mapping_skips_identity(self):
        # We don't write cname records to map host names to themselves.
        # Without this, a node would get an invalid cname record upon
        # enlistment.
        zone = factory.make_name('zone')
        network = IPNetwork('10.250.99.0/24')
        ip = factory.getRandomIPInNetwork(network)
        generated_name = generated_hostname(ip)
        dns_zone_config = DNSForwardZoneConfig(
            zone, networks=[network],
            dns_ip=factory.getRandomIPInNetwork(network),
            mapping={generated_name: ip})
        self.assertNotIn(
            generated_name,
            dict(dns_zone_config.get_cname_mapping()))

    def test_get_static_mapping(self):
        name = factory.getRandomString()
        network = IPNetwork('192.12.0.1/30')
        dns_ip = factory.getRandomIPInNetwork(network)
        dns_zone_config = DNSForwardZoneConfig(
            name, networks=[network], dns_ip=dns_ip)
        self.assertItemsEqual(
            [
                ('%s.' % name, dns_ip),
                (generated_hostname('192.12.0.0'), '192.12.0.0'),
                (generated_hostname('192.12.0.1'), '192.12.0.1'),
                (generated_hostname('192.12.0.2'), '192.12.0.2'),
                (generated_hostname('192.12.0.3'), '192.12.0.3'),
            ],
            dns_zone_config.get_static_mapping(),
            )

    def test_forward_zone_get_static_mapping_returns_iterator(self):
        name = factory.getRandomString()
        network = IPNetwork('192.12.0.1/30')
        dns_ip = factory.getRandomIPInNetwork(network)
        dns_zone_config = DNSForwardZoneConfig(
            name, networks=[network], dns_ip=dns_ip)
        self.assertThat(
            dns_zone_config.get_static_mapping(),
            MatchesAll(
                IsInstance(Iterable), Not(IsInstance(Sequence))))

    def test_get_static_mapping_multiple_networks(self):
        name = factory.getRandomString()
        networks = IPNetwork('11.11.11.11/31'), IPNetwork('22.22.22.22/31')
        dns_ip = factory.getRandomIPInNetwork(networks[0])
        dns_zone_config = DNSForwardZoneConfig(
            name, networks=networks, dns_ip=dns_ip)
        self.assertItemsEqual(
            [
                ('%s.' % name, dns_ip),
                (generated_hostname('11.11.11.10'), '11.11.11.10'),
                (generated_hostname('11.11.11.11'), '11.11.11.11'),
                (generated_hostname('22.22.22.22'), '22.22.22.22'),
                (generated_hostname('22.22.22.23'), '22.22.22.23'),
            ],
            dns_zone_config.get_static_mapping(),
            )

    def test_writes_dns_zone_config(self):
        target_dir = self.make_dir()
        self.patch(DNSForwardZoneConfig, 'target_dir', target_dir)
        domain = factory.getRandomString()
        hostname = factory.getRandomString()
        network = factory.getRandomNetwork()
        ip = factory.getRandomIPInNetwork(network)
        dns_zone_config = DNSForwardZoneConfig(
            domain, serial=random.randint(1, 100),
            mapping={hostname: ip}, networks=[network])
        dns_zone_config.write_config()
        self.assertThat(
            os.path.join(target_dir, 'zone.%s' % domain),
            FileContains(
                matcher=ContainsAll(
                    [
                        '%s IN CNAME %s' % (hostname, generated_hostname(ip)),
                        '%s IN A %s' % (generated_hostname(ip), ip),
                    ])))

    def test_writes_dns_zone_config_with_NS_record(self):
        target_dir = self.make_dir()
        self.patch(DNSForwardZoneConfig, 'target_dir', target_dir)
        network = factory.getRandomNetwork()
        dns_ip = factory.getRandomIPAddress()
        dns_zone_config = DNSForwardZoneConfig(
            factory.getRandomString(), serial=random.randint(1, 100),
            dns_ip=dns_ip, networks=[network])
        dns_zone_config.write_config()
        self.assertThat(
            os.path.join(target_dir, 'zone.%s' % dns_zone_config.domain),
            FileContains(
                matcher=ContainsAll(
                    [
                        'IN  NS  %s.' % dns_zone_config.domain,
                        '%s. IN A %s' % (dns_zone_config.domain, dns_ip),
                    ])))

    def test_config_file_is_world_readable(self):
        self.patch(DNSForwardZoneConfig, 'target_dir', self.make_dir())
        network = factory.getRandomNetwork()
        dns_zone_config = DNSForwardZoneConfig(
            factory.getRandomString(), serial=random.randint(1, 100),
            dns_ip=factory.getRandomIPAddress(), networks=[network])
        dns_zone_config.write_config()
        filepath = FilePath(dns_zone_config.target_path)
        self.assertTrue(filepath.getPermissions().other.read)


class TestDNSReverseZoneConfig(MAASTestCase):
    """Tests for DNSReverseZoneConfig."""

    def test_fields(self):
        domain = factory.getRandomString()
        serial = random.randint(1, 200)
        hostname = factory.getRandomString()
        network = factory.getRandomNetwork()
        ip = factory.getRandomIPInNetwork(network)
        mapping = {hostname: ip}
        dns_zone_config = DNSReverseZoneConfig(
            domain, serial, mapping, network=network)
        self.assertThat(
            dns_zone_config,
            MatchesStructure.byEquality(
                domain=domain,
                serial=serial,
                mapping=mapping,
                network=network,
                )
            )

    def test_computes_dns_config_file_paths(self):
        domain = factory.make_name('zone')
        reverse_file_name = 'zone.168.192.in-addr.arpa'
        dns_zone_config = DNSReverseZoneConfig(
            domain, network=IPNetwork("192.168.0.0/22"))
        self.assertEqual(
            (
                locate_config(TEMPLATES_DIR, 'zone.template'),
                os.path.join(conf.DNS_CONFIG_DIR, reverse_file_name)
            ),
            (
                dns_zone_config.template_path,
                dns_zone_config.target_path,
            ))

    def test_reverse_data_slash_24(self):
        # DNSReverseZoneConfig calculates the reverse data correctly for
        # a /24 network.
        domain = factory.make_name('zone')
        hostname = factory.getRandomString()
        ip = '192.168.0.5'
        network = IPNetwork('192.168.0.1/24')
        dns_zone_config = DNSReverseZoneConfig(
            domain, mapping={hostname: ip}, network=network)
        self.assertEqual(
            '0.168.192.in-addr.arpa',
            dns_zone_config.zone_name)

    def test_reverse_data_slash_22(self):
        # DNSReverseZoneConfig calculates the reverse data correctly for
        # a /22 network.
        domain = factory.getRandomString()
        hostname = factory.getRandomString()
        ip = '192.168.0.10'
        network = IPNetwork('192.168.0.1/22')
        dns_zone_config = DNSReverseZoneConfig(
            domain, mapping={hostname: ip}, network=network)
        self.assertEqual(
            '168.192.in-addr.arpa',
            dns_zone_config.zone_name)

    def test_get_static_mapping_returns_iterator(self):
        dns_zone_config = DNSReverseZoneConfig(
            factory.getRandomString(), network=IPNetwork('192.12.0.1/30'))
        self.assertThat(
            dns_zone_config.get_static_mapping(),
            MatchesAll(
                IsInstance(Iterable), Not(IsInstance(Sequence))))

    def test_get_static_mapping(self):
        name = factory.getRandomString()
        network = IPNetwork('192.12.0.1/30')
        dns_zone_config = DNSReverseZoneConfig(name, network=network)
        self.assertItemsEqual(
            [
                ('0', '%s.' % generated_hostname('192.12.0.0', name)),
                ('1', '%s.' % generated_hostname('192.12.0.1', name)),
                ('2', '%s.' % generated_hostname('192.12.0.2', name)),
                ('3', '%s.' % generated_hostname('192.12.0.3', name)),
            ],
            dns_zone_config.get_static_mapping(),
            )

    def test_writes_dns_zone_config_with_NS_record(self):
        target_dir = self.make_dir()
        self.patch(DNSReverseZoneConfig, 'target_dir', target_dir)
        network = factory.getRandomNetwork()
        dns_ip = factory.getRandomIPAddress()
        dns_zone_config = DNSReverseZoneConfig(
            factory.getRandomString(), serial=random.randint(1, 100),
            dns_ip=dns_ip, network=network)
        dns_zone_config.write_config()
        self.assertThat(
            os.path.join(
                target_dir, 'zone.%s' % dns_zone_config.zone_name),
            FileContains(
                matcher=Contains('IN  NS  %s.' % dns_zone_config.domain)))

    def test_writes_reverse_dns_zone_config(self):
        target_dir = self.make_dir()
        self.patch(DNSReverseZoneConfig, 'target_dir', target_dir)
        domain = factory.getRandomString()
        network = IPNetwork('192.168.0.1/22')
        dns_zone_config = DNSReverseZoneConfig(
            domain, serial=random.randint(1, 100), network=network)
        dns_zone_config.write_config()
        reverse_file_name = 'zone.168.192.in-addr.arpa'
        expected = Contains(
            '10.0 IN PTR %s' % generated_hostname('192.168.0.10'))
        self.assertThat(
            os.path.join(target_dir, reverse_file_name),
            FileContains(matcher=expected))

    def test_reverse_config_file_is_world_readable(self):
        self.patch(DNSReverseZoneConfig, 'target_dir', self.make_dir())
        dns_zone_config = DNSReverseZoneConfig(
            factory.getRandomString(), serial=random.randint(1, 100),
            dns_ip=factory.getRandomIPAddress(),
            network=factory.getRandomNetwork())
        dns_zone_config.write_config()
        filepath = FilePath(dns_zone_config.target_path)
        self.assertTrue(filepath.getPermissions().other.read)
