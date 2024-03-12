# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test cases for dns.config"""


import errno
import os.path
import random
from textwrap import dedent
from unittest.mock import Mock, sentinel

from fixtures import EnvironmentVariable
from netaddr import IPAddress, IPNetwork
from testtools.matchers import (
    AllMatch,
    Contains,
    ContainsAll,
    EndsWith,
    Equals,
    FileContains,
    FileExists,
    Is,
    IsInstance,
    MatchesAll,
    Not,
    SamePath,
    StartsWith,
)
from testtools.testcase import ExpectedException
from twisted.python.filepath import FilePath

from maastesting.factory import factory
from maastesting.fakemethod import FakeMethod
from maastesting.testcase import MAASTestCase
from provisioningserver.dns import config
from provisioningserver.dns.config import (
    clean_old_zone_files,
    compose_config_path,
    DEFAULT_CONTROLS,
    DNSConfig,
    DNSConfigDirectoryMissing,
    DNSConfigFail,
    DynamicDNSUpdate,
    execute_rndc_command,
    extract_suggested_named_conf,
    generate_rndc,
    MAAS_NAMED_CONF_NAME,
    MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME,
    MAAS_NAMED_RNDC_CONF_NAME,
    MAAS_RNDC_CONF_NAME,
    NAMED_CONF_OPTIONS,
    render_dns_template,
    report_missing_config_dir,
    set_up_options_conf,
    set_up_rndc,
    uncomment_named_conf,
)
from provisioningserver.dns.testing import (
    patch_dns_config_path,
    patch_dns_default_controls,
    patch_zone_file_config_path,
)
from provisioningserver.dns.zoneconfig import (
    DNSForwardZoneConfig,
    DNSReverseZoneConfig,
)
from provisioningserver.utils import locate_config
from provisioningserver.utils.isc import parse_isc_string, read_isc_file

NAMED_CONF_OPTIONS_CONTENTS = dedent(
    """\
    options {
        forwarders {
            8.8.8.8;
            8.8.4.4;
        };
        dnssec-validation auto;
        allow-query { any; };
        allow-recursion { trusted; };
        allow-query-cache { trusted; };
        auth-nxdomain no;
        listen-on-v6 { any; };
    };
    """
)

NAMED_CONF_OPTIONS_WITH_ALLOW_QUERY_CONTENTS = dedent(
    """\
    options {
        forwarders {
            8.8.8.8;
            8.8.4.4;
        };
        dnssec-validation auto;
        allow-query { any; };
        auth-nxdomain no;
        listen-on-v6 { any; };
    };
    """
)

NAMED_CONF_OPTIONS_NO_ALLOW_CONTENTS = dedent(
    """\
    options {
        forwarders {
            8.8.8.8;
            8.8.4.4;
        };
        dnssec-validation auto;
        auth-nxdomain no;
        listen-on-v6 { any; };
    };
    """
)


