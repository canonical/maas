# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.utils.dhcp``."""

__all__ = []

from maastesting.factory import factory
from maastesting.matchers import DocTestMatches
from maastesting.testcase import MAASTestCase
from netaddr import IPAddress
from provisioningserver.utils.dhcp import DHCP
from testtools.matchers import Equals, Is


class TestDHCP(MAASTestCase):
    def test__is_valid_returns_false_for_truncated_packet(self):
        packet = factory.make_dhcp_packet(truncated=True)
        dhcp = DHCP(packet)
        self.assertThat(dhcp.is_valid(), Equals(False))
        self.assertThat(
            dhcp.invalid_reason, DocTestMatches("Truncated DHCP packet.")
        )

    def test__is_valid_returns_false_for_invalid_cookie(self):
        packet = factory.make_dhcp_packet(bad_cookie=True)
        dhcp = DHCP(packet)
        self.assertThat(dhcp.is_valid(), Equals(False))
        self.assertThat(
            dhcp.invalid_reason, DocTestMatches("Invalid DHCP cookie.")
        )

    def test__is_valid_returns_false_for_truncated_option_length(self):
        packet = factory.make_dhcp_packet(truncated_option_length=True)
        dhcp = DHCP(packet)
        self.assertThat(dhcp.is_valid(), Equals(False))
        self.assertThat(
            dhcp.invalid_reason,
            DocTestMatches("Truncated length field in DHCP option."),
        )

    def test__is_valid_returns_false_for_truncated_option_value(self):
        packet = factory.make_dhcp_packet(truncated_option_value=True)
        dhcp = DHCP(packet)
        self.assertThat(dhcp.is_valid(), Equals(False))
        self.assertThat(
            dhcp.invalid_reason, DocTestMatches("Truncated DHCP option value.")
        )

    def test__is_valid_return_true_for_valid_packet(self):
        packet = factory.make_dhcp_packet()
        dhcp = DHCP(packet)
        self.assertThat(dhcp.is_valid(), Equals(True))

    def test__returns_server_identifier_if_included(self):
        server_ip = factory.make_ip_address(ipv6=False)
        packet = factory.make_dhcp_packet(
            include_server_identifier=True, server_ip=server_ip
        )
        dhcp = DHCP(packet)
        self.assertThat(dhcp.is_valid(), Equals(True))
        self.assertThat(dhcp.server_identifier, Equals(IPAddress(server_ip)))

    def test__server_identifier_none_if_not_included(self):
        packet = factory.make_dhcp_packet(include_server_identifier=False)
        dhcp = DHCP(packet)
        self.assertThat(dhcp.is_valid(), Equals(True))
        self.assertThat(dhcp.server_identifier, Is(None))
