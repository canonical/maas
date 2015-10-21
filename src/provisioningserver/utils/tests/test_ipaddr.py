# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test parser for 'ip addr show'."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import json
import os
from shutil import rmtree
from subprocess import check_output
from tempfile import mkdtemp
from textwrap import dedent

from maastesting.testcase import MAASTestCase
from provisioningserver.network import filter_likely_unmanaged_networks
from provisioningserver.utils.ipaddr import (
    _add_additional_interface_properties,
    _get_settings_dict,
    _parse_interface_definition,
    annotate_with_driver_information,
    get_interface_type,
    parse_ip_addr,
)
from testtools import ExpectedException
from testtools.matchers import (
    Contains,
    Equals,
)


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
        self.assertThat(set(interface['flags']), Equals(
            {'LOWER_UP', 'UP', 'MULTICAST', 'BROADCAST'}))

    def test_parse_interface_definition_tolerates_empty_flags(self):
        interface = _parse_interface_definition(
            "2: eth0: <> mtu 1500")
        self.assertThat(set(interface['flags']), Equals(set()))

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


class TestParseIPAddr(MAASTestCase):

    def test_ignores_whitespace_lines(self):
        testdata = dedent("""

        1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN \
mode DEFAULT group default


            link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00

            inet 127.0.0.1/8 scope host lo
                valid_lft forever preferred_lft forever

            inet6 ::1/128 scope host
                valid_lft forever preferred_lft forever

        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000

            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff

        """)
        ip_link = parse_ip_addr(testdata)
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
        ip_link = parse_ip_addr(testdata)
        self.assertEquals(2, ip_link['eth0']['index'])

    def test_parses_name(self):
        testdata = dedent("""
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
        """)
        ip_link = parse_ip_addr(testdata)
        self.assertEquals('eth0', ip_link['eth0']['name'])

    def test_parses_mac(self):
        testdata = dedent("""
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
        """)
        ip_link = parse_ip_addr(testdata)
        self.assertEquals('80:fa:5c:0d:43:5e', ip_link['eth0']['mac'])

    def test_parses_flags(self):
        testdata = dedent("""
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
        """)
        ip_link = parse_ip_addr(testdata)
        flags = ip_link['eth0'].get('flags')
        self.assertIsNotNone(flags)
        self.assertThat(set(flags), Equals({
            'BROADCAST', 'MULTICAST', 'UP', 'LOWER_UP'
        }))

    def test_parses_settings(self):
        testdata = dedent("""
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
        """)
        ip_link = parse_ip_addr(testdata)
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

    def test_parses_inet(self):
        testdata = dedent("""
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
            inet 192.168.0.3/24 brd 192.168.0.255 scope global eth0
                valid_lft forever preferred_lft forever
            inet6 fe80::3e97:eff:fe0e:56dc/64 scope link
                valid_lft forever preferred_lft forever
        """)
        ip_link = parse_ip_addr(testdata)
        inet = ip_link['eth0'].get('inet')
        self.assertEqual(['192.168.0.3/24'], inet)

    def test_parses_multiple_inet(self):
        testdata = dedent("""
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
            inet 192.168.0.3/24 brd 192.168.0.255 scope global eth0
                valid_lft forever preferred_lft forever
            inet 192.168.0.4/24 brd 192.168.0.255 scope global eth0
                valid_lft forever preferred_lft forever
            inet6 fe80::3e97:eff:fe0e:56dc/64 scope link
                valid_lft forever preferred_lft forever
        """)
        ip_link = parse_ip_addr(testdata)
        inet = ip_link['eth0'].get('inet')
        self.assertEqual(['192.168.0.3/24', '192.168.0.4/24'], inet)

    def test_parses_inet6(self):
        testdata = dedent("""
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
            inet 192.168.0.3/24 brd 192.168.0.255 scope global eth0
                valid_lft forever preferred_lft forever
            inet6 2001:db8:85a3:8d3:1319:8a2e:370:7348/64 scope link
                valid_lft forever preferred_lft forever
        """)
        ip_link = parse_ip_addr(testdata)
        inet = ip_link['eth0'].get('inet6')
        self.assertEqual(['2001:db8:85a3:8d3:1319:8a2e:370:7348/64'], inet)

    def test_skips_ipv4_link_local(self):
        testdata = dedent("""
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
            inet 169.254.1.4/16 brd 192.168.0.255 scope global eth0
                valid_lft forever preferred_lft forever
        """)
        ip_link = parse_ip_addr(testdata)
        self.assertIsNone(ip_link['eth0'].get('inet'))

    def test_skips_ipv6_link_local(self):
        testdata = dedent("""
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
            inet6 fe80::3e97:eff:fe0e:56dc/64 scope link
                valid_lft forever preferred_lft forever
        """)
        ip_link = parse_ip_addr(testdata)
        self.assertIsNone(ip_link['eth0'].get('inet6'))

    def test_parses_multiple_interfaces(self):
        testdata = dedent("""
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
            inet 192.168.0.3/24 brd 192.168.0.255 scope global eth0
                valid_lft forever preferred_lft forever
            inet6 2001:db8:85a3:8d3:1319:8a2e:370:7350/64 scope link
                valid_lft forever preferred_lft forever
        3: eth1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP \
mode DORMANT group default qlen 1000
            link/ether 48:51:bb:7a:d5:e2 brd ff:ff:ff:ff:ff:ff
            inet 192.168.0.5/24 brd 192.168.0.255 scope global eth1
                valid_lft forever preferred_lft forever
            inet6 2001:db8:85a3:8d3:1319:8a2e:370:7348/64 scope link
                valid_lft forever preferred_lft forever
            inet6 2620:1:260::1/64 scope global
                valid_lft forever preferred_lft forever
        """)
        ip_link = parse_ip_addr(testdata)
        self.assertEquals(2, ip_link['eth0']['index'])
        self.assertEquals('80:fa:5c:0d:43:5e', ip_link['eth0']['mac'])
        self.assertEquals(['192.168.0.3/24'], ip_link['eth0']['inet'])
        self.assertEquals(
            ['2001:db8:85a3:8d3:1319:8a2e:370:7350/64'],
            ip_link['eth0']['inet6'])
        self.assertEquals(3, ip_link['eth1']['index'])
        self.assertEquals('48:51:bb:7a:d5:e2', ip_link['eth1']['mac'])
        self.assertEquals(['192.168.0.5/24'], ip_link['eth1']['inet'])
        self.assertEquals(
            ['2001:db8:85a3:8d3:1319:8a2e:370:7348/64', '2620:1:260::1/64'],
            ip_link['eth1']['inet6'])


