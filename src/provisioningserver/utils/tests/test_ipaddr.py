# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test parser for 'ip addr show'."""


import os
from shutil import rmtree
from subprocess import check_output
from tempfile import mkdtemp
from textwrap import dedent
from unittest.mock import sentinel

import netifaces
from testtools import ExpectedException
from testtools.matchers import Contains, Equals, Not

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import ipaddr as ipaddr_module
from provisioningserver.utils.ipaddr import (
    _add_additional_interface_properties,
    _parse_interface_definition,
    annotate_with_driver_information,
    annotate_with_proc_net_bonding_original_macs,
    get_bonded_interfaces,
    get_interface_type,
    get_ip_addr,
    get_mac_addresses,
    get_machine_default_gateway_ip,
    get_settings_dict,
    parse_ip_addr,
)


class TestHelperFunctions(MAASTestCase):
    def testget_settings_dict_ignores_empty_settings_string(self):
        settings = get_settings_dict("")
        self.assertEqual({}, settings)

    def testget_settings_dict_handles_odd_number_of_tokens(self):
        self.assertThat(get_settings_dict("mtu"), Equals({}))
        self.assertThat(
            get_settings_dict("mtu 1500 qdisc"), Equals({"mtu": "1500"})
        )

    def testget_settings_dict_creates_correct_dictionary(self):
        settings = get_settings_dict("mtu 1073741824 state AWESOME")
        self.assertThat(
            settings, Equals({"mtu": "1073741824", "state": "AWESOME"})
        )

    def testget_settings_dict_ignores_whitespace(self):
        settings = get_settings_dict("    mtu   1073741824  state  AWESOME  ")
        self.assertThat(
            settings, Equals({"mtu": "1073741824", "state": "AWESOME"})
        )

    def test_add_additional_interface_properties_adds_mac_address(self):
        interface = {}
        _add_additional_interface_properties(
            interface, "link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff"
        )
        self.assertThat(interface, Equals({"mac": "80:fa:5c:0d:43:5e"}))

    def test_add_additional_interface_properties_ignores_loopback_mac(self):
        interface = {}
        _add_additional_interface_properties(
            interface, "link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00"
        )
        self.assertThat(interface, Equals({}))

    def test_parse_interface_definition_extracts_ifname(self):
        interface = _parse_interface_definition(
            "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500"
        )
        self.assertThat(interface["name"], Equals("eth0"))

    def test_parse_interface_definition_extracts_flags(self):
        interface = _parse_interface_definition(
            "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500"
        )
        self.assertThat(
            set(interface["flags"]),
            Equals({"LOWER_UP", "UP", "MULTICAST", "BROADCAST"}),
        )

    def test_parse_interface_definition_tolerates_empty_flags(self):
        interface = _parse_interface_definition("2: eth0: <> mtu 1500")
        self.assertThat(set(interface["flags"]), Equals(set()))

    def test_parse_interface_definition_extracts_settings(self):
        interface = _parse_interface_definition(
            "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500"
        )
        self.assertThat(interface["settings"], Equals({"mtu": "1500"}))

    def test_parse_interface_definition_malformed_line_raises_valueerror(self):
        with ExpectedException(ValueError):
            _parse_interface_definition("2: eth0")

    def test_parse_interface_definition_regex_failure_raises_valueerror(self):
        with ExpectedException(ValueError):
            _parse_interface_definition("2: eth0: ")