class TestHelpers(MAASTestCase):
    def test_get_dns_config_dir_defaults_to_etc_bind_maas(self):
        self.useFixture(EnvironmentVariable("MAAS_DNS_CONFIG_DIR"))
        self.assertThat(
            config.get_dns_config_dir(),
            MatchesAll(
                SamePath(locate_config("../bind/maas")), IsInstance(str)
            ),
        )

    def test_get_dns_config_dir_checks_environ_first(self):
        directory = self.make_dir()
        self.useFixture(EnvironmentVariable("MAAS_DNS_CONFIG_DIR", directory))
        self.assertThat(
            config.get_dns_config_dir(),
            MatchesAll(SamePath(directory), IsInstance(str)),
        )

    def test_get_bind_config_dir_defaults_to_etc_bind_maas(self):
        self.useFixture(EnvironmentVariable("MAAS_BIND_CONFIG_DIR"))
        self.assertThat(
            config.get_bind_config_dir(),
            MatchesAll(SamePath(locate_config("../bind")), IsInstance(str)),
        )

    def test_get_bind_config_dir_checks_environ_first(self):
        directory = self.make_dir()
        self.useFixture(EnvironmentVariable("MAAS_BIND_CONFIG_DIR", directory))
        self.assertThat(
            config.get_bind_config_dir(),
            MatchesAll(SamePath(directory), IsInstance(str)),
        )

    def test_get_dns_root_port_defaults_to_954(self):
        self.useFixture(EnvironmentVariable("MAAS_DNS_RNDC_PORT"))
        self.assertEqual(954, config.get_dns_rndc_port())

    def test_get_dns_root_port_checks_environ_first(self):
        port = factory.pick_port()
        self.useFixture(EnvironmentVariable("MAAS_DNS_RNDC_PORT", "%d" % port))
        self.assertEqual(port, config.get_dns_rndc_port())

    def test_get_dns_default_controls_defaults_to_affirmative(self):
        self.useFixture(EnvironmentVariable("MAAS_DNS_DEFAULT_CONTROLS"))
        self.assertTrue(config.get_dns_default_controls())

    def test_get_dns_default_controls_defaults_always_false_in_snap(self):
        self.useFixture(EnvironmentVariable("MAAS_DNS_DEFAULT_CONTROLS", "1"))
        self.patch(config, "running_in_snap").return_value = True
        self.assertFalse(config.get_dns_default_controls())

    def test_get_dns_default_controls_checks_environ_first(self):
        self.useFixture(EnvironmentVariable("MAAS_DNS_DEFAULT_CONTROLS", "0"))
        self.assertFalse(config.get_dns_default_controls())

    def test_get_zone_file_config_dir_defaults_to_var_lib_bind_maas(self):
        self.useFixture(EnvironmentVariable("MAAS_ZONE_FILE_CONFIG_DIR"))
        self.assertEqual(
            str(config.get_zone_file_config_dir()), "/var/lib/bind/maas"
        )

    def test_get_zone_file_config_dir_check_environ_first(self):
        directory = self.make_dir()
        self.useFixture(
            EnvironmentVariable("MAAS_ZONE_FILE_CONFIG_DIR", directory)
        )
        self.assertEqual(str(config.get_zone_file_config_dir()), directory)


