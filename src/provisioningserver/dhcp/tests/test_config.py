# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test cases for dhcp.config"""

__all__ = []

from base64 import b64encode
from itertools import count
import pipes
import random
import re
import subprocess
import tempfile
from textwrap import dedent
import traceback

from maastesting.factory import factory
from maastesting.matchers import GreaterThanOrEqual
from provisioningserver.boot import BootMethodRegistry
from provisioningserver.dhcp import config
from provisioningserver.dhcp.testing.config import (
    make_failover_peer_config,
    make_global_dhcp_snippets,
    make_host,
    make_shared_network,
)
from provisioningserver.testing.testcase import PservTestCase
from provisioningserver.utils.shell import select_c_utf8_locale
import tempita
from testtools.content import (
    Content,
    text_content,
    UTF8_TEXT,
)
from testtools.matchers import (
    AfterPreprocessing,
    Contains,
    ContainsAll,
    Equals,
)

# Simple test version of the DHCP template.  Contains parameter
# substitutions, but none that aren't also in the real template.
sample_template = dedent("""\
    {{omapi_key}}
    {{for failover_peer in failover_peers}}
        {{failover_peer['name']}}
        {{failover_peer['mode']}}
        {{failover_peer['address']}}
        {{failover_peer['peer_address']}}
    {{endfor}}
    {{for shared_network in shared_networks}}
        {{shared_network['name']}}
        {{for dhcp_subnet in shared_network['subnets']}}
            {{dhcp_subnet['subnet']}}
            {{dhcp_subnet['subnet_mask']}}
            {{dhcp_subnet['broadcast_ip']}}
            {{dhcp_subnet['dns_servers']}}
            {{dhcp_subnet['domain_name']}}
            {{dhcp_subnet['router_ip']}}
            {{for pool in dhcp_subnet['pools']}}
                {{pool['ip_range_low']}}
                {{pool['ip_range_high']}}
                {{pool['failover_peer']}}
            {{endfor}}
        {{endfor}}
    {{endfor}}
    {{for host in hosts}}
        {{host['host']}}
        {{host['mac']}}
        {{host['ip']}}
    {{endfor}}
""")


def make_sample_params(ipv6=False):
    """Return a dict of arbitrary DHCP configuration parameters."""
    failover_peers = [
        make_failover_peer_config()
        for _ in range(3)
    ]
    shared_networks = [
        make_shared_network(ipv6=ipv6)
        for _ in range(3)
    ]

    # Fix-up failover peers referenced in pools so that they refer to a
    # predefined peer; `dhcpd -t` will otherwise reject the configuration.
    for shared_network in shared_networks:
        for subnet in shared_network["subnets"]:
            for pool in subnet["pools"]:
                peer = random.choice(failover_peers)
                pool["failover_peer"] = peer["name"]

    return {
        'omapi_key': b64encode(factory.make_bytes()).decode("ascii"),
        'failover_peers': failover_peers,
        'shared_networks': shared_networks,
        'hosts': [make_host(ipv6=ipv6) for _ in range(3)],
        'global_dhcp_snippets': make_global_dhcp_snippets(),
    }


def validate_dhcpd_configuration(test, configuration, ipv6):
    """Validate `configuration` using `dhcpd` itself."""
    with tempfile.NamedTemporaryFile(
            "w", encoding="ascii", prefix="dhcpd.",
            suffix=".conf") as conffile:
        # Write the configuration to the temporary file.
        conffile.write(configuration)
        conffile.flush()
        # Add line numbers to configuration and add as a detail. This will
        # make it much easier to debug; `dhcpd -t` prints line numbers for any
        # errors it finds.
        test.addDetail(conffile.name, Content(
            UTF8_TEXT, lambda: map(str.encode, (
                "> %3d  %s" % entry for entry in zip(
                    count(1), configuration.splitlines(keepends=True))))))
        # Call `dhcpd` via `aa-exec --profile unconfined`. The latter is
        # needed so that `dhcpd` can open the configuration file from /tmp.
        process = subprocess.Popen(
            ("aa-exec", "--profile", "unconfined", "dhcpd",
             ("-6" if ipv6 else "-4"), "-t", "-cf", conffile.name),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=select_c_utf8_locale())
        command = " ".join(map(pipes.quote, process.args))
        output, _ = process.communicate()
        # Record the output from `dhcpd -t` as a detail.
        test.addDetail(
            "stdout/err from `%s`" % command,
            text_content(output.decode("utf-8")))
        # Check that it completed successfully.
        test.assertThat(
            process.returncode, Equals(0),
            "`%s` failed." % command)


