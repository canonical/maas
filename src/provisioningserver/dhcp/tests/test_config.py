# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test cases for dhcp.config"""

__all__ = []

from os import (
    makedirs,
    path,
)
from textwrap import dedent
import traceback

from maastesting.factory import factory
from provisioningserver.boot import BootMethodRegistry
from provisioningserver.dhcp import config
from provisioningserver.dhcp.testing.config import (
    make_dhcp_snippets,
    make_failover_peer_config,
    make_host,
    make_shared_network,
)
from provisioningserver.testing.testcase import PservTestCase
import tempita
from testtools.matchers import (
    Contains,
    ContainsAll,
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


def make_sample_params(hosts=None):
    """Return a dict of arbitrary DHCP configuration parameters."""
    failover_peers = [
        make_failover_peer_config()
        for _ in range(3)
    ]
    shared_networks = [
        make_shared_network()
        for _ in range(3)
    ]
    if hosts is None:
        hosts = [
            make_host()
            for _ in range(3)
        ]
    return {
        'omapi_key': factory.make_name('key'),
        'failover_peers': failover_peers,
        'shared_networks': shared_networks,
        'hosts': hosts,
        'global_dhcp_snippets': make_dhcp_snippets(),
        }


class TestGetConfig(PservTestCase):
    """Tests for `get_config`."""

    def patch_template(self, name=None, template_content=sample_template):
        """Patch the DHCP config template with the given contents.

        Returns a `tempita.Template` of the given template, so that a test
        can make its own substitutions and compare to those made by the
        code being tested.
        """
        if name is None:
            name = 'dhcpd.conf.template'
        fake_root = self.make_dir()
        template_dir = path.join(fake_root, 'templates', 'dhcp')
        makedirs(template_dir)
        template = factory.make_file(
            template_dir, name, contents=template_content)
        self.patch(config, 'locate_template').return_value = template
        return tempita.Template(template_content, name=template)

    def test__uses_branch_template_by_default(self):
        # Since the branch comes with dhcp templates in etc/maas, we can
        # instantiate those templates without any hackery.
        self.assertIsNotNone(
            config.get_config('dhcpd.conf.template', **make_sample_params()))
        self.assertIsNotNone(
            config.get_config('dhcpd6.conf.template', **make_sample_params()))

    def test__substitutes_parameters(self):
        template_name = factory.make_name('template')
        template = self.patch_template(name=template_name)
        params = make_sample_params()
        self.assertEqual(
            template.substitute(params),
            config.get_config(template_name, **params))

    def test__complains_if_too_few_parameters(self):
        template = self.patch_template()
        params = make_sample_params()
        del params['shared_networks'][0]['subnets'][0]['subnet']

        e = self.assertRaises(
            config.DHCPConfigError,
            config.get_config, 'dhcpd.conf.template', **params)

        tbe = traceback.TracebackException.from_exception(e)
        self.assertDocTestMatches(
            dedent("""\
            Traceback (most recent call last):
            ...
            KeyError: 'subnet at line ... column ... in file %s'
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
            """ % template.name),
            "".join(tbe.format()),
        )

    def test__includes_compose_conditional_bootloader(self):
        params = make_sample_params()
        bootloader = config.compose_conditional_bootloader()
        self.assertThat(
            config.get_config('dhcpd.conf.template', **params),
            Contains(bootloader))

    def test__renders_without_ntp_servers_set(self):
        params = make_sample_params()
        for network in params['shared_networks']:
            for subnet in network['subnets']:
                del subnet['ntp_server']
        template = self.patch_template()
        rendered = template.substitute(params)
        self.assertEqual(
            rendered,
            config.get_config('dhcpd.conf.template', **params))
        self.assertNotIn("ntp-servers", rendered)

    def test__renders_router_ip_if_present(self):
        params = make_sample_params()
        router_ip = factory.make_ipv4_address()
        params['shared_networks'][0]['subnets'][0]['router_ip'] = router_ip
        self.assertThat(
            config.get_config('dhcpd.conf.template', **params),
            Contains(router_ip))

    def test__renders_with_empty_string_router_ip(self):
        params = make_sample_params()
        for network in params['shared_networks']:
            for subnet in network['subnets']:
                subnet['router_ip'] = ''
        template = self.patch_template()
        rendered = template.substitute(params)
        self.assertEqual(
            rendered,
            config.get_config('dhcpd.conf.template', **params))
        self.assertNotIn("routers", rendered)

    def test__renders_with_hosts(self):
        network = factory.make_ipv4_network()
        hosts = [
            make_host(network)
            for _ in range(3)
        ]
        params = make_sample_params(hosts)
        config_output = config.get_config('dhcpd.conf.template', **params)
        self.assertThat(
            config_output,
            ContainsAll([
                host['host']
                for host in hosts
            ]))
        self.assertThat(
            config_output,
            ContainsAll([
                host['mac']
                for host in hosts
            ]))
        self.assertThat(
            config_output,
            ContainsAll([
                host['ip']
                for host in hosts
            ]))

    def test__renders_global_dhcp_snippets(self):
        params = make_sample_params()
        config_output = config.get_config('dhcpd.conf.template', **params)
        self.assertThat(
            config_output,
            ContainsAll([
                dhcp_snippet['value']
                for dhcp_snippet in params['global_dhcp_snippets']
            ]))

    def test__renders_subnet_dhcp_snippets(self):
        params = make_sample_params()
        config_output = config.get_config('dhcpd.conf.template', **params)
        for shared_network in params['shared_networks']:
            for subnet in shared_network['subnets']:
                self.assertThat(
                    config_output,
                    ContainsAll([
                        dhcp_snippet['value']
                        for dhcp_snippet in subnet['dhcp_snippets']
                    ]))

    def test__renders_node_dhcp_snippets(self):
        params = make_sample_params()
        config_output = config.get_config('dhcpd.conf.template', **params)
        for host in params['hosts']:
            self.assertThat(
                config_output,
                ContainsAll([
                    dhcp_snippet['value']
                    for dhcp_snippet in host['dhcp_snippets']
                ]))


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