class TestRNDCUtilities(MAASTestCase):
    def test_generate_rndc_returns_configurations(self):
        rndc_content, named_content = generate_rndc(
            include_default_controls=False
        )
        # rndc_content and named_content look right.
        self.assertIn("# Start of rndc.conf", rndc_content)
        self.assertIn("controls {", named_content)
        # named_content does not include any comment.
        self.assertNotIn("\n#", named_content)

    def test_set_up_rndc_writes_configurations(self):
        dns_conf_dir = patch_dns_config_path(self)
        set_up_rndc()
        expected = (
            (MAAS_RNDC_CONF_NAME, "# Start of rndc.conf"),
            (MAAS_NAMED_RNDC_CONF_NAME, "controls {"),
        )
        for filename, content in expected:
            filepath = os.path.join(dns_conf_dir, filename)
            with open(filepath, encoding="ascii") as stream:
                conf_content = stream.read()
                self.assertIn(content, conf_content)

    def test_set_up_options_conf_writes_configuration(self):
        dns_conf_dir = patch_dns_config_path(self)
        fake_dns = [factory.make_ipv4_address(), factory.make_ipv4_address()]
        set_up_options_conf(upstream_dns=fake_dns)
        target_file = os.path.join(
            dns_conf_dir, MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME
        )
        self.assertThat(
            target_file,
            MatchesAll(
                *(
                    FileContains(matcher=Contains(address))
                    for address in fake_dns
                )
            ),
        )

    def test_set_up_options_conf_write_config_assumes_no_overrides(self):
        dns_conf_dir = patch_dns_config_path(self)
        set_up_options_conf()
        target_file = os.path.join(
            dns_conf_dir, MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME
        )
        target = read_isc_file(target_file)
        self.assertThat(
            [
                target["allow-query"]["any"],
                target["allow-recursion"]["trusted"],
                target["allow-query-cache"]["trusted"],
            ],
            AllMatch(Equals(True)),
        )

    def test_set_up_options_conf_write_config_allows_overrides(self):
        dns_conf_dir = patch_dns_config_path(self)
        factory.make_file(
            location=dns_conf_dir,
            name=NAMED_CONF_OPTIONS,
            contents=NAMED_CONF_OPTIONS_CONTENTS,
        )
        set_up_options_conf()
        target_file = os.path.join(
            dns_conf_dir, MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME
        )
        target = read_isc_file(target_file)
        self.assertThat(
            [
                target.get("allow-query"),
                target.get("allow-recursion"),
                target.get("allow-query-cache"),
            ],
            AllMatch(Is(None)),
        )

    def test_set_up_options_conf_write_config_allows_zero_overrides(self):
        dns_conf_dir = patch_dns_config_path(self)
        factory.make_file(
            location=dns_conf_dir,
            name=NAMED_CONF_OPTIONS,
            contents=NAMED_CONF_OPTIONS_NO_ALLOW_CONTENTS,
        )
        set_up_options_conf()
        target_file = os.path.join(
            dns_conf_dir, MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME
        )
        target = read_isc_file(target_file)
        self.assertThat(
            [
                target["allow-query"]["any"],
                target["allow-recursion"]["trusted"],
                target["allow-query-cache"]["trusted"],
            ],
            AllMatch(Equals(True)),
        )

    def test_set_up_options_conf_write_config_allows_single_override(self):
        dns_conf_dir = patch_dns_config_path(self)
        factory.make_file(
            location=dns_conf_dir,
            name=NAMED_CONF_OPTIONS,
            contents=NAMED_CONF_OPTIONS_WITH_ALLOW_QUERY_CONTENTS,
        )
        set_up_options_conf()
        target_file = os.path.join(
            dns_conf_dir, MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME
        )
        target = read_isc_file(target_file)
        self.assertIsNone(target.get("allow-query"))

    def test_set_up_options_conf_handles_no_upstream_dns(self):
        dns_conf_dir = patch_dns_config_path(self)
        set_up_options_conf()
        target_file = os.path.join(
            dns_conf_dir, MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME
        )
        self.assertThat(target_file, FileExists())

    def test_clean_old_zone_files(self):
        zone_file_dir = patch_zone_file_config_path(self)

        zonefiles = [
            os.path.join(zone_file_dir, f"zone.{i}")
            for i, _ in enumerate(range(2))
        ]
        for zonefile in zonefiles:
            with open(zonefile, "w+"):
                pass

        clean_old_zone_files()
        for zonefile in zonefiles:
            self.assertRaises(FileNotFoundError, os.stat, zonefile)

    def test_clean_old_zone_files_only_deletes_files(self):
        zone_file_dir = patch_zone_file_config_path(self)

        zonefiles = [
            os.path.join(zone_file_dir, f"zone.{i}")
            for i, _ in enumerate(range(2))
        ]
        for zonefile in zonefiles:
            with open(zonefile, "w+"):
                pass

        child_dir = os.path.join(zone_file_dir, "test_dir")
        os.mkdir(child_dir)

        clean_old_zone_files()
        self.assertIsNotNone(os.stat(child_dir))

    def test_rndc_config_includes_default_controls(self):
        dns_conf_dir = patch_dns_config_path(self)
        patch_dns_default_controls(self, enable=True)
        set_up_rndc()
        rndc_file = os.path.join(dns_conf_dir, MAAS_NAMED_RNDC_CONF_NAME)
        with open(rndc_file, encoding="ascii") as stream:
            conf_content = stream.read()
            self.assertIn(DEFAULT_CONTROLS, conf_content)

    def test_execute_rndc_command_executes_command(self):
        recorder = FakeMethod()
        fake_dir = patch_dns_config_path(self)
        self.patch(config, "call_and_check", recorder)
        command = factory.make_string()
        execute_rndc_command([command], timeout=sentinel.timeout)
        rndc_conf_path = os.path.join(fake_dir, MAAS_RNDC_CONF_NAME)
        expected_command = ["rndc", "-c", rndc_conf_path, command]
        self.assertEqual((expected_command,), recorder.calls[0][0])
        self.assertEqual({"timeout": sentinel.timeout}, recorder.calls[0][1])

    def test_extract_suggested_named_conf_extracts_section(self):
        named_part = factory.make_string()
        # Actual rndc-confgen output, mildly mangled for testing purposes.
        # Note the awkward line break.  The code works by matching that exact
        # line, so there's no leeway with the spacing.
        rndc_config = (
            dedent(
                """\
            # Start of rndc.conf
            %(rndc_part)s
            # End of rndc.conf

            # %(start_marker)s
            %(named_part)s
            # End of named.conf
        """
            )
            % {
                "start_marker": (
                    "Use with the following in named.conf, "
                    "adjusting the allow list as needed:"
                ),
                "rndc_part": factory.make_string(),
                "named_part": named_part,
            }
        )
        # What you get is just the suggested named.conf that's embedded in
        # the rndc-confgen output, not including its header and footer.
        self.assertEqual(
            named_part + "\n", extract_suggested_named_conf(rndc_config)
        )

    def test_extract_suggested_named_conf_notices_missing_boundary(self):
        # extract_suggested_named_conf raises an exception if it does not
        # find the expected boundary between the rndc and named parts of the
        # generated configuration.
        rndc_config = (
            dedent(
                """\
            # Start of rndc.conf
            %s

            %s
            # End of named.conf
        """
            )
            % (factory.make_string(), factory.make_string())
        )
        self.assertRaises(
            ValueError, extract_suggested_named_conf, rndc_config
        )

    def test_uncomment_named_conf_uncomments(self):
        rndc_conf = 'key "rndc_key" {}'
        self.assertEqual(rndc_conf, uncomment_named_conf("# %s" % rndc_conf))

    def test_uncomment_named_conf_uncomments_multiple_lines(self):
        # named.conf section, extracted from actual rndc-confgen output.
        # Note the weird %s: the config has a line ending in a space.
        named_comment = (
            dedent(
                """\
            # key "rndc-key" {
            # \talgorithm hmac-md5;
            # \tsecret "FuvtYZbYYLLJQKtn3zembg==";
            # };
            # %s
            # controls {
            # \tinet 127.0.0.1 port 953
            # \t\tallow { 127.0.0.1; } keys { "rndc-key"; };
            # };
            """
            )
            % ""
        )

        self.assertIn(
            'key "rndc-key" {\n' "\talgorithm hmac-md5;\n",
            uncomment_named_conf(named_comment),
        )


