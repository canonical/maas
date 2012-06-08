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

from provisioningserver.dhcp import config
import tempita
from testtools import TestCase
from testtools.matchers import MatchesRegex


class TestDHCPConfig(TestCase):

    def setUp(self):
        super(TestDHCPConfig, self).setUp()
        self.template_content = dedent("""\
            {{subnet}}
            {{subnet_mask}}
            {{next_server}}
            {{broadcast_address}}
            {{dns_servers}}
            {{gateway}}
            {{low_range}}
            {{high_range}}
            """)
        self.template = tempita.Template(
            content=self.template_content,
            name="%s.template" % self.__class__.__name__)

    def test_param_substitution(self):
        self.patch(config, "template", self.template)

        params = dict(
            subnet="10.0.0.0",
            subnet_mask="255.0.0.0",
            next_server="10.0.0.1",
            broadcast_address="10.255.255.255",
            dns_servers="10.1.0.1 10.1.0.2",
            gateway="10.0.0.2",
            low_range="10.0.0.3",
            high_range="10.0.0.254")

        output = config.get_config(**params)

        expected = self.template.substitute(params)
        self.assertEqual(expected, output)

    def test_get_config_with_too_few_parameters(self):
        self.patch(config, "template", self.template)

        params = dict(
            # subnet is missing
            subnet_mask="255.0.0.0",
            next_server="10.0.0.1",
            broadcast_address="10.255.255.255",
            dns_servers="10.1.0.1 10.1.0.2",
            gateway="10.0.0.2",
            low_range="10.0.0.3",
            high_range="10.0.0.254")

        e = self.assertRaises(
            config.DHCPConfigError, config.get_config, **params)

        self.assertThat(
            e.message, MatchesRegex(
                "name 'subnet' is not defined at line \d+ column \d+ "
                "in file %s" % self.template.name))
