# Copyright 2016-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import call

from maastesting.testcase import MAASTestCase
from metadataserver.builtin_scripts.commissioning_scripts import (
    dhcp_unconfigured_ifaces,
)

# The two following example outputs differ because eth2 and eth1 are not
# configured and thus 'ip -o link show' returns a list with both 'eth1'
# and 'eth2' while 'ip -o link show up' does not contain them.

# Example output of 'ip -o link show':
ip_link_show_all = b"""\
1: eth2: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:08 brd \
 ff:ff:ff:ff:ff:ff
2: eth1: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:07 brd \
 ff:ff:ff:ff:ff:ff
3: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP mode \
 DEFAULT group default qlen 1000\\    link/ether 00:01:02:03:04:03 brd \
 ff:ff:ff:ff:ff:ff
4: eth4: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:04 brd \
 ff:ff:ff:ff:ff:ff
5: eth5: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:06 brd \
 ff:ff:ff:ff:ff:ff
6: eth6: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:06 brd \
 ff:ff:ff:ff:ff:ff
7: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode \
 DEFAULT group default qlen 1000\\    link/loopback 00:00:00:00:00:00 brd \
 00:00:00:00:00:00
8: virbr0: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:02 brd \
 ff:ff:ff:ff:ff:ff
9: wlan0: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:05 brd \
 ff:ff:ff:ff:ff:ff
"""

# Example output of 'ip -o link show up':
ip_link_show = b"""\
1: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP mode \
 DEFAULT group default qlen 1000\\    link/ether 00:01:02:03:04:03 brd \
 ff:ff:ff:ff:ff:ff
2: eth4: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state UP mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:04 brd \
 ff:ff:ff:ff:ff:ff
3: eth5: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state UP mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:06 brd \
 ff:ff:ff:ff:ff:ff
4: eth6: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state UP mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:06 brd \
 ff:ff:ff:ff:ff:ff
5: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode \
 DEFAULT group default qlen 1000\\    link/loopback 00:00:00:00:00:00 \
 brd 00:00:00:00:00:00
6: virbr0: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state UP mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:02 brd \
 ff:ff:ff:ff:ff:ff
7: wlan0: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state UP mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:05 brd \
 ff:ff:ff:ff:ff:ff
"""

# Example output of 'ip addr list dev XX':
ip_eth0 = b"""\
3: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP ...
    link/ether 00:01:02:03:04:03 brd ff:ff:ff:ff:ff:ff
    inet 192.168.0.1/24 brd 192.168.0.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet6 2001:db8::32/64 scope global
       valid_lft forever preferred_lft forever
    inet6 fe80::0201:02ff:fe03:0403/64 scope link
       valid_lft forever preferred_lft forever
"""
ip_eth4 = b"""\
4: eth4: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP ...
    link/ether 00:01:02:03:04:04 brd ff:ff:ff:ff:ff:ff
    inet 192.168.4.1/24 brd 192.168.4.255 scope global eth4
       valid_lft forever preferred_lft forever
    inet6 fe80::0201:02ff:fe03:0404/64 scope link
       valid_lft forever preferred_lft forever
"""
ip_eth5 = b"""\
6: eth5: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP ...
    link/ether 00:01:02:03:04:06 brd ff:ff:ff:ff:ff:ff
    inet 192.168.5.1/24 brd 192.168.4.255 scope global eth4
       valid_lft forever preferred_lft forever
"""
ip_eth6 = b"""\
6: eth6: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP ...
    link/ether 00:01:02:03:04:06 brd ff:ff:ff:ff:ff:ff
    inet6 2001:db8:0:6::32/64 scope global
       valid_lft forever preferred_lft forever
    inet6 fe80::0201:02ff:fe03:0406/64 scope link
       valid_lft forever preferred_lft forever
"""
ip_lo = b"""\
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN ...
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host
       valid_lft forever preferred_lft forever
"""
ip_virbr0 = b"""\
2: virbr0: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN ...
    link/ether 00:01:02:03:04:02 brd ff:ff:ff:ff:ff:ff
    inet 192.168.122.1/24 brd 192.168.122.255 scope global virbr0
       valid_lft forever preferred_lft forever
    inet6 fe80::0201:02ff:fe03:0402/64 scope link
       valid_lft forever preferred_lft forever
"""
ip_wlan0 = b"""\
5: wlan0: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN ...
    link/ether 00:01:02:03:04:05 brd ff:ff:ff:ff:ff:ff
    inet 192.168.3.1/24 brd 192.168.3.255 scope global virbr0
       valid_lft forever preferred_lft forever
    inet6 fe80::0201:02ff:fe03:0405/64 scope link
       valid_lft forever preferred_lft forever
"""