class TestGetConfig(PservTestCase):
    """Tests for `get_config`."""

    scenarios = [
        ("v4", dict(template='dhcpd.conf.template', ipv6=False)),
        ("v6", dict(template='dhcpd6.conf.template', ipv6=True)),
    ]

    def patch_template(self, name):
        """Patch the DHCP config template with `sample_template`.

        Returns a `tempita.Template` of the `sample_template`, so that a test
        can make its own substitutions and compare to those made by the code
        being tested.

        Be careful! You're NOT testing using the real template any more!
        """
        template = self.make_file(name, contents=sample_template)
        self.patch(config, 'locate_template').return_value = template
        return tempita.Template(sample_template, name=template)

    def test__substitutes_parameters(self):
        template_name = factory.make_name('template')
        template = self.patch_template(name=template_name)
        params = make_sample_params(ipv6=self.ipv6)
        self.assertEqual(
            template.substitute(params.copy()),
            config.get_config(template_name, **params))

    def test__uses_branch_template_by_default(self):
        # Since the branch comes with dhcp templates in etc/maas, we can
        # instantiate those templates without any hackery.
        self.assertIsNotNone(
            config.get_config(
                self.template, **make_sample_params(ipv6=self.ipv6)))

    def test__complains_if_too_few_parameters(self):
        params = make_sample_params(ipv6=self.ipv6)
        del params['hosts'][0]['mac']

        e = self.assertRaises(
            config.DHCPConfigError,
            config.get_config, self.template, **params)

        tbe = traceback.TracebackException.from_exception(e)
        self.assertDocTestMatches(
            dedent("""\
            Traceback (most recent call last):
            ...
            KeyError: 'mac at line ... column ... in file ...'
            <BLANKLINE>
            ...
            <BLANKLINE>
            The above exception was the direct cause of the following
            exception:
            <BLANKLINE>
            Traceback (most recent call last):
            ...
            provisioningserver.dhcp.config.DHCPConfigError: Failed to render
            DHCP configuration.
            """),
            "".join(tbe.format()),
        )

    def test__includes_compose_conditional_bootloader(self):
        params = make_sample_params(ipv6=self.ipv6)
        bootloader = config.compose_conditional_bootloader()
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        self.assertThat(rendered, Contains(bootloader))

    def test__renders_dns_servers_as_comma_separated_list(self):
        params = make_sample_params(ipv6=self.ipv6)
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        dns_servers_expected = [
            ", ".join(subnet["dns_servers"].split())
            for network in params['shared_networks']
            for subnet in network['subnets']
        ]
        dns_servers_pattern = r"\b%s\s+(.+);" % re.escape(
            "dhcp6.name-servers" if self.ipv6 else "domain-name-servers")
        dns_servers_observed = re.findall(dns_servers_pattern, rendered)
        self.assertEqual(dns_servers_expected, dns_servers_observed)

    def test__renders_without_dns_servers_set(self):
        params = make_sample_params(ipv6=self.ipv6)
        for network in params['shared_networks']:
            for subnet in network['subnets']:
                subnet['dns_servers'] = ""
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        self.assertNotIn("dhcp6.name-servers", rendered)  # IPv6
        self.assertNotIn("domain-name-servers", rendered)  # IPv4

    def test__renders_ntp_servers_as_comma_separated_list(self):
        params = make_sample_params(ipv6=self.ipv6)
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        ntp_servers_expected = [
            ", ".join(subnet["ntp_servers"].split())
            for network in params['shared_networks']
            for subnet in network['subnets']
        ]
        ntp_servers_observed = re.findall(r"\bntp-servers\s+(.+);", rendered)
        self.assertEqual(ntp_servers_expected, ntp_servers_observed)

    def test__renders_without_ntp_servers_set(self):
        params = make_sample_params(ipv6=self.ipv6)
        for network in params['shared_networks']:
            for subnet in network['subnets']:
                subnet['ntp_servers'] = ""
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        self.assertNotIn("ntp-servers", rendered)

    def test__renders_router_ip_if_present(self):
        params = make_sample_params(ipv6=self.ipv6)
        router_ip = factory.make_ipv4_address()
        params['shared_networks'][0]['subnets'][0]['router_ip'] = router_ip
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        self.assertThat(rendered, Contains(router_ip))

    def test__renders_with_empty_string_router_ip(self):
        params = make_sample_params(ipv6=self.ipv6)
        for network in params['shared_networks']:
            for subnet in network['subnets']:
                subnet['router_ip'] = ''
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        # Remove all lines that have been commented out.
        rendered = "".join(
            line for line in rendered.splitlines(keepends=True)
            if not line.lstrip().startswith("#"))
        self.assertNotIn("option routers", rendered)

    def test__renders_with_hosts(self):
        params = make_sample_params(ipv6=self.ipv6)
        self.assertThat(
            params["hosts"], AfterPreprocessing(
                len, GreaterThanOrEqual(1)))
        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)
        self.assertThat(
            config_output,
            ContainsAll([
                host['host']
                for host in params["hosts"]
            ]))
        self.assertThat(
            config_output,
            ContainsAll([
                host['mac']
                for host in params["hosts"]
            ]))
        self.assertThat(
            config_output,
            ContainsAll([
                host['ip']
                for host in params["hosts"]
            ]))

    def test__renders_global_dhcp_snippets(self):
        params = make_sample_params(ipv6=self.ipv6)
        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)
        self.assertThat(
            config_output,
            ContainsAll([
                dhcp_snippet['value']
                for dhcp_snippet in params['global_dhcp_snippets']
            ]))

    def test__renders_subnet_dhcp_snippets(self):
        params = make_sample_params(ipv6=self.ipv6)
        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)
        for shared_network in params['shared_networks']:
            for subnet in shared_network['subnets']:
                self.assertThat(
                    config_output,
                    ContainsAll([
                        dhcp_snippet['value']
                        for dhcp_snippet in subnet['dhcp_snippets']
                    ]))

    def test__renders_node_dhcp_snippets(self):
        params = make_sample_params(ipv6=self.ipv6)
        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)
        for host in params['hosts']:
            self.assertThat(
                config_output,
                ContainsAll([
                    dhcp_snippet['value']
                    for dhcp_snippet in host['dhcp_snippets']
                ]))

    def test__renders_subnet_cidr(self):
        params = make_sample_params(ipv6=self.ipv6)
        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)
        for shared_network in params['shared_networks']:
            for subnet in shared_network['subnets']:
                if self.ipv6 is True:
                    expected = "subnet6 %s" % subnet['subnet_cidr']
                else:
                    expected = "subnet %s netmask %s" % (
                        subnet['subnet'], subnet['subnet_mask'])
                self.assertThat(
                    config_output,
                    Contains(expected))


class TestComposeConditionalBootloader(PservTestCase):
    """Tests for `compose_conditional_bootloader`."""

    def test__composes_bootloader_section(self):
        output = config.compose_conditional_bootloader()
        for name, method in BootMethodRegistry:
            if name == "pxe":
                self.assertThat(output, Contains("else"))
                self.assertThat(output, Contains(method.bootloader_path))
            elif method.arch_octet is not None:
                self.assertThat(output, Contains(method.arch_octet))
                self.assertThat(output, Contains(method.bootloader_path))
            else:
                # No DHCP configuration is rendered for boot methods that have
                # no `arch_octet`, with the solitary exception of PXE.
                pass
