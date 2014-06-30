# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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

import errno
import os.path
import random
from textwrap import dedent

from celery.app import app_or_default
from maastesting.factory import factory
from maastesting.fakemethod import FakeMethod
from maastesting.testcase import MAASTestCase
from mock import Mock
from netaddr import (
    IPAddress,
    IPNetwork,
    )
from provisioningserver.dns import config
from provisioningserver.dns.config import (
    compose_config_path,
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
    render_dns_template,
    report_missing_config_dir,
    set_up_options_conf,
    setup_rndc,
    uncomment_named_conf,
    )
from testtools.matchers import (
    Contains,
    ContainsAll,
    EndsWith,
    FileContains,
    FileExists,
    MatchesAll,
    MatchesStructure,
    Not,
    StartsWith,
    )
from testtools.testcase import ExpectedException
from twisted.python.filepath import FilePath


conf = app_or_default().conf


def patch_dns_config_path(testcase):
    """Set the DNS config dir to a temporary directory, and return its path."""
    config_dir = testcase.make_dir()
    testcase.patch(conf, 'DNS_CONFIG_DIR', config_dir)
    return config_dir


class TestRNDCUtilities(MAASTestCase):

    def test_generate_rndc_returns_configurations(self):
        rndc_content, named_content = generate_rndc()
        # rndc_content and named_content look right.
        self.assertIn('# Start of rndc.conf', rndc_content)
        self.assertIn('controls {', named_content)
        # named_content does not include any comment.
        self.assertNotIn('\n#', named_content)

    def test_setup_rndc_writes_configurations(self):
        dns_conf_dir = patch_dns_config_path(self)
        setup_rndc()
        expected = (
            (MAAS_RNDC_CONF_NAME, '# Start of rndc.conf'),
            (MAAS_NAMED_RNDC_CONF_NAME, 'controls {'))
        for filename, content in expected:
            with open(os.path.join(dns_conf_dir, filename), "rb") as stream:
                conf_content = stream.read()
                self.assertIn(content, conf_content)

    def test_set_up_options_conf_writes_configuration(self):
        dns_conf_dir = patch_dns_config_path(self)
        fake_dns = factory.getRandomIPAddress()
        set_up_options_conf(upstream_dns=fake_dns)
        target_file = os.path.join(
            dns_conf_dir, MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME)
        self.assertThat(
            target_file,
            FileContains(matcher=Contains(fake_dns)))

    def test_set_up_options_conf_handles_no_upstream_dns(self):
        dns_conf_dir = patch_dns_config_path(self)
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
        dns_conf_dir = patch_dns_config_path(self)
        self.patch(conf, 'DNS_DEFAULT_CONTROLS', True)
        setup_rndc()
        rndc_file = os.path.join(dns_conf_dir, MAAS_NAMED_RNDC_CONF_NAME)
        with open(rndc_file, "rb") as stream:
            conf_content = stream.read()
            self.assertIn(DEFAULT_CONTROLS, conf_content)

    def test_execute_rndc_command_executes_command(self):
        recorder = FakeMethod()
        fake_dir = patch_dns_config_path(self)
        self.patch(config, 'call_and_check', recorder)
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


class TestComposeConfigPath(MAASTestCase):
    """Tests for `compose_config_path`."""

    def test_returns_filename_in_dns_config_dir(self):
        dns_dir = patch_dns_config_path(self)
        filename = factory.make_name('config')
        self.assertEqual(
            os.path.join(dns_dir, filename),
            compose_config_path(filename))


class TestRenderDNSTemplate(MAASTestCase):
    """Tests for `render_dns_template`."""

    def test_renders_template(self):
        template_text = 'X %d Y' % random.randint(1, 10000)
        self.assertEqual(
            template_text,
            render_dns_template(self.make_file(contents=template_text)))

    def test_interpolates_parameters(self):
        param_name = factory.make_name('param', sep='_')
        param_value = factory.getRandomString()
        self.assertEqual(
            "X %s Y" % param_value,
            render_dns_template(
                self.make_file(contents="X {{%s}} Y" % param_name),
                {param_name: param_value}))

    def test_combines_parameter_dicts(self):
        self.assertEqual(
            "aaa bbb",
            render_dns_template(
                self.make_file(contents='{{one}} {{two}}'),
                {'one': 'aaa'}, {'two': 'bbb'}))

    def test_takes_latest_value_of_redefined_parameter(self):
        self.assertEqual(
            "last",
            render_dns_template(
                self.make_file(contents='{{var}}'),
                {'var': 'first'}, {'var': 'middle'}, {'var': 'last'}))

    def test_reports_missing_parameters(self):
        e = self.assertRaises(
            DNSConfigFail,
            render_dns_template,
            self.make_file(contents='{{x}}'), {'y': '?'})
        self.assertIn("'x' is not defined", unicode(e))