class TestComposeConfigPath(MAASTestCase):
    """Tests for `compose_config_path`."""

    def test_returns_filename_in_dns_config_dir(self):
        dns_dir = patch_dns_config_path(self)
        filename = factory.make_name("config")
        self.assertEqual(
            os.path.join(dns_dir, filename), compose_config_path(filename)
        )


class TestRenderDNSTemplate(MAASTestCase):
    """Tests for `render_dns_template`."""

    def test_renders_template(self):
        template_text = "X %d Y" % random.randint(1, 10000)
        self.assertEqual(
            template_text,
            render_dns_template(self.make_file(contents=template_text)),
        )

    def test_interpolates_parameters(self):
        param_name = factory.make_name("param", sep="_")
        param_value = factory.make_string()
        self.assertEqual(
            "X %s Y" % param_value,
            render_dns_template(
                self.make_file(contents="X {{%s}} Y" % param_name),
                {param_name: param_value},
            ),
        )

    def test_combines_parameter_dicts(self):
        self.assertEqual(
            "aaa bbb",
            render_dns_template(
                self.make_file(contents="{{one}} {{two}}"),
                {"one": "aaa"},
                {"two": "bbb"},
            ),
        )

    def test_takes_latest_value_of_redefined_parameter(self):
        self.assertEqual(
            "last",
            render_dns_template(
                self.make_file(contents="{{var}}"),
                {"var": "first"},
                {"var": "middle"},
                {"var": "last"},
            ),
        )

    def test_reports_missing_parameters(self):
        e = self.assertRaises(
            DNSConfigFail,
            render_dns_template,
            self.make_file(contents="{{x}}"),
            {"y": "?"},
        )
        self.assertIn("'x' is not defined", str(e))


