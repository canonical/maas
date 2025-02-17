# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.dns import get_iface_name_based_hostname, get_ip_based_hostname
from maastesting.factory import factory


class TestIpBasedHostnameGenerator:
    def test_ipv4_numeric(self):
        assert get_ip_based_hostname(2130706433) == "127-0-0-1"
        assert get_ip_based_hostname(int(pow(2, 32) - 1)) == "255-255-255-255"

    def test_ipv4_text(self):
        ipv4 = factory.make_ipv4_address()
        assert get_ip_based_hostname(ipv4) == ipv4.replace(".", "-")
        assert get_ip_based_hostname("172.16.0.1") == "172-16-0-1"

    def test_ipv6_text(self):
        assert (
            get_ip_based_hostname("2001:67c8:1562:1511:1:1:1:1")
            == "2001-67c8-1562-1511-1-1-1-1"
        )

    def test_ipv6_does_not_generate_invalid_name(self):
        ipv6s = ["2001:67c:1562::15", "2001:67c:1562:15::"]
        results = [get_ip_based_hostname(ipv6) for ipv6 in ipv6s]
        assert results == [
            "2001-67c-1562-0-0-0-0-15",
            "2001-67c-1562-15-0-0-0-0",
        ]


class TestIfaceBasedHostnameGenerator:
    def test_interface_name_changed(self):
        assert get_iface_name_based_hostname("eth_0") == "eth-0"

    def test_interface_name_unchanged(self):
        assert get_iface_name_based_hostname("eth0") == "eth0"

    def test_interface_name_trailing(self):
        assert get_iface_name_based_hostname("interface-") == "interface"

    def test_interface_name_leading(self):
        assert get_iface_name_based_hostname("-interface") == "interface"

    def test_interface_name_leading_nonletter(self):
        assert get_iface_name_based_hostname("33inter_face") == "inter-face"