class TestReportMissingConfigDir(MAASTestCase):
    """Tests for the `report_missing_config_dir` context manager."""

    def test_specially_reports_missing_config_dir(self):
        with ExpectedException(DNSConfigDirectoryMissing):
            with report_missing_config_dir():
                open(os.path.join(self.make_dir(), 'nonexistent-file.txt'))

    def test_succeeds_if_no_exceptions(self):
        with report_missing_config_dir():
            pass
        # The real test is that we get here without error.
        pass

    def test_passes_on_other_similar_errors(self):
        with ExpectedException(OSError):
            with report_missing_config_dir():
                raise OSError(errno.EACCES, "Deliberate error for testing.")

    def test_passes_on_dissimilar_errors(self):
        class DeliberateError(Exception):
            """Deliberately induced error for testing."""

        with ExpectedException(DeliberateError):
            with report_missing_config_dir():
                raise DeliberateError("This exception propagates unchanged.")


class TestDNSConfig(MAASTestCase):
    """Tests for DNSConfig."""

    def test_write_config_DNSConfigDirectoryMissing_if_dir_missing(self):
        dnsconfig = DNSConfig()
        dir_name = patch_dns_config_path(self)
        os.rmdir(dir_name)
        self.assertRaises(DNSConfigDirectoryMissing, dnsconfig.write_config)

    def test_write_config_errors_if_unexpected_exception(self):
        dnsconfig = DNSConfig()
        exception = IOError(errno.EBUSY, factory.getRandomString())
        self.patch(config, 'atomic_write', Mock(side_effect=exception))
        self.assertRaises(IOError, dnsconfig.write_config)

    def test_write_config_skips_writing_if_overwrite_false(self):
        # If DNSConfig is created with overwrite=False, it won't
        # overwrite an existing config file.
        target_dir = patch_dns_config_path(self)
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
        target_dir = patch_dns_config_path(self)
        dnsconfig = DNSConfig()
        dnsconfig.write_config(overwrite=False)
        self.assertThat(
            os.path.join(target_dir, MAAS_NAMED_CONF_NAME),
            FileExists())

    def test_write_config_writes_config(self):
        target_dir = patch_dns_config_path(self)
        domain = factory.getRandomString()
        network = IPNetwork('192.168.0.3/24')
        ip = factory.getRandomIPInNetwork(network)
        forward_zone = DNSForwardZoneConfig(
            domain, mapping={factory.getRandomString(): ip})
        reverse_zone = DNSReverseZoneConfig(domain, network=network)
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
        target_dir = patch_dns_config_path(self)
        DNSConfig().write_config()
        config_file = FilePath(os.path.join(target_dir, MAAS_NAMED_CONF_NAME))
        self.assertTrue(config_file.getPermissions().other.read)

    def test_get_include_snippet_returns_snippet(self):
        target_dir = patch_dns_config_path(self)
        snippet = DNSConfig.get_include_snippet()
        self.assertThat(
            snippet,
            MatchesAll(
                Not(StartsWith('\n')),
                EndsWith('\n'),
                Contains(target_dir),
                Contains(
                    'include "%s/%s"'
                    % (conf.DNS_CONFIG_DIR, DNSConfig.target_file_name))))


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
            domain, serial=serial, mapping=mapping)
        self.assertThat(
            dns_zone_config,
            MatchesStructure.byEquality(
                domain=domain,
                serial=serial,
                _mapping=mapping,
                )
            )

    def test_computes_dns_config_file_paths(self):
        domain = factory.make_name('zone')
        dns_zone_config = DNSForwardZoneConfig(domain)
        self.assertEqual(
            os.path.join(conf.DNS_CONFIG_DIR, 'zone.%s' % domain),
            dns_zone_config.target_path)

    def test_get_a_mapping(self):
        name = factory.getRandomString()
        network = IPNetwork('192.12.0.1/30')
        dns_ip = factory.getRandomIPInNetwork(network)
        mapping = {'hostname': '192.12.0.2', 'hostname2': '192.12.0.3'}
        expected = [('%s.' % name, dns_ip)] + mapping.items()
        self.assertItemsEqual(
            expected,
            DNSForwardZoneConfig.get_A_mapping(mapping, name, dns_ip))

    def test_writes_dns_zone_config(self):
        target_dir = patch_dns_config_path(self)
        domain = factory.getRandomString()
        hostname = factory.getRandomString()
        network = factory.getRandomNetwork()
        ip = factory.getRandomIPInNetwork(network)
        dns_zone_config = DNSForwardZoneConfig(
            domain, serial=random.randint(1, 100),
            mapping={hostname: ip})
        dns_zone_config.write_config()
        self.assertThat(
            os.path.join(target_dir, 'zone.%s' % domain),
            FileContains(
                matcher=ContainsAll(
                    [
                        '%s IN A %s' % (hostname, ip),
                    ])))

    def test_writes_dns_zone_config_with_NS_record(self):
        target_dir = patch_dns_config_path(self)
        dns_ip = factory.getRandomIPAddress()
        dns_zone_config = DNSForwardZoneConfig(
            factory.getRandomString(), serial=random.randint(1, 100),
            dns_ip=dns_ip)
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
        patch_dns_config_path(self)
        dns_zone_config = DNSForwardZoneConfig(
            factory.getRandomString(), serial=random.randint(1, 100),
            dns_ip=factory.getRandomIPAddress())
        dns_zone_config.write_config()
        filepath = FilePath(dns_zone_config.target_path)
        self.assertTrue(filepath.getPermissions().other.read)