class TestGetInterfaceType(MAASTestCase):

    def setUp(self):
        super(TestGetInterfaceType, self).setUp()
        self.tmp_sys_net = mkdtemp('maas-unit-tests.sys-class-net')
        self.tmp_proc_net_vlan = mkdtemp('maas-unit-tests.proc-net-vlan')

    def tearDown(self):
        super(TestGetInterfaceType, self).tearDown()
        rmtree(self.tmp_sys_net)
        rmtree(self.tmp_proc_net_vlan)

    def createInterfaceType(
            self, ifname, iftype, is_bridge=False, is_vlan=False,
            is_bond=False, is_wireless=False, is_physical=False):
        ifdir = os.path.join(self.tmp_sys_net, ifname)
        os.mkdir(ifdir)
        type_file = os.path.join(ifdir, 'type')
        f = open(type_file, 'w')
        f.write(b"%d\n" % iftype)
        f.close()
        if is_bridge:
            os.mkdir(os.path.join(ifdir, 'bridge'))
        if is_vlan:
            f = open(os.path.join(self.tmp_proc_net_vlan, ifname), 'w')
            f.close()
        if is_bond:
            os.mkdir(os.path.join(ifdir, 'bonding'))
        if is_physical or is_wireless:
            os.mkdir(os.path.join(ifdir, 'device'))
            os.mkdir(os.path.join(ifdir, 'device', 'driver'))
            # Note: the symlink here doesn't actually need to resolve
            # to a real file.
            os.symlink(
                os.path.join('..', 'driver_module_name'),
                os.path.join(ifdir, 'device', 'driver', 'module'))
        if is_wireless:
            os.mkdir(os.path.join(ifdir, 'device', 'ieee80211'))

    def createIpIpInterface(self, ifname):
        self.createInterfaceType(ifname, 768)

    def createLoopbackInterface(self, ifname):
        self.createInterfaceType(ifname, 772)

    def createEthernetInterface(self, ifname, **kwargs):
        self.createInterfaceType(ifname, 1, **kwargs)

    def test__identifies_missing_interface(self):
        self.assertThat(get_interface_type(
            'eth0', sys_class_net=self.tmp_sys_net),
            Equals('missing')
        )

    def test__identifies_bridge_interface(self):
        self.createEthernetInterface('br0', is_bridge=True)
        self.assertThat(get_interface_type(
            'br0', sys_class_net=self.tmp_sys_net,
            proc_net_vlan=self.tmp_proc_net_vlan),
            Equals('ethernet.bridge')
        )

    def test__identifies_bond_interface(self):
        self.createEthernetInterface('bond0', is_bond=True)
        self.assertThat(get_interface_type(
            'bond0', sys_class_net=self.tmp_sys_net,
            proc_net_vlan=self.tmp_proc_net_vlan),
            Equals('ethernet.bond')
        )

    def test__identifies_vlan_interface(self):
        self.createEthernetInterface('vlan42', is_vlan=True)
        self.assertThat(get_interface_type(
            'vlan42', sys_class_net=self.tmp_sys_net,
            proc_net_vlan=self.tmp_proc_net_vlan),
            Equals('ethernet.vlan')
        )

    def test__identifies_physical_ethernet_interface(self):
        self.createEthernetInterface('eth0', is_physical=True)
        self.assertThat(get_interface_type(
            'eth0', sys_class_net=self.tmp_sys_net,
            proc_net_vlan=self.tmp_proc_net_vlan),
            Equals('ethernet.physical')
        )

    def test__identifies_wireless_ethernet_interface(self):
        self.createEthernetInterface('wlan0', is_wireless=True)
        self.assertThat(get_interface_type(
            'wlan0', sys_class_net=self.tmp_sys_net,
            proc_net_vlan=self.tmp_proc_net_vlan),
            Equals('ethernet.wireless')
        )

    def test__identifies_other_ethernet_interface(self):
        self.createEthernetInterface('eth1')
        self.assertThat(get_interface_type(
            'eth1', sys_class_net=self.tmp_sys_net,
            proc_net_vlan=self.tmp_proc_net_vlan),
            Equals('ethernet')
        )

    def test__identifies_loopback_interface(self):
        self.createLoopbackInterface('lo')
        self.assertThat(get_interface_type(
            'lo', sys_class_net=self.tmp_sys_net,
            proc_net_vlan=self.tmp_proc_net_vlan),
            Equals('loopback')
        )

    def test__identifies_ipip_interface(self):
        self.createIpIpInterface('tun0')
        self.assertThat(get_interface_type(
            'tun0', sys_class_net=self.tmp_sys_net,
            proc_net_vlan=self.tmp_proc_net_vlan),
            Equals('ipip')
        )

    def test__unknown_interfaces_type_includes_id(self):
        self.createInterfaceType('avian0', 1149)
        self.assertThat(get_interface_type(
            'avian0', sys_class_net=self.tmp_sys_net,
            proc_net_vlan=self.tmp_proc_net_vlan),
            Equals('unknown-1149')
        )


