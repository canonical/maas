# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test parser for 'ip addr show'."""


import json
import os
from shutil import rmtree
from tempfile import mkdtemp
from textwrap import dedent

import netifaces

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.refresh import get_resources_bin_path
from provisioningserver.utils import ipaddr as ipaddr_module
from provisioningserver.utils.ipaddr import (
    _annotate_with_proc_net_bonding_original_macs,
    get_ip_addr,
    get_mac_addresses,
    get_machine_default_gateway_ip,
)
from provisioningserver.utils.tests.test_lxd import SAMPLE_LXD_NETWORKS


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
        proc_net_bonding_bond0 = os.path.join(
            self.tmp_proc_net, "bonding", "bond0"
        )
        with open(proc_net_bonding_bond0, mode="w") as f:
            f.write(testdata)
        interfaces = {
            "ens3": {"mac": "00:01:02:03:04:05"},
            "ens11": {"mac": "01:02:03:04:05:06"},
        }
        _annotate_with_proc_net_bonding_original_macs(
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
        _annotate_with_proc_net_bonding_original_macs(
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
        patch_call_and_check.return_value = json.dumps(
            {"networks": SAMPLE_LXD_NETWORKS}
        )
        # all interfaces from binary output are included in result
        self.assertCountEqual(SAMPLE_LXD_NETWORKS, get_ip_addr())
        self.assertThat(
            patch_call_and_check,
            MockCalledOnceWith([get_resources_bin_path()]),
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
