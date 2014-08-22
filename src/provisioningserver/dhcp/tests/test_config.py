# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test cases for dhcp.config"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from os import (
    makedirs,
    path,
    )
from textwrap import dedent

from fixtures import EnvironmentVariableFixture
from maastesting.factory import factory
from provisioningserver.boot import BootMethodRegistry
from provisioningserver.dhcp import config
from provisioningserver.dhcp.testing.config import make_subnet_config
from provisioningserver.testing.testcase import PservTestCase
import tempita
from testtools.matchers import (
    Contains,
    MatchesRegex,
    )

# Simple test version of the DHCP template.  Contains parameter
# substitutions, but none that aren't also in the real template.
sample_template = dedent("""\
    {{omapi_key}}
    {{for dhcp_subnet in dhcp_subnets}}
        {{dhcp_subnet['subnet']}}
        {{dhcp_subnet['interface']}}
        {{dhcp_subnet['subnet_mask']}}
        {{dhcp_subnet['broadcast_ip']}}
        {{dhcp_subnet['dns_servers']}}
        {{dhcp_subnet['domain_name']}}
        {{dhcp_subnet['router_ip']}}
        {{dhcp_subnet['ip_range_low']}}
        {{dhcp_subnet['ip_range_high']}}
    {{endfor}}
""")


def make_sample_params():
    """Return a dict of arbitrary DHCP configuration parameters."""
    if factory.pick_bool():
        network = factory.getRandomNetwork()
    else:
        network = factory.make_ipv6_network()
    return {
        'omapi_key': factory.make_name('key'),
        'dhcp_subnets': [make_subnet_config(network)],
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
        fake_etc_maas = self.make_dir()
        self.useFixture(EnvironmentVariableFixture(
            'MAAS_CONFIG_DIR', fake_etc_maas))
        template_dir = path.join(fake_etc_maas, 'templates', 'dhcp')
        makedirs(template_dir)
        template = factory.make_file(
            template_dir, name, contents=template_content)
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

    def test__quotes_interface(self):
        # The interface name doesn't normally need to be quoted, but the
        # template does quote it, in case it contains dots or other weird
        # but legal characters (bug 1306335).
        params = make_sample_params()
        self.assertIn(
            'interface "%s";' % params['dhcp_subnets'][0]['interface'],
            config.get_config('dhcpd.conf.template', **params))

    def test__complains_if_too_few_parameters(self):
        template = self.patch_template()
        params = make_sample_params()
        del params['dhcp_subnets'][0]['subnet']

        e = self.assertRaises(
            config.DHCPConfigError,
            config.get_config, 'dhcpd.conf.template', **params)

        self.assertThat(
            unicode(e), MatchesRegex(
                "subnet at line \d+ column \d+ "
                "in file %s" % template.name))

    def test__includes_compose_conditional_bootloader(self):
        params = make_sample_params()
        bootloader = config.compose_conditional_bootloader()
        self.assertThat(
            config.get_config('dhcpd.conf.template', **params),
            Contains(bootloader))

    def test__renders_without_ntp_servers_set(self):
        params = make_sample_params()
        del params['dhcp_subnets'][0]['ntp_server']
        template = self.patch_template()
        rendered = template.substitute(params)
        self.assertEqual(
            rendered,
            config.get_config('dhcpd.conf.template', **params))
        self.assertNotIn("ntp-servers", rendered)


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