class TestAnnotateWithDriverInformation(MAASTestCase):

    def test__populates_interface_type_for_each_interface(self):
        # Note: this is more of an end-to-end test, since we call
        # "/sbin/ip addr" on the host running the tests. This is necessary
        # because we don't have dependency injection for the directory names
        # all the way through.
        ip_addr_output = check_output(['/sbin/ip', 'addr'])
        interfaces = parse_ip_addr(ip_addr_output)
        interfaces_with_types = annotate_with_driver_information(interfaces)
        for name in interfaces:
            self.assertThat(interfaces_with_types[name], Contains('type'))


class TestFilterLikelyUnmanagedNetworks(MAASTestCase):

    def test__filters_based_on_name_by_default(self):
        input_networks = [
            {"interface": "em0"},
            {"interface": "eth0"},
            {"interface": "vlan0"},
            {"interface": "bond0"},
            {"interface": "br0"},
            {"interface": "wlan0"},
            {"interface": "avian0"},
        ]
        actual_networks = filter_likely_unmanaged_networks(input_networks)
        expected_networks = [
            {"interface": "em0"},
            {"interface": "eth0"},
            {"interface": "vlan0"},
            {"interface": "bond0"},
        ]
        self.assertThat(actual_networks, Equals(expected_networks))

    def test__filters_based_on_json_data_if_available(self):
        input_networks = [
            {"interface": "em0"},
            {"interface": "eth0"},
            {"interface": "vlan0"},
            {"interface": "bond0"},
            {"interface": "avian0"},
            {"interface": "br0"},
            {"interface": "wlan0"},
        ]
        # Wow, these are some poorly named interfaces.
        # Though I guess technically an avian carrier is a physical interface.
        input_json = {
            "avian0": {"type": "ethernet.physical"},
            "br0": {"type": "ethernet.vlan"},
            "wlan0": {"type": "ethernet.bond"}
        }
        actual_networks = filter_likely_unmanaged_networks(
            input_networks, json.dumps(input_json))
        expected_networks = [
            {"interface": "avian0"},
            {"interface": "br0"},
            {"interface": "wlan0"},
        ]
        self.assertThat(actual_networks, Equals(expected_networks))

    def test__falls_back_to_names_if_no_interfaces_found(self):
        input_networks = [
            {"interface": "em0"},
            {"interface": "eth0"},
            {"interface": "vlan0"},
            {"interface": "bond0"},
            {"interface": "br0"},
            {"interface": "wlan0"},
            {"interface": "avian0"},
        ]
        input_json = {
        }
        actual_networks = filter_likely_unmanaged_networks(
            input_networks, json.dumps(input_json))
        expected_networks = [
            {"interface": "em0"},
            {"interface": "eth0"},
            {"interface": "vlan0"},
            {"interface": "bond0"},
        ]
        self.assertThat(actual_networks, Equals(expected_networks))
