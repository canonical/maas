# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `validate_nonoverlapping_networks`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django.core.exceptions import ValidationError
from maasserver.enum import NODEGROUPINTERFACE_MANAGEMENT
from maasserver.forms import validate_nonoverlapping_networks
from maastesting.factory import factory
from testtools import TestCase
from testtools.matchers import (
    Contains,
    MatchesAll,
    MatchesRegex,
    StartsWith,
)


class TestValidateNonoverlappingNetworks(TestCase):
    """Tests for `validate_nonoverlapping_networks`."""

    def make_interface_definition(self, ip, netmask, name=None):
        """Return a minimal imitation of an interface definition."""
        if name is None:
            name = factory.make_name('itf')
        return {
            'interface': name,
            'ip': ip,
            'subnet_mask': netmask,
            'management': NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
        }

    def test_accepts_zero_interfaces(self):
        validate_nonoverlapping_networks([])
        # Success is getting here without error.
        pass

    def test_accepts_single_interface(self):
        validate_nonoverlapping_networks(
            [self.make_interface_definition('10.1.1.1', '255.255.0.0')])
        # Success is getting here without error.
        pass

    def test_accepts_disparate_ranges(self):
        validate_nonoverlapping_networks([
            self.make_interface_definition('10.1.0.0', '255.255.0.0'),
            self.make_interface_definition('192.168.0.0', '255.255.255.0'),
            ])
        # Success is getting here without error.
        pass

    def test_accepts_near_neighbours(self):
        validate_nonoverlapping_networks([
            self.make_interface_definition('10.1.0.0', '255.255.0.0'),
            self.make_interface_definition('10.2.0.0', '255.255.0.0'),
            ])
        # Success is getting here without error.
        pass

    def test_rejects_identical_ranges(self):
        definitions = [
            self.make_interface_definition('192.168.0.0', '255.255.255.0'),
            self.make_interface_definition('192.168.0.0', '255.255.255.0'),
            ]
        error = self.assertRaises(
            ValidationError,
            validate_nonoverlapping_networks, definitions)
        error_text = error.messages[0]
        self.assertThat(
            error_text, MatchesRegex(
                "Conflicting networks on [^\\s]+ and [^\\s]+: "
                "address ranges overlap."))
        self.assertThat(
            error_text,
            MatchesAll(
                *(
                    Contains(definition['interface'])
                    for definition in definitions
                )))

    def test_rejects_nested_ranges(self):
        definitions = [
            self.make_interface_definition('192.168.0.0', '255.255.0.0'),
            self.make_interface_definition('192.168.100.0', '255.255.255.0'),
            ]
        error = self.assertRaises(
            ValidationError,
            validate_nonoverlapping_networks, definitions)
        self.assertIn("Conflicting networks", unicode(error))

    def test_detects_conflict_regardless_of_order(self):
        definitions = [
            self.make_interface_definition('192.168.100.0', '255.255.255.0'),
            self.make_interface_definition('192.168.1.0', '255.255.255.0'),
            self.make_interface_definition('192.168.64.0', '255.255.192.0'),
            ]
        error = self.assertRaises(
            ValidationError,
            validate_nonoverlapping_networks, definitions)
        self.assertThat(error.messages[0], StartsWith("Conflicting networks"))