class TestReportMissingConfigDir(MAASTestCase):
    """Tests for the `report_missing_config_dir` context manager."""

    def test_specially_reports_missing_config_dir(self):
        with ExpectedException(DNSConfigDirectoryMissing):
            with report_missing_config_dir():
                open(os.path.join(self.make_dir(), "nonexistent-file.txt"))

    def test_succeeds_if_no_exceptions(self):
        with report_missing_config_dir():
            pass
        # The real test is that we get here without error.
        pass

    def test_passes_on_other_similar_errors(self):
        with ExpectedException(PermissionError):
            with report_missing_config_dir():
                # OSError(EACCESS) is transmogrified, by Python itself, into
                # PermissionError. It's a subclass of OSError.
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
        self.patch(config, "atomic_write", Mock(side_effect=exception))
        self.assertRaises(IOError, dnsconfig.write_config)

    def test_write_config_skips_writing_if_overwrite_false(self):
        # If DNSConfig is created with overwrite=False, it won't
        # overwrite an existing config file.
        target_dir = patch_dns_config_path(self)
        random_content = factory.make_string()
        factory.make_file(
            location=target_dir,
            name=MAAS_NAMED_CONF_NAME,
            contents=random_content,
        )
        dnsconfig = DNSConfig()
        dnsconfig.write_config(overwrite=False)
        self.assertThat(
            os.path.join(target_dir, MAAS_NAMED_CONF_NAME),
            FileContains(random_content),
        )

    def test_write_config_writes_config_if_no_existing_file(self):
        # If DNSConfig is created with overwrite=False, the config file
        # will be written if no config file exists.
        target_dir = patch_dns_config_path(self)
        dnsconfig = DNSConfig()
        dnsconfig.write_config(overwrite=False)
        self.assertThat(
            os.path.join(target_dir, MAAS_NAMED_CONF_NAME), FileExists()
        )

    def test_write_config_writes_config(self):
        target_dir = patch_dns_config_path(self)
        domain = factory.make_string()
        network = IPNetwork("192.168.0.3/24")
        ip = factory.pick_ip_in_network(network)
        forward_zone = DNSForwardZoneConfig(
            domain, mapping={factory.make_string(): ip}
        )
        reverse_zone = DNSReverseZoneConfig(domain, network=network)
        dnsconfig = DNSConfig((forward_zone, reverse_zone))
        dnsconfig.write_config()
        self.assertThat(
            os.path.join(target_dir, MAAS_NAMED_CONF_NAME),
            FileContains(
                matcher=ContainsAll(
                    [
                        "zone.%s" % domain,
                        "zone.0.168.192.in-addr.arpa",
                        MAAS_NAMED_RNDC_CONF_NAME,
                    ]
                )
            ),
        )

    def test_write_config_with_forwarded_zones(self):
        name = factory.make_name("domain")
        ip = factory.make_ip_address()
        forwarded_zones = [(name, [(ip, None)])]
        target_dir = patch_dns_config_path(self)
        DNSConfig(forwarded_zones=forwarded_zones).write_config()
        config_path = os.path.join(target_dir, MAAS_NAMED_CONF_NAME)
        expected_content = dedent(
            f"""
        zone "{name}" {{
            type forward;
            forward only;
            forwarders {{
                {ip} port 53;
            }};
        }};
        """
        )
        config = read_isc_file(config_path)
        expected = parse_isc_string(expected_content)
        self.assertEqual(expected[f'zone "{name}"'], config[f'zone "{name}"'])

    def test_write_config_with_forwarded_zones_with_custom_port(self):
        name = factory.make_name("domain")
        ip = factory.make_ip_address()
        port = 5353
        forwarded_zones = [(name, [(ip, port)])]
        target_dir = patch_dns_config_path(self)
        DNSConfig(forwarded_zones=forwarded_zones).write_config()
        config_path = os.path.join(target_dir, MAAS_NAMED_CONF_NAME)
        expected_content = dedent(
            f"""
        zone "{name}" {{
            type forward;
            forward only;
            forwarders {{
                {ip} port {port};
            }};
        }};
        """
        )
        config = read_isc_file(config_path)
        print(config)
        expected = parse_isc_string(expected_content)
        self.assertEqual(expected[f'zone "{name}"'], config[f'zone "{name}"'])

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
                Not(StartsWith("\n")),
                EndsWith("\n"),
                Contains(target_dir),
                Contains(
                    'include "%s/%s"'
                    % (config.get_dns_config_dir(), DNSConfig.target_file_name)
                ),
            ),
        )


