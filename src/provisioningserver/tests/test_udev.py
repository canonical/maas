# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for udev rules generation code."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.udev import (
    compose_network_interfaces_udev_rules,
    compose_udev_attr_equality,
    compose_udev_equality,
    compose_udev_rule,
    compose_udev_setting,
)
from testtools.matchers import ContainsAll


class TestComposeUdevEquality(MAASTestCase):

    def test__generates_comparison_with_double_equals_sign(self):
        self.assertEqual('KEY=="value"', compose_udev_equality('KEY', 'value'))

    def test__rejects_lower_case_letters_in_key(self):
        self.assertRaises(
            AssertionError,
            compose_udev_equality, 'key', 'value')


class TestComposeUdevAttrEquality(MAASTestCase):

    def test__generates_comparison_with_double_equals_sign(self):
        self.assertEqual(
            'ATTR{key}=="value"',
            compose_udev_attr_equality('key', 'value'))

    def test__rejects_upper_case_letters_in_key(self):
        self.assertRaises(
            AssertionError,
            compose_udev_attr_equality, 'KEY', 'value')


class TestComposeUdevSetting(MAASTestCase):

    def test__generates_assignment_with_single_equals_sign(self):
        self.assertEqual('KEY="value"', compose_udev_setting('KEY', 'value'))

    def test__rejects_lower_case_letters_in_key(self):
        self.assertRaises(
            AssertionError,
            compose_udev_setting, 'key', 'value')


class TestComposeUdevRule(MAASTestCase):

    def test__generates_rule(self):
        interface = factory.make_name('eth')
        mac = factory.make_mac_address()
        expected_rule = (
            'SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", '
            'ATTR{address}=="%(mac)s", NAME="%(interface)s"\n'
            ) % {'mac': mac, 'interface': interface}
        self.assertEqual(expected_rule, compose_udev_rule(interface, mac))


class TestComposeNetworkInterfacesUdevRules(MAASTestCase):

    def test__generates_udev_rules(self):
        interfaces = [
            (factory.make_name('eth'), factory.make_mac_address())
            for _ in range(2)
            ]

        self.assertThat(
            compose_network_interfaces_udev_rules(interfaces),
            ContainsAll([
                'ATTR{address}=="%s", NAME="%s"\n' % (interface, mac)
                for mac, interface in interfaces
                ]))