class TestParseIPAddr(MAASTestCase):
    def test_ignores_whitespace_lines(self):
        testdata = dedent(
            """

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

        """
        )
        ip_link = parse_ip_addr(testdata)
        # Sanity check to ensure some data exists
        self.assertIsNotNone(ip_link.get("lo"))
        self.assertIsNotNone(ip_link.get("eth0"))
        self.assertIsNotNone(ip_link["eth0"].get("mac"))

    def test_parses_name(self):
        testdata = dedent(
            """
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
        """
        )
        ip_link = parse_ip_addr(testdata)
        self.assertEqual("eth0", ip_link["eth0"]["name"])

    def test_parses_mac(self):
        testdata = dedent(
            """
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
        """
        )
        ip_link = parse_ip_addr(testdata)
        self.assertEqual("80:fa:5c:0d:43:5e", ip_link["eth0"]["mac"])

    def test_parses_flags(self):
        testdata = dedent(
            """
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
        """
        )
        ip_link = parse_ip_addr(testdata)
        flags = ip_link["eth0"].get("flags")
        self.assertIsNotNone(flags)
        self.assertThat(
            set(flags), Equals({"BROADCAST", "MULTICAST", "UP", "LOWER_UP"})
        )

    def test_parses_settings(self):
        testdata = dedent(
            """
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
        """
        )
        ip_link = parse_ip_addr(testdata)
        settings = ip_link["eth0"].get("settings")
        self.assertIsNotNone(settings)
        self.assertThat(
            settings,
            Equals(
                {
                    "mtu": "1500",
                    "qdisc": "pfifo_fast",
                    "state": "UP",
                    "mode": "DEFAULT",
                    "group": "default",
                    "qlen": "1000",
                }
            ),
        )

    def test_parses_inet(self):
        testdata = dedent(
            """
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
            inet 192.168.0.3/24 brd 192.168.0.255 scope global eth0
                valid_lft forever preferred_lft forever
            inet6 fe80::3e97:eff:fe0e:56dc/64 scope link
                valid_lft forever preferred_lft forever
        """
        )
        ip_link = parse_ip_addr(testdata)
        inet = ip_link["eth0"].get("inet")
        self.assertEqual(["192.168.0.3/24"], inet)

    def test_parses_multiple_inet(self):
        testdata = dedent(
            """
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
            inet 192.168.0.3/24 brd 192.168.0.255 scope global eth0
                valid_lft forever preferred_lft forever
            inet 192.168.0.4/24 brd 192.168.0.255 scope global eth0
                valid_lft forever preferred_lft forever
            inet6 fe80::3e97:eff:fe0e:56dc/64 scope link
                valid_lft forever preferred_lft forever
        """
        )
        ip_link = parse_ip_addr(testdata)
        inet = ip_link["eth0"].get("inet")
        self.assertEqual(["192.168.0.3/24", "192.168.0.4/24"], inet)

    def test_parses_inet6(self):
        testdata = dedent(
            """
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
            inet 192.168.0.3/24 brd 192.168.0.255 scope global eth0
                valid_lft forever preferred_lft forever
            inet6 2001:db8:85a3:8d3:1319:8a2e:370:7348/64 scope link
                valid_lft forever preferred_lft forever
        """
        )
        ip_link = parse_ip_addr(testdata)
        inet = ip_link["eth0"].get("inet6")
        self.assertEqual(["2001:db8:85a3:8d3:1319:8a2e:370:7348/64"], inet)

    def test_skips_ipv4_link_local(self):
        testdata = dedent(
            """
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
            inet 169.254.1.4/16 brd 192.168.0.255 scope global eth0
                valid_lft forever preferred_lft forever
        """
        )
        ip_link = parse_ip_addr(testdata)
        self.assertIsNone(ip_link["eth0"].get("inet"))

    def test_skips_ipv6_link_local(self):
        testdata = dedent(
            """
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
            inet6 fe80::3e97:eff:fe0e:56dc/64 scope link
                valid_lft forever preferred_lft forever
        """
        )
        ip_link = parse_ip_addr(testdata)
        self.assertIsNone(ip_link["eth0"].get("inet6"))

    def test_handles_wlan_flags(self):
        testdata = dedent(
            """
        2: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
            inet6 fe80::3e97:eff:fe0e:56dc/64 scope link
                valid_lft forever preferred_lft forever
            inet 192.168.2.112/24 brd 192.168.2.255 scope global dynamic wlan0
                valid_lft forever preferred_lft forever
        """
        )
        ip_link = parse_ip_addr(testdata)
        inet = ip_link["wlan0"].get("inet")
        self.assertEqual(["192.168.2.112/24"], inet)

    def test_parses_multiple_interfaces(self):
        testdata = dedent(
            """
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
            inet6 2001:db8:85a3:8d3:1319:8a2e:370:3645/64 scope global dynamic
                valid_lft forever preferred_lft forever
            inet6 2001:db8:85a3:8d3::1111/64 scope global tentative dynamic
                valid_lft forever preferred_lft forever
            inet6 2620:1:260::1/64 scope global
                valid_lft forever preferred_lft forever
        """
        )
        ip_link = parse_ip_addr(testdata)
        self.assertEqual("80:fa:5c:0d:43:5e", ip_link["eth0"]["mac"])
        self.assertEqual(["192.168.0.3/24"], ip_link["eth0"]["inet"])
        self.assertEqual(
            ["2001:db8:85a3:8d3:1319:8a2e:370:7350/64"],
            ip_link["eth0"]["inet6"],
        )
        self.assertEqual("48:51:bb:7a:d5:e2", ip_link["eth1"]["mac"])
        self.assertEqual(["192.168.0.5/24"], ip_link["eth1"]["inet"])
        self.assertEqual(
            [
                "2001:db8:85a3:8d3:1319:8a2e:370:7348/64",
                "2001:db8:85a3:8d3:1319:8a2e:370:3645/64",
                "2001:db8:85a3:8d3::1111/64",
                "2620:1:260::1/64",
            ],
            ip_link["eth1"]["inet6"],
        )

    def test_parses_xenial_interfaces(self):
        testdata = dedent(
            """
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN \
group default
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host
       valid_lft forever preferred_lft forever
2: ens3: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP \
group default qlen 1000
    link/ether 52:54:00:2d:39:49 brd ff:ff:ff:ff:ff:ff
    inet 172.16.100.108/24 brd 172.16.100.255 scope global ens3
       valid_lft forever preferred_lft forever
    inet6 fe80::5054:ff:fe2d:3949/64 scope link
       valid_lft forever preferred_lft forever
3: ens10: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN \
group default qlen 1000
    link/ether 52:54:00:e5:c6:6b brd ff:ff:ff:ff:ff:ff
4: ens11: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN \
group default qlen 1000
    link/ether 52:54:00:ed:9f:9d brd ff:ff:ff:ff:ff:ff
       """
        )
        ip_link = parse_ip_addr(testdata)
        self.assertEqual("52:54:00:2d:39:49", ip_link["ens3"]["mac"])
        self.assertEqual(["172.16.100.108/24"], ip_link["ens3"]["inet"])
        self.assertEqual("52:54:00:e5:c6:6b", ip_link["ens10"]["mac"])
        self.assertThat(ip_link["ens10"], Not(Contains("inet")))
        self.assertEqual("52:54:00:ed:9f:9d", ip_link["ens11"]["mac"])
        self.assertThat(ip_link["ens11"], Not(Contains("inet")))