class TestDynamicDNSUpdate(MAASTestCase):
    def test_create_from_trigger_v4(self):
        domain = factory.make_name()
        update = DynamicDNSUpdate.create_from_trigger(
            operation="INSERT",
            zone=domain,
            name=f"{factory.make_name()}.{domain}",
            rectype="A",
            answer=factory.make_ip_address(ipv6=False),
        )
        self.assertEqual(update.rectype, "A")

    def test_create_from_trigger_v6(self):
        domain = factory.make_name()
        update = DynamicDNSUpdate.create_from_trigger(
            operation="INSERT",
            zone=domain,
            name=f"{factory.make_name()}.{domain}",
            rectype="A",
            answer=factory.make_ip_address(ipv6=True),
        )
        self.assertEqual(update.rectype, "AAAA")

    def test_answer_as_ip_returns_ip_when_answer_is_an_ip(self):
        domain = factory.make_name()
        update = DynamicDNSUpdate(
            operation="INSERT",
            zone=domain,
            name=f"{factory.make_name()}.{domain}",
            rectype="A",
            answer=factory.make_ip_address(),
        )
        self.assertIsNotNone(update.answer_as_ip)

    def test_answer_as_ip_returns_none_when_answer_is_not_an_ip(self):
        domain = factory.make_name()
        update = DynamicDNSUpdate(
            operation="INSERT",
            zone=domain,
            name=f"{factory.make_name()}.{domain}",
            rectype="CNAME",
            answer=factory.make_name(),
        )
        self.assertIsNone(update.answer_as_ip)

    def test_answer_is_ip_returns_true_when_answer_is_an_ip(self):
        domain = factory.make_name()
        update = DynamicDNSUpdate(
            operation="INSERT",
            zone=domain,
            name=f"{factory.make_name()}.{domain}",
            rectype="A",
            answer=factory.make_ip_address(),
        )
        self.assertTrue(update.answer_is_ip)

    def test_answer_is_ip_returns_false_when_answer_is_not_an_ip(self):
        domain = factory.make_name()
        update = DynamicDNSUpdate(
            operation="INSERT",
            zone=domain,
            name=f"{factory.make_name()}.{domain}",
            rectype="CNAME",
            answer=factory.make_name(),
        )
        self.assertFalse(update.answer_is_ip)

    def test_as_reverse_record_update(self):
        domain = factory.make_name()
        ip_version = random.choice([4, 6])
        host_bits = (
            random.randint(8, 24)
            if ip_version == 4
            else random.randint(8, 124)
        )
        subnet = factory.make_ip4_or_6_network(
            version=ip_version, host_bits=host_bits
        )
        fwd_update = DynamicDNSUpdate(
            operation="INSERT",
            zone=domain,
            name=f"{factory.make_name()}.{domain}",
            rectype="A",
            answer=str(IPAddress(subnet.next())),
        )
        expected_rev_update = DynamicDNSUpdate(
            operation="INSERT",
            zone=domain,
            name=IPAddress(fwd_update.answer).reverse_dns,
            rectype="PTR",
            ttl=fwd_update.ttl,
            subnet=str(subnet),
            answer=fwd_update.name,
        )
        rev_update = DynamicDNSUpdate.as_reverse_record_update(
            fwd_update, subnet
        )
        self.assertEqual(expected_rev_update.name, rev_update.name)
        self.assertEqual(expected_rev_update.rectype, rev_update.rectype)
        self.assertEqual(expected_rev_update.answer, rev_update.answer)

    def test_as_reverse_record_update_for_glue_zone_v4(self):
        domain = factory.make_name()
        subnet = IPNetwork("10.1.1.0/25")
        fwd_update = DynamicDNSUpdate(
            operation="INSERT",
            zone=domain,
            name=f"{factory.make_name()}.{domain}",
            rectype="A",
            answer=str("10.1.1.5"),
        )
        expected_rev_update = DynamicDNSUpdate(
            operation="INSERT",
            zone=domain,
            name="5.0-25.1.1.10.in-addr.arpa.",
            rectype="PTR",
            ttl=fwd_update.ttl,
            subnet=str(subnet),
            answer=fwd_update.name,
        )
        rev_update = DynamicDNSUpdate.as_reverse_record_update(
            fwd_update, subnet
        )
        self.assertEqual(expected_rev_update.name, rev_update.name)
        self.assertEqual(expected_rev_update.rectype, rev_update.rectype)
        self.assertEqual(expected_rev_update.answer, rev_update.answer)

    def test_as_reverse_record_update_for_glue_zone_v6(self):
        domain = factory.make_name()
        subnet = IPNetwork("fc55:4c7c:a5ea:57b0:7cad:a076:a844:8000/126")
        fwd_update = DynamicDNSUpdate(
            operation="INSERT",
            zone=domain,
            name=f"{factory.make_name()}.{domain}",
            rectype="A",
            answer="fc55:4c7c:a5ea:57b0:7cad:a076:a844:8001",
        )
        expected_rev_update = DynamicDNSUpdate(
            operation="INSERT",
            zone=domain,
            name="1.8000-126.0.0.8.4.4.8.a.6.7.0.a.d.a.c.7.0.b.7.5.a.e.5.a.c.7.c.4.5.5.c.f.ip6.arpa.",
            rectype="PTR",
            ttl=fwd_update.ttl,
            subnet=str(subnet),
            answer=fwd_update.name,
        )
        rev_update = DynamicDNSUpdate.as_reverse_record_update(
            fwd_update, subnet
        )
        self.assertEqual(expected_rev_update.name, rev_update.name)
        self.assertEqual(expected_rev_update.rectype, rev_update.rectype)
        self.assertEqual(expected_rev_update.answer, rev_update.answer)

    def test_as_reverse_record_update_no_zone_set(self):
        domain = factory.make_name()
        subnet = IPNetwork("10.1.1.128/25")
        fwd_update = DynamicDNSUpdate(
            operation="INSERT",
            zone=domain,
            name=f"{factory.make_name()}.{domain}",
            rectype="A",
            answer=str("10.1.1.161"),
        )
        expected_rev_update = DynamicDNSUpdate(
            operation="INSERT",
            zone="128-25.1.1.10.in-addr.arpa.",
            name="161.128-25.1.1.10.in-addr.arpa.",
            rectype="PTR",
            ttl=fwd_update.ttl,
            subnet=str(subnet),
            answer=fwd_update.name,
        )
        rev_update = DynamicDNSUpdate.as_reverse_record_update(
            fwd_update, subnet
        )
        self.assertEqual(expected_rev_update.name, rev_update.name)
        self.assertEqual(expected_rev_update.rectype, rev_update.rectype)
        self.assertEqual(expected_rev_update.answer, rev_update.answer)
        self.assertEqual(expected_rev_update.zone, rev_update.zone)