DHCP6_TEMPLATE = (
    "for idx in $(seq 10); do dhclient -6 %s && break || sleep 10; done"
)
DHCPCD6_TEMPLATE = (
    "for idx in $(seq 10); do dhcpcd -t 30 -6 %s && break || sleep 10; done"
)


class TestDHCPExplore(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.patch(dhcp_unconfigured_ifaces, "print")
        self.patch(dhcp_unconfigured_ifaces, "sleep")

    def test_calls_dhclient_on_unconfigured_interfaces(self):
        self.patch(
            dhcp_unconfigured_ifaces, "which"
        ).return_value = "/usr/sbin/dhclient"
        check_output = self.patch(dhcp_unconfigured_ifaces, "check_output")
        check_output.side_effect = [
            ip_link_show_all,
            ip_link_show,
            ip_eth0,
            ip_eth4,
            ip_eth5,
            ip_eth6,
            ip_lo,
            ip_virbr0,
            ip_wlan0,
            ip_eth0,
            ip_eth4,
            ip_eth5,
            ip_eth6,
            ip_lo,
            ip_virbr0,
            ip_wlan0,
            # Return interfaces with IPs so there isn't a sleep
            ip_wlan0,
            ip_wlan0,
            ip_wlan0,
            ip_eth0,
            ip_eth0,
            ip_eth0,
            ip_eth0,
            ip_eth0,
        ]
        mock_call = self.patch(dhcp_unconfigured_ifaces, "call")
        mock_popen = self.patch(dhcp_unconfigured_ifaces, "Popen")
        dhcp_unconfigured_ifaces.dhcp_explore()
        mock_call.assert_has_calls(
            [
                call(["dhclient", "-nw", "-4", "eth1"]),
                call(["dhclient", "-nw", "-4", "eth2"]),
                call(["dhclient", "-nw", "-4", "eth6"]),
            ]
        )
        mock_popen.assert_has_calls(
            [
                call(["sh", "-c", DHCP6_TEMPLATE % "eth0"]),
                call(["sh", "-c", DHCP6_TEMPLATE % "eth1"]),
                call(["sh", "-c", DHCP6_TEMPLATE % "eth2"]),
                call(["sh", "-c", DHCP6_TEMPLATE % "eth5"]),
            ],
        )

    def test_calls_dhcpcd_on_unconfigured_interfaces(self):
        self.patch(dhcp_unconfigured_ifaces, "which").return_value = None
        check_output = self.patch(dhcp_unconfigured_ifaces, "check_output")
        check_output.side_effect = [
            ip_link_show_all,
            ip_link_show,
            ip_eth0,
            ip_eth4,
            ip_eth5,
            ip_eth6,
            ip_lo,
            ip_virbr0,
            ip_wlan0,
            ip_eth0,
            ip_eth4,
            ip_eth5,
            ip_eth6,
            ip_lo,
            ip_virbr0,
            ip_wlan0,
            # Return interfaces with IPs so there isn't a sleep
            ip_wlan0,
            ip_wlan0,
            ip_wlan0,
            ip_eth0,
            ip_eth0,
            ip_eth0,
            ip_eth0,
            ip_eth0,
        ]
        mock_call = self.patch(dhcp_unconfigured_ifaces, "call")
        mock_popen = self.patch(dhcp_unconfigured_ifaces, "Popen")
        dhcp_unconfigured_ifaces.dhcp_explore()
        mock_call.assert_has_calls(
            [
                call(["dhcpcd", "-b", "-4", "eth1"]),
                call(["dhcpcd", "-b", "-4", "eth2"]),
                call(["dhcpcd", "-b", "-4", "eth6"]),
            ]
        )
        mock_popen.assert_has_calls(
            [
                call(["sh", "-c", DHCPCD6_TEMPLATE % "eth0"]),
                call(["sh", "-c", DHCPCD6_TEMPLATE % "eth1"]),
                call(["sh", "-c", DHCPCD6_TEMPLATE % "eth2"]),
                call(["sh", "-c", DHCPCD6_TEMPLATE % "eth5"]),
            ],
        )
