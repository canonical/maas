# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test parser for 'ip link show'."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )
from testtools import ExpectedException
from testtools.matchers import Equals


str = None

__metaclass__ = type
__all__ = []

from textwrap import dedent

from maasserver.utils.iplink import (
    _get_settings_dict,
    _add_additional_interface_properties,
    _parse_interface_definition,
    parse_ip_link,
)

from maastesting.testcase import MAASTestCase


class TestHelperFunctions(MAASTestCase):
    def test_get_settings_dict_ignores_empty_settings_string(self):
        settings = _get_settings_dict("")
        self.assertEqual({}, settings)

    def test_get_settings_dict_asserts_for_odd_number_of_tokens(self):
        with ExpectedException(AssertionError):
            _get_settings_dict("mtu")
        with ExpectedException(AssertionError):
            _get_settings_dict("mtu 1500 qdisc")

    def test_get_settings_dict_creates_correct_dictionary(self):
        settings = _get_settings_dict("mtu 1073741824 state AWESOME")
        self.assertThat(settings, Equals(
            {'mtu': '1073741824', 'state': 'AWESOME'}))

    def test_get_settings_dict_ignores_whitespace(self):
        settings = _get_settings_dict("    mtu   1073741824  state  AWESOME  ")
        self.assertThat(settings, Equals(
            {'mtu': '1073741824', 'state': 'AWESOME'}))

    def test_add_additional_interface_properties_adds_mac_address(self):
        interface = {}
        _add_additional_interface_properties(
            interface, "link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff")
        self.assertThat(interface, Equals({'mac': '80:fa:5c:0d:43:5e'}))

    def test_add_additional_interface_properties_ignores_loopback_mac(self):
        interface = {}
        _add_additional_interface_properties(
            interface, "link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00")
        self.assertThat(interface, Equals({}))

    def test_parse_interface_definition_extracts_ifindex(self):
        interface = _parse_interface_definition(
            "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500")
        self.assertThat(interface['index'], Equals(2))

    def test_parse_interface_definition_extracts_ifname(self):
        interface = _parse_interface_definition(
            "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500")
        self.assertThat(interface['name'], Equals('eth0'))

    def test_parse_interface_definition_extracts_flags(self):
        interface = _parse_interface_definition(
            "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500")
        self.assertThat(interface['flags'], Equals(
            {'LOWER_UP', 'UP', 'MULTICAST', 'BROADCAST'}))

    def test_parse_interface_definition_tolerates_empty_flags(self):
        interface = _parse_interface_definition(
            "2: eth0: <> mtu 1500")
        self.assertThat(interface['flags'], Equals(set()))

    def test_parse_interface_definition_extracts_settings(self):
        interface = _parse_interface_definition(
            "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500")
        self.assertThat(interface['settings'], Equals(
            {'mtu': '1500'}))

    def test_parse_interface_definition_malformed_line_raises_valueerror(self):
        with ExpectedException(ValueError):
            _parse_interface_definition("2: eth0")

    def test_parse_interface_definition_regex_failure_raises_valueerror(self):
        with ExpectedException(ValueError):
            _parse_interface_definition("2: eth0: ")


class TestParseIPLink(MAASTestCase):

    def test_ignores_whitespace_lines(self):
        testdata = dedent("""

        1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN \
mode DEFAULT group default


            link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00

        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000

            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff

        """)
        ip_link = parse_ip_link(testdata)
        # Sanity check to ensure some data exists
        self.assertIsNotNone(ip_link.get('lo'))
        self.assertIsNotNone(ip_link.get('eth0'))
        self.assertIsNotNone(ip_link['eth0'].get('mac'))

    def test_parses_ifindex(self):
        testdata = dedent("""
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
        """)
        ip_link = parse_ip_link(testdata)
        self.assertEquals(2, ip_link['eth0']['index'])

    def test_parses_name(self):
        testdata = dedent("""
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
        """)
        ip_link = parse_ip_link(testdata)
        self.assertEquals('eth0', ip_link['eth0']['name'])

    def test_parses_mac(self):
        testdata = dedent("""
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
        """)
        ip_link = parse_ip_link(testdata)
        self.assertEquals('80:fa:5c:0d:43:5e', ip_link['eth0']['mac'])

    def test_parses_flags(self):
        testdata = dedent("""
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
        """)
        ip_link = parse_ip_link(testdata)
        flags = ip_link['eth0'].get('flags')
        self.assertIsNotNone(flags)
        self.assertThat(flags, Equals({
            'BROADCAST', 'MULTICAST', 'UP', 'LOWER_UP'
        }))

    def test_parses_settings(self):
        testdata = dedent("""
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
        """)
        ip_link = parse_ip_link(testdata)
        settings = ip_link['eth0'].get('settings')
        self.assertIsNotNone(settings)
        self.assertThat(settings, Equals({
            'mtu': '1500',
            'qdisc': 'pfifo_fast',
            'state': 'UP',
            'mode': 'DEFAULT',
            'group': 'default',
            'qlen': '1000',

        }))

    def test_parses_multiple_interfaces(self):
        testdata = dedent("""
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
        3: eth1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP \
mode DORMANT group default qlen 1000
            link/ether 48:51:bb:7a:d5:e2 brd ff:ff:ff:ff:ff:ff
        """)
        ip_link = parse_ip_link(testdata)
        self.assertEquals(2, ip_link['eth0']['index'])
        self.assertEquals('80:fa:5c:0d:43:5e', ip_link['eth0']['mac'])
        self.assertEquals(3, ip_link['eth1']['index'])
        self.assertEquals('48:51:bb:7a:d5:e2', ip_link['eth1']['mac'])
