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
from netaddr import IPNetwork
from provisioningserver.dns import config
from provisioningserver.dns.config import (
    compose_config_path,
    DEFAULT_CONTROLS,
    DNSConfig,
    DNSConfigDirectoryMissing,
    DNSConfigFail,
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
from provisioningserver.dns.zoneconfig import (
    DNSForwardZoneConfig,
    DNSReverseZoneConfig,
    )
from testtools.matchers import (
    Contains,
    ContainsAll,
    EndsWith,
    FileContains,
    FileExists,
    MatchesAll,
    Not,
    StartsWith,
    )
from testtools.testcase import ExpectedException
from twisted.python.filepath import FilePath


celery_conf = app_or_default().conf


def patch_dns_config_path(testcase):
    """Set the DNS config dir to a temporary directory, and return its path."""
    config_dir = testcase.make_dir()
    testcase.patch(celery_conf, 'DNS_CONFIG_DIR', config_dir)
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
        fake_dns = factory.make_ipv4_address()
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
        self.patch(celery_conf, 'DNS_DEFAULT_CONTROLS', True)
        setup_rndc()
        rndc_file = os.path.join(dns_conf_dir, MAAS_NAMED_RNDC_CONF_NAME)
        with open(rndc_file, "rb") as stream:
            conf_content = stream.read()
            self.assertIn(DEFAULT_CONTROLS, conf_content)

    def test_execute_rndc_command_executes_command(self):
        recorder = FakeMethod()
        fake_dir = patch_dns_config_path(self)
        self.patch(config, 'call_and_check', recorder)
        command = factory.make_string()
        execute_rndc_command([command])
        rndc_conf_path = os.path.join(fake_dir, MAAS_RNDC_CONF_NAME)
        expected_command = ['rndc', '-c', rndc_conf_path, command]
        self.assertEqual((expected_command,), recorder.calls[0][0])

    def test_extract_suggested_named_conf_extracts_section(self):
        named_part = factory.make_string()
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
            'rndc_part': factory.make_string(),
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
        """) % (factory.make_string(), factory.make_string())
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
        param_value = factory.make_string()
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
        exception = IOError(errno.EBUSY, factory.make_string())
        self.patch(config, 'atomic_write', Mock(side_effect=exception))
        self.assertRaises(IOError, dnsconfig.write_config)

    def test_write_config_skips_writing_if_overwrite_false(self):
        # If DNSConfig is created with overwrite=False, it won't
        # overwrite an existing config file.
        target_dir = patch_dns_config_path(self)
        random_content = factory.make_string()
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
        domain = factory.make_string()
        network = IPNetwork('192.168.0.3/24')
        ip = factory.pick_ip_in_network(network)
        forward_zone = DNSForwardZoneConfig(
            domain, mapping={factory.make_string(): ip})
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
                    % (
                        celery_conf.DNS_CONFIG_DIR,
                        DNSConfig.target_file_name,
                    ))))