class FakeSysProcTestCase(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.tmp_sys_net = mkdtemp("maas-unit-tests.sys-class-net")
        self.tmp_proc_net = mkdtemp("maas-unit-tests.proc-net")
        os.mkdir(os.path.join(self.tmp_proc_net, "vlan"))
        os.mkdir(os.path.join(self.tmp_proc_net, "bonding"))

    def tearDown(self):
        super().tearDown()
        rmtree(self.tmp_sys_net)
        rmtree(self.tmp_proc_net)

    def createInterfaceType(
        self,
        ifname,
        iftype,
        is_bridge=False,
        is_vlan=False,
        is_bond=False,
        is_wireless=False,
        is_physical=False,
        is_tunnel=False,
        bonded_interfaces=None,
    ):
        ifdir = os.path.join(self.tmp_sys_net, ifname)
        os.mkdir(ifdir)
        type_file = os.path.join(ifdir, "type")
        with open(type_file, "w", encoding="utf-8") as f:
            f.write("%d\n" % iftype)
        if is_bridge:
            os.mkdir(os.path.join(ifdir, "bridge"))
        if is_tunnel:
            with open(os.path.join(ifdir, "tun_flags"), "w"):
                pass  # Just touch.
        if is_vlan:
            with open(os.path.join(self.tmp_proc_net, "vlan", ifname), "w"):
                pass  # Just touch.
        if is_bond:
            os.mkdir(os.path.join(ifdir, "bonding"))
            if bonded_interfaces is not None:
                filename_slaves = os.path.join(ifdir, "bonding", "slaves")
                with open(filename_slaves, "w", encoding="utf-8") as f:
                    f.write("%s\n" % " ".join(bonded_interfaces))
        if is_physical or is_wireless:
            device_real = os.path.join(ifdir, "device.real")
            os.mkdir(device_real)
            os.symlink(device_real, os.path.join(ifdir, "device"))
        if is_wireless:
            os.mkdir(os.path.join(ifdir, "device", "ieee80211"))

    def createIpIpInterface(self, ifname):
        self.createInterfaceType(ifname, 768)

    def createLoopbackInterface(self, ifname):
        self.createInterfaceType(ifname, 772)

    def createEthernetInterface(self, ifname, **kwargs):
        self.createInterfaceType(ifname, 1, **kwargs)


class TestGetInterfaceType(FakeSysProcTestCase):
    def test_identifies_missing_interface(self):
        self.assertThat(
            get_interface_type("eth0", sys_class_net=self.tmp_sys_net),
            Equals("missing"),
        )

    def test_identifies_bridge_interface(self):
        self.createEthernetInterface("br0", is_bridge=True)
        self.assertThat(
            get_interface_type(
                "br0",
                sys_class_net=self.tmp_sys_net,
                proc_net=self.tmp_proc_net,
            ),
            Equals("ethernet.bridge"),
        )

    def test_identifies_tunnel_interface(self):
        self.createEthernetInterface("vnet0", is_tunnel=True)
        self.assertThat(
            get_interface_type(
                "vnet0",
                sys_class_net=self.tmp_sys_net,
                proc_net=self.tmp_proc_net,
            ),
            Equals("ethernet.tunnel"),
        )

    def test_identifies_bond_interface(self):
        self.createEthernetInterface("bond0", is_bond=True)
        self.assertThat(
            get_interface_type(
                "bond0",
                sys_class_net=self.tmp_sys_net,
                proc_net=self.tmp_proc_net,
            ),
            Equals("ethernet.bond"),
        )

    def test_identifies_bonded_interfaces(self):
        self.createEthernetInterface(
            "bond0", is_bond=True, bonded_interfaces=["eth0", "eth1"]
        )
        self.assertThat(
            get_bonded_interfaces("bond0", sys_class_net=self.tmp_sys_net),
            Equals(["eth0", "eth1"]),
        )

    def test_identifies_vlan_interface(self):
        self.createEthernetInterface("vlan42", is_vlan=True)
        self.assertThat(
            get_interface_type(
                "vlan42",
                sys_class_net=self.tmp_sys_net,
                proc_net=self.tmp_proc_net,
            ),
            Equals("ethernet.vlan"),
        )

    def test_identifies_physical_ethernet_interface(self):
        self.createEthernetInterface("eth0", is_physical=True)
        self.assertThat(
            get_interface_type(
                "eth0",
                sys_class_net=self.tmp_sys_net,
                proc_net=self.tmp_proc_net,
            ),
            Equals("ethernet.physical"),
        )

    def test_identifies_wireless_ethernet_interface(self):
        self.createEthernetInterface("wlan0", is_wireless=True)
        self.assertThat(
            get_interface_type(
                "wlan0",
                sys_class_net=self.tmp_sys_net,
                proc_net=self.tmp_proc_net,
            ),
            Equals("ethernet.wireless"),
        )

    def test_identifies_other_ethernet_interface(self):
        self.createEthernetInterface("eth1")
        self.assertThat(
            get_interface_type(
                "eth1",
                sys_class_net=self.tmp_sys_net,
                proc_net=self.tmp_proc_net,
            ),
            Equals("ethernet"),
        )

    def test_identifies_loopback_interface(self):
        self.createLoopbackInterface("lo")
        self.assertThat(
            get_interface_type(
                "lo",
                sys_class_net=self.tmp_sys_net,
                proc_net=self.tmp_proc_net,
            ),
            Equals("loopback"),
        )

    def test_identifies_ipip_interface(self):
        self.createIpIpInterface("tun0")
        self.assertThat(
            get_interface_type(
                "tun0",
                sys_class_net=self.tmp_sys_net,
                proc_net=self.tmp_proc_net,
            ),
            Equals("ipip"),
        )

    def test_unknown_interfaces_type_includes_id(self):
        self.createInterfaceType("avian0", 1149)
        self.assertThat(
            get_interface_type(
                "avian0",
                sys_class_net=self.tmp_sys_net,
                proc_net=self.tmp_proc_net,
            ),
            Equals("unknown-1149"),
        )


class TestAnnotateWithDriverInformation(FakeSysProcTestCase):
    def test_populates_interface_type_for_each_interface(self):
        # Note: this is more of an end-to-end test, since we call
        # "/sbin/ip addr" on the host running the tests.
        ip_addr_output = check_output(["ip", "addr"])
        interfaces = parse_ip_addr(ip_addr_output)
        interfaces_with_types = annotate_with_driver_information(interfaces)
        for name in interfaces:
            iface = interfaces_with_types[name]
            self.assertThat(iface, Contains("type"))
            if iface["type"] == "ethernet.vlan":
                self.expectThat(iface, Contains("vid"))
            elif iface["type"] == "ethernet.bond":
                self.expectThat(iface, Contains("bonded_interfaces"))
            elif iface["type"] == "ethernet.bridge":
                self.expectThat(iface, Contains("bridged_interfaces"))

    def test_finds_bond_members_original_mac_addresses(self):
        testdata = dedent(
            """\
            Ethernet Channel Bonding Driver: v3.7.1 (April 27, 2011)

            Bonding Mode: fault-tolerance (active-backup)
            Primary Slave: None
            Currently Active Slave: ens11
            MII Status: up
            MII Polling Interval (ms): 100
            Up Delay (ms): 200
            Down Delay (ms): 0

            Slave Interface: ens11
            MII Status: up
            Speed: Unknown
            Duplex: Unknown
            Link Failure Count: 0
            Permanent HW addr: 52:54:00:ea:1c:fc
            Slave queue ID: 0

            Slave Interface: ens3
            MII Status: up
            Speed: Unknown
            Duplex: Unknown
            Link Failure Count: 0
            Permanent HW addr: 52:54:00:13:0e:6f
            Slave queue ID: 0
            """
        )
        proc_net_bonding_bond0 = os.path.join(
            self.tmp_proc_net, "bonding", "bond0"
        )
        with open(proc_net_bonding_bond0, mode="w") as f:
            f.write(testdata)
        interfaces = {
            "ens3": {"mac": "00:01:02:03:04:05"},
            "ens11": {"mac": "01:02:03:04:05:06"},
        }
        annotate_with_proc_net_bonding_original_macs(
            interfaces, proc_net=self.tmp_proc_net
        )
        self.assertEqual(
            {
                "ens3": {"mac": "52:54:00:13:0e:6f"},
                "ens11": {"mac": "52:54:00:ea:1c:fc"},
            },
            interfaces,
        )

    def test_ignores_missing_proc_net_bonding(self):
        os.rmdir(os.path.join(self.tmp_proc_net, "bonding"))
        interfaces = {
            "ens3": {"mac": "00:01:02:03:04:05"},
            "ens11": {"mac": "01:02:03:04:05:06"},
        }
        annotate_with_proc_net_bonding_original_macs(
            interfaces, proc_net=self.tmp_proc_net
        )
        self.assertEqual(
            {
                "ens3": {"mac": "00:01:02:03:04:05"},
                "ens11": {"mac": "01:02:03:04:05:06"},
            },
            interfaces,
        )


class TestGetIPAddr(MAASTestCase):
    """Tests for `get_ip_addr`, `get_mac_addresses`."""

    def test_get_ip_addr_calls_methods(self):
        patch_call_and_check = self.patch(ipaddr_module, "call_and_check")
        patch_call_and_check.return_value = sentinel.ip_addr_cmd
        patch_parse_ip_addr = self.patch(ipaddr_module, "parse_ip_addr")
        patch_parse_ip_addr.return_value = sentinel.parse_result
        patch_annotate_with_driver_information = self.patch(
            ipaddr_module, "annotate_with_driver_information"
        )
        patch_annotate_with_driver_information.return_value = sentinel.output
        self.assertEquals(sentinel.output, get_ip_addr())
        self.assertThat(
            patch_call_and_check, MockCalledOnceWith(["ip", "addr"])
        )
        self.assertThat(
            patch_parse_ip_addr, MockCalledOnceWith(sentinel.ip_addr_cmd)
        )
        self.assertThat(
            patch_annotate_with_driver_information,
            MockCalledOnceWith(sentinel.parse_result),
        )

    def test_get_mac_addresses_returns_all_mac_addresses(self):
        mac_addresses = []
        results = {}
        for _ in range(3):
            mac = factory.make_mac_address()
            mac_addresses.append(mac)
            results[factory.make_name("eth")] = {"mac": mac}
        results[factory.make_name("eth")] = {"mac": "00:00:00:00:00:00"}
        patch_get_ip_addr = self.patch(ipaddr_module, "get_ip_addr")
        patch_get_ip_addr.return_value = results
        observed = get_mac_addresses()
        self.assertItemsEqual(mac_addresses, observed)

    def test_get_mac_addresses_ignores_duplicates(self):
        mac_addresses = set()
        results = {}
        mac = factory.make_mac_address()
        mac_addresses.add(mac)
        for _ in range(3):
            results[factory.make_name("eth")] = {"mac": mac}
        patch_get_ip_addr = self.patch(ipaddr_module, "get_ip_addr")
        patch_get_ip_addr.return_value = results
        observed = get_mac_addresses()
        self.assertItemsEqual(mac_addresses, observed)


class TestGetMachineDefaultGatewayIP(MAASTestCase):
    def test_get_machine_default_gateway_ip_no_defaults(self):
        self.patch(netifaces, "gateways").return_value = {}
        self.assertIsNone(get_machine_default_gateway_ip())

    def test_get_machine_default_gateway_ip_returns_ipv4(self):
        gw_address = factory.make_ipv4_address()
        ipv4_address = factory.make_ipv4_address()
        iface_name = factory.make_name("eth")
        self.patch(netifaces, "gateways").return_value = {
            "default": {netifaces.AF_INET: (gw_address, iface_name)}
        }
        self.patch(netifaces, "ifaddresses").return_value = {
            netifaces.AF_INET: [{"addr": ipv4_address}]
        }
        self.assertEqual(ipv4_address, get_machine_default_gateway_ip())

    def test_get_machine_default_gateway_ip_returns_ipv6(self):
        gw_address = factory.make_ipv6_address()
        ipv6_address = factory.make_ipv6_address()
        iface_name = factory.make_name("eth")
        self.patch(netifaces, "gateways").return_value = {
            "default": {netifaces.AF_INET6: (gw_address, iface_name)}
        }
        self.patch(netifaces, "ifaddresses").return_value = {
            netifaces.AF_INET6: [{"addr": ipv6_address}]
        }
        self.assertEqual(ipv6_address, get_machine_default_gateway_ip())

    def test_get_machine_default_gateway_ip_returns_ipv4_over_ipv6(self):
        gw4_address = factory.make_ipv4_address()
        gw6_address = factory.make_ipv6_address()
        ipv4_address = factory.make_ipv4_address()
        ipv6_address = factory.make_ipv6_address()
        iface = factory.make_name("eth")
        self.patch(netifaces, "gateways").return_value = {
            "default": {
                netifaces.AF_INET: (gw4_address, iface),
                netifaces.AF_INET6: (gw6_address, iface),
            }
        }
        self.patch(netifaces, "ifaddresses").return_value = {
            netifaces.AF_INET: [{"addr": ipv4_address}],
            netifaces.AF_INET6: [{"addr": ipv6_address}],
        }
        self.assertEqual(ipv4_address, get_machine_default_gateway_ip())

    def test_get_machine_default_gateway_ip_returns_first_ip(self):
        gw_address = factory.make_ipv4_address()
        ipv4_address1 = factory.make_ipv4_address()
        ipv4_address2 = factory.make_ipv4_address()
        iface = factory.make_name("eth")
        self.patch(netifaces, "gateways").return_value = {
            "default": {netifaces.AF_INET: (gw_address, iface)}
        }
        self.patch(netifaces, "ifaddresses").return_value = {
            netifaces.AF_INET: [
                {"addr": ipv4_address1},
                {"addr": ipv4_address2},
            ]
        }
        self.assertEqual(ipv4_address1, get_machine_default_gateway_ip())