class TestDNSReverseZoneConfig(MAASTestCase):
    """Tests for DNSReverseZoneConfig."""

    def test_fields(self):
        domain = factory.getRandomString()
        serial = random.randint(1, 200)
        network = factory.getRandomNetwork()
        dns_zone_config = DNSReverseZoneConfig(
            domain, serial=serial, network=network)
        self.assertThat(
            dns_zone_config,
            MatchesStructure.byEquality(
                domain=domain,
                serial=serial,
                _network=network,
                )
            )

    def test_computes_dns_config_file_paths(self):
        domain = factory.make_name('zone')
        reverse_file_name = 'zone.168.192.in-addr.arpa'
        dns_zone_config = DNSReverseZoneConfig(
            domain, network=IPNetwork("192.168.0.0/22"))
        self.assertEqual(
            os.path.join(conf.DNS_CONFIG_DIR, reverse_file_name),
            dns_zone_config.target_path)

    def test_reverse_zone_file(self):
        # DNSReverseZoneConfig calculates the reverse zone file name
        # correctly for IPv4 and IPv6 networks.
        expected = [
            # IPv4 networks.
            (IPNetwork('192.168.0.1/22'), '168.192.in-addr.arpa'),
            (IPNetwork('192.168.0.1/24'), '0.168.192.in-addr.arpa'),
            # IPv6 networks.
            (IPNetwork('3ffe:801::/32'), '1.0.8.0.e.f.f.3.ip6.arpa'),
            (IPNetwork('2001:db8:0::/48'), '0.0.0.0.8.b.d.0.1.0.0.2.ip6.arpa'),
            (
                IPNetwork('2001:ba8:1f1:400::/56'),
                '4.0.1.f.1.0.8.a.b.0.1.0.0.2.ip6.arpa'
            ),
            (
                IPNetwork('2610:8:6800:1::/64'),
                '1.0.0.0.0.0.8.6.8.0.0.0.0.1.6.2.ip6.arpa',
            ),
            (
                IPNetwork('2001:ba8:1f1:400::/103'),
                '0.0.0.0.0.0.0.0.0.0.0.4.0.1.f.1.0.8.a.b.0.1.0.0.2.ip6.arpa',
            ),

        ]
        results = []
        for network, _ in expected:
            domain = factory.make_name('zone')
            dns_zone_config = DNSReverseZoneConfig(domain, network=network)
            results.append((network, dns_zone_config.zone_name))
        self.assertEqual(expected, results)

    def test_get_ptr_mapping(self):
        name = factory.getRandomString()
        network = IPNetwork('192.12.0.1/30')
        mapping = {
            factory.getRandomIPInNetwork(network): factory.getRandomString(),
            factory.getRandomIPInNetwork(network): factory.getRandomString(),
        }
        expected = [
            (IPAddress(ip).reverse_dns, '%s.%s.' % (hostname, name))
            for ip, hostname in mapping.items()
        ]
        self.assertItemsEqual(
            expected,
            DNSReverseZoneConfig.get_PTR_mapping(mapping, name))

    def test_writes_dns_zone_config_with_NS_record(self):
        target_dir = patch_dns_config_path(self)
        network = factory.getRandomNetwork()
        dns_zone_config = DNSReverseZoneConfig(
            factory.getRandomString(), serial=random.randint(1, 100),
            network=network)
        dns_zone_config.write_config()
        self.assertThat(
            os.path.join(
                target_dir, 'zone.%s' % dns_zone_config.zone_name),
            FileContains(
                matcher=Contains('IN  NS  %s.' % dns_zone_config.domain)))

    def test_writes_reverse_dns_zone_config(self):
        target_dir = patch_dns_config_path(self)
        domain = factory.getRandomString()
        network = IPNetwork('192.168.0.1/22')
        dns_zone_config = DNSReverseZoneConfig(
            domain, serial=random.randint(1, 100), network=network)
        dns_zone_config.write_config()
        reverse_file_name = 'zone.168.192.in-addr.arpa'
        expected = Contains(
            'IN  NS  %s' % domain)
        self.assertThat(
            os.path.join(target_dir, reverse_file_name),
            FileContains(matcher=expected))

    def test_reverse_config_file_is_world_readable(self):
        patch_dns_config_path(self)
        dns_zone_config = DNSReverseZoneConfig(
            factory.getRandomString(), serial=random.randint(1, 100),
            network=factory.getRandomNetwork())
        dns_zone_config.write_config()
        filepath = FilePath(dns_zone_config.target_path)
        self.assertTrue(filepath.getPermissions().other.read)
