# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Debian `/etc/network/interfaces` generation."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from random import randint
from textwrap import dedent

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import ANY
from provisioningserver.drivers.osystem import debian_networking
from provisioningserver.drivers.osystem.debian_networking import (
    compose_ipv4_stanza,
    compose_ipv6_stanza,
    compose_network_interfaces,
    has_static_ipv6_address,
)
from testtools.matchers import Contains


class TestComposeIPv4Stanza(MAASTestCase):

    def test__produces_dhcp_stanza_by_default(self):
        interface = factory.make_name('eth')
        self.assertEqual(
            "iface %s inet dhcp" % interface,
            compose_ipv4_stanza(interface).strip())

    def test__produces_static_nil_address_if_disabled(self):
        interface = factory.make_name('eth')
        stanza = compose_ipv4_stanza(interface, disable=True)
        self.expectThat(
            stanza,
            Contains("iface %s inet static\n" % interface))
        self.expectThat(
            stanza + '\n',
            Contains("address 0.0.0.0\n"))


class TestComposeIPv6Stanza(MAASTestCase):

    def test__produces_static_stanza(self):
        ip = factory.make_ipv6_address()
        netmask = randint(64, 127)
        interface = factory.make_name('eth')
        expected = dedent("""\
            iface %s inet6 static
            \tnetmask %d
            \taddress %s
            """) % (interface, netmask, ip)
        self.assertEqual(
            expected.strip(),
            compose_ipv6_stanza(interface, ip, netmask=netmask).strip())

    def test__netmask_defaults_to_64(self):
        ip = factory.make_ipv6_address()
        interface = factory.make_name('eth')
        self.assertIn('netmask 64', compose_ipv6_stanza(interface, ip))

    def test__netmask_accepts_address_style_netmask_string(self):
        ip = factory.make_ipv6_address()
        netmask = 'ffff:ffff:ffff:ffff:ffff:ffff:ffff:fffc'
        interface = factory.make_name('eth')
        self.assertIn(
            'netmask %s' % netmask,
            compose_ipv6_stanza(interface, ip, netmask=netmask))

    def test__includes_gateway_if_given(self):
        ip = factory.make_ipv6_address()
        interface = factory.make_name('eth')
        gateway = factory.make_ipv6_address()
        expected = dedent("""\
            iface %s inet6 static
            \tnetmask 64
            \taddress %s
            \tgateway %s
            """) % (interface, ip, gateway)
        self.assertEqual(
            expected.strip(),
            compose_ipv6_stanza(interface, ip, gateway=gateway).strip())

    def test__adds_nameserver_if_given(self):
        ip = factory.make_ipv6_address()
        interface = factory.make_name('eth')
        nameserver = factory.make_ipv6_address()
        expected = dedent("""\
            iface %s inet6 static
            \tnetmask 64
            \taddress %s
            \tdns-nameservers %s
            """) % (interface, ip, nameserver)
        self.assertEqual(
            expected.strip(),
            compose_ipv6_stanza(interface, ip, nameserver=nameserver).strip())


class TestHasStaticIPv6Address(MAASTestCase):

    def test__returns_False_for_empty_mapping(self):
        self.assertFalse(has_static_ipv6_address({}))

    def test__finds_IPv6_address(self):
        self.assertTrue(
            has_static_ipv6_address(
                {factory.make_mac_address(): {factory.make_ipv6_address()}}))

    def test__ignores_IPv4_address(self):
        self.assertFalse(
            has_static_ipv6_address(
                {factory.make_mac_address(): {factory.make_ipv4_address()}}))

    def test__finds_IPv6_address_among_IPv4_addresses(self):
        mapping = {
            factory.make_mac_address(): {factory.make_ipv4_address()},
            factory.make_mac_address(): {
                factory.make_ipv4_address(),
                factory.make_ipv6_address(),
                factory.make_ipv4_address(),
                },
            factory.make_mac_address(): {factory.make_ipv4_address()},
            }
        self.assertTrue(has_static_ipv6_address(mapping))


