# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import json
import os
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from textwrap import dedent

import netifaces

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import ipaddr as ipaddr_module
from provisioningserver.utils.ipaddr import (
    _annotate_with_proc_net_bonding_original_macs,
    _update_interface_type,
    get_ip_addr,
    get_mac_addresses,
    get_machine_default_gateway_ip,
)
from provisioningserver.utils.tests.test_lxd import SAMPLE_LXD_NETWORKS


class FakeSysProcTestCase(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.path_sys_net = Path(mkdtemp("maas-unit-tests.sys-class-net"))
        self.path_proc_net = Path(mkdtemp("maas-unit-tests.proc-net"))
        (self.path_proc_net / "vlan").mkdir()
        (self.path_proc_net / "bonding").mkdir()

    def tearDown(self):
        super().tearDown()
        rmtree(self.path_sys_net)
        rmtree(self.path_proc_net)

    def createInterfaceType(
        self,
        ifname,
        iftype=1,
        is_wireless=False,
        is_physical=False,
        is_tunnel=False,
    ):
        ifdir = self.path_sys_net / ifname
        ifdir.mkdir()
        type_file = ifdir / "type"
        type_file.write_text(f"{iftype}\n")
        if is_physical or is_wireless:
            device_real = ifdir / "device.real"
            device_real.mkdir()
            (ifdir / "device").symlink_to(device_real)
        if is_wireless:
            (ifdir / "device" / "ieee80211").mkdir()
        if is_tunnel:
            (ifdir / "tun_flags").touch()


class TestAnnotateWithProcNetBondingOriginalMacs(FakeSysProcTestCase):
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
        proc_net_bonding_bond0 = self.path_proc_net / "bonding" / "bond0"
        proc_net_bonding_bond0.write_text(testdata)
        interfaces = {
            "ens3": {"mac": "00:01:02:03:04:05"},
            "ens11": {"mac": "01:02:03:04:05:06"},
        }
        _annotate_with_proc_net_bonding_original_macs(
            interfaces, proc_net=self.path_proc_net
        )
        self.assertEqual(
            {
                "ens3": {"mac": "52:54:00:13:0e:6f"},
                "ens11": {"mac": "52:54:00:ea:1c:fc"},
            },
            interfaces,
        )

    def test_ignores_missing_proc_net_bonding(self):
        os.rmdir(os.path.join(self.path_proc_net, "bonding"))
        interfaces = {
            "ens3": {"mac": "00:01:02:03:04:05"},
            "ens11": {"mac": "01:02:03:04:05:06"},
        }
        _annotate_with_proc_net_bonding_original_macs(
            interfaces, proc_net=self.path_proc_net
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
        self.patch(ipaddr_module, "running_in_snap").return_value = False
        self.patch(
            ipaddr_module, "_get_resources_bin_path"
        ).return_value = "/path/to/amd64"
        patch_call_and_check = self.patch(ipaddr_module, "call_and_check")
        patch_call_and_check.return_value = json.dumps(
            {"networks": SAMPLE_LXD_NETWORKS}
        )
        # all interfaces from binary output are included in result
        self.assertCountEqual(SAMPLE_LXD_NETWORKS, get_ip_addr())
        patch_call_and_check.assert_called_once_with(
            ["sudo", "/path/to/amd64"]
        )

    def test_no_use_sudo_in_snap(self):
        self.patch(
            ipaddr_module, "_get_resources_bin_path"
        ).return_value = "/path/to/amd64"
        patch_call_and_check = self.patch(ipaddr_module, "call_and_check")
        patch_call_and_check.return_value = json.dumps(
            {"networks": SAMPLE_LXD_NETWORKS}
        )
        self.patch(ipaddr_module, "running_in_snap").return_value = True
        get_ip_addr()
        patch_call_and_check.assert_called_once_with(["/path/to/amd64"])

    def test_get_mac_addresses_returns_all_mac_addresses(self):
        mac_addresses = []
        results = {}
        for _ in range(3):
            mac = factory.make_mac_address()
            mac_addresses.append(mac)
            results[factory.make_name("eth")] = {"mac": mac}
        results[factory.make_name("eth")] = {"mac": ""}
        patch_get_ip_addr = self.patch(ipaddr_module, "get_ip_addr")
        patch_get_ip_addr.return_value = results
        observed = get_mac_addresses()
        self.assertCountEqual(mac_addresses, observed)

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
        self.assertCountEqual(mac_addresses, observed)

    def test_get_mac_addresses_skips_ipoib_mac_addresses(self):
        mac_addresses = []
        results = {}
        for _ in range(3):
            mac = factory.make_mac_address()
            mac_addresses.append(mac)
            results[factory.make_name("eth")] = {"mac": mac}
        results[factory.make_name("ibp")] = {
            "mac": "a0:00:02:20:fe:80:00:00:00:00:00:00:e4:1d:2d:03:00:4f:06:e1"
        }
        self.patch(ipaddr_module, "get_ip_addr").return_value = results
        observed = get_mac_addresses()
        self.assertCountEqual(mac_addresses, observed)


class TestUpdateInterfaceType(FakeSysProcTestCase):
    def test_ipip(self):
        networks = {
            "if0": {
                "addresses": [],
                "hwaddr": "00:00:00:00:00:01",
                "state": "up",
                "type": "broadcast",
                "bond": None,
                "bridge": None,
                "vlan": None,
            },
        }
        self.createInterfaceType("if0", 768)
        ifaces = ipaddr_module.parse_lxd_networks(networks)
        _update_interface_type(ifaces, sys_class_net=self.path_sys_net)
        self.assertEqual(ifaces["if0"]["type"], "ipip")

    def test_tunnel(self):
        networks = {
            "if0": {
                "addresses": [],
                "hwaddr": "00:00:00:00:00:01",
                "state": "up",
                "type": "broadcast",
                "bond": None,
                "bridge": None,
                "vlan": None,
            },
        }
        self.createInterfaceType("if0", is_tunnel=True)
        ifaces = ipaddr_module.parse_lxd_networks(networks)
        _update_interface_type(ifaces, sys_class_net=self.path_sys_net)
        self.assertEqual(ifaces["if0"]["type"], "tunnel")

    def test_physical(self):
        networks = {
            "if0": {
                "addresses": [],
                "hwaddr": "00:00:00:00:00:01",
                "state": "up",
                "type": "broadcast",
                "bond": None,
                "bridge": None,
                "vlan": None,
            },
        }
        self.createInterfaceType("if0", is_physical=True)
        ifaces = ipaddr_module.parse_lxd_networks(networks)
        _update_interface_type(ifaces, sys_class_net=self.path_sys_net)
        self.assertEqual(ifaces["if0"]["type"], "physical")

    def test_wireless(self):
        networks = {
            "if0": {
                "addresses": [],
                "hwaddr": "00:00:00:00:00:01",
                "state": "up",
                "type": "broadcast",
                "bond": None,
                "bridge": None,
                "vlan": None,
            },
        }
        self.createInterfaceType("if0", is_wireless=True)
        ifaces = ipaddr_module.parse_lxd_networks(networks)
        _update_interface_type(ifaces, sys_class_net=self.path_sys_net)
        self.assertEqual(ifaces["if0"]["type"], "wireless")

    def test_ethernet(self):
        networks = {
            "if0": {
                "addresses": [],
                "hwaddr": "00:00:00:00:00:01",
                "state": "up",
                "type": "broadcast",
                "bond": None,
                "bridge": None,
                "vlan": None,
            },
        }
        self.createInterfaceType("if0")
        ifaces = ipaddr_module.parse_lxd_networks(networks)
        _update_interface_type(ifaces, sys_class_net=self.path_sys_net)
        self.assertEqual(ifaces["if0"]["type"], "ethernet")

    def test_unknown(self):
        networks = {
            "if0": {
                "addresses": [],
                "hwaddr": "00:00:00:00:00:01",
                "state": "up",
                "type": "broadcast",
                "bond": None,
                "bridge": None,
                "vlan": None,
            },
        }
        self.createInterfaceType("if0", 123456)
        ifaces = ipaddr_module.parse_lxd_networks(networks)
        _update_interface_type(ifaces, sys_class_net=self.path_sys_net)
        self.assertEqual(ifaces["if0"]["type"], "unknown-123456")


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
