# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test cases for dhcp.config"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from textwrap import dedent

from maastesting.matchers import ContainsAll
from provisioningserver.dhcp import config
from provisioningserver.pxe.tftppath import compose_bootloader_path
import tempita
from testtools import TestCase
from testtools.matchers import MatchesRegex

# Simple test version of the DHCP template.  Contains parameter
# substitutions, but none that aren't also in the real template.
sample_template = dedent("""\
    {{omapi_shared_key}}
    {{subnet}}
    {{subnet_mask}}
    {{next_server}}
    {{broadcast_ip}}
    {{dns_servers}}
    {{router_ip}}
    {{ip_range_low}}
    {{ip_range_high}}
""")


def make_sample_params():
    """Produce a dict of sample parameters.

    The sample provides all parameters used by the DHCP template.
    """
    return dict(
        omapi_shared_key="random",
        subnet="10.0.0.0",
        subnet_mask="255.0.0.0",
        next_server="10.0.0.1",
        broadcast_ip="10.255.255.255",
        dns_servers="10.1.0.1 10.1.0.2",
        router_ip="10.0.0.2",
        ip_range_low="10.0.0.3",
        ip_range_high="10.0.0.254",
        )


class TestDHCPConfig(TestCase):

    def patch_template(self, template_content=sample_template):
        """Patch the DHCP config template with the given contents."""
        name = "%s.template" % self.__class__.__name__
        template = tempita.Template(content=template_content, name=name)
        self.patch(config, "template", template)
        return template

    def test_param_substitution(self):
        template = self.patch_template()
        params = make_sample_params()
        self.assertEqual(
            template.substitute(params),
            config.get_config(**params))

    def test_get_config_with_too_few_parameters(self):
        template = self.patch_template()
        params = make_sample_params()
        del params['subnet']

        e = self.assertRaises(
            config.DHCPConfigError, config.get_config, **params)

        self.assertThat(
            e.message, MatchesRegex(
                "name 'subnet' is not defined at line \d+ column \d+ "
                "in file %s" % template.name))

    def test_config_refers_to_PXE_for_supported_architectures(self):
        params = make_sample_params()
        bootloaders = config.compose_bootloaders()
        archs = [
            ('i386', 'generic'),
            ('arm', 'highbank'),
            ]
        paths = [bootloaders[arch] for arch in archs]
        output = config.get_config(**params)
        self.assertThat(output, ContainsAll(paths))

    def test_compose_bootloaders_lists_tftp_paths(self):
        sample_arch = ('i386', 'generic')
        self.assertEqual(
            compose_bootloader_path(*sample_arch),
            config.compose_bootloaders()[sample_arch])