class TestComposeNetworkInterfaces(MAASTestCase):

    def make_listing(self, interface=None, mac=None):
        """Return a list containing an interface/MAC tuple."""
        if interface is None:
            interface = factory.make_name('eth')
        if mac is None:
            mac = factory.make_mac_address()
        return [(interface, mac)]

    def make_mapping(self, mac=None, ips=None):
        """Create a MAC-to-IPs `defaultdict` like `map_static_ips` returns.

        The mapping will map `mac` (random by default) to `ips` (containing
        one IPv6 address by default).
        """
        if mac is None:
            mac = factory.make_mac_address()
        if ips is None:
            ips = {factory.make_ipv6_address()}
        return {mac: ips}

    def test__always_generates_lo(self):
        self.assertIn('auto lo', compose_network_interfaces([], [], {}, {}))

    def test__generates_DHCPv4_config_if_IPv4_not_disabled(self):
        interface = factory.make_name('eth')
        mac = factory.make_mac_address()
        self.assertIn(
            "\niface %s inet dhcp\n" % interface,
            compose_network_interfaces(
                self.make_listing(interface, mac), [], {}, {}))

    def test__generates_DHCPv4_config_if_no_IPv6_configured(self):
        interface = factory.make_name('eth')
        mac = factory.make_mac_address()
        self.assertIn(
            "\niface %s inet dhcp\n" % interface,
            compose_network_interfaces(
                self.make_listing(interface, mac), [], {}, {},
                disable_ipv4=True))

    def test__disables_IPv4_statically_if_IPv4_disabled(self):
        interface = factory.make_name('eth')
        mac = factory.make_mac_address()
        self.assertIn(
            "\niface %s inet static" % interface,
            compose_network_interfaces(
                self.make_listing(interface, mac), [], self.make_mapping(mac),
                {}, disable_ipv4=True))

    def test__generates_static_IPv6_config(self):
        interface = factory.make_name('eth')
        mac = factory.make_mac_address()
        ipv6 = factory.make_ipv6_address()
        disable_ipv4 = factory.pick_bool()
        self.assertIn(
            "\niface %s inet6 static" % interface,
            compose_network_interfaces(
                self.make_listing(interface, mac), [],
                self.make_mapping(mac, {ipv6}), {}, disable_ipv4=disable_ipv4))

    def test__passes_subnet_details_when_creating_IPv6_stanza(self):
        interface = factory.make_name('eth')
        mac = factory.make_mac_address()
        ipv6 = factory.make_ipv6_address()
        gateway = factory.make_ipv6_address()
        nameserver = factory.make_ipv6_address()
        netmask = '%s' % randint(16, 127)
        fake = self.patch_autospec(debian_networking, 'compose_ipv6_stanza')
        fake.return_value = factory.make_name('stanza')

        compose_network_interfaces(
            self.make_listing(interface, mac), [],
            self.make_mapping(mac, {ipv6}), self.make_mapping(mac, {gateway}),
            nameservers=[nameserver], netmasks={ipv6: netmask})

        self.assertThat(
            fake, MockCalledOnceWith(
                interface, ipv6, gateway=gateway, nameserver=nameserver,
                netmask=netmask))

    def test__ignores_IPv4_nameserver_when_creating_IPv6_stanza(self):
        interface = factory.make_name('eth')
        mac = factory.make_mac_address()
        ipv6 = factory.make_ipv6_address()
        nameserver = factory.make_ipv4_address()
        fake = self.patch_autospec(debian_networking, 'compose_ipv6_stanza')
        fake.return_value = factory.make_name('stanza')

        compose_network_interfaces(
            self.make_listing(interface, mac), [],
            self.make_mapping(mac, {ipv6}), gateways_mapping={},
            nameservers=[nameserver])

        self.assertThat(
            fake, MockCalledOnceWith(
                interface, ANY, gateway=ANY, nameserver=None, netmask=ANY))

    def test__omits_gateway_and_nameserver_if_not_set(self):
        interface = factory.make_name('eth')
        mac = factory.make_mac_address()
        fake = self.patch_autospec(debian_networking, 'compose_ipv6_stanza')
        fake.return_value = factory.make_name('stanza')

        compose_network_interfaces(
            self.make_listing(interface, mac), [], self.make_mapping(mac), {})

        self.assertThat(
            fake,
            MockCalledOnceWith(
                interface, ANY, gateway=None, nameserver=None, netmask=ANY))

    def test__writes_auto_lines_for_interfaces_in_auto_interfaces(self):
        interface = factory.make_name('eth')
        mac = factory.make_mac_address()

        interfaces_file = compose_network_interfaces(
            self.make_listing(interface, mac), [mac], {}, {})

        self.assertIn('auto %s' % interface, interfaces_file)
        self.assertEqual(1, interfaces_file.count('auto %s' % interface))

    def test__omits_auto_lines_for_interfaces_not_in_auto_interfaces(self):
        interface = factory.make_name('eth')
        interfaces_file = compose_network_interfaces(
            self.make_listing(interface), [factory.make_mac_address()], {}, {})
        self.assertNotIn('auto %s' % interface, interfaces_file)
