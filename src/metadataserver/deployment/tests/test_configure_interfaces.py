# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the node-side `configure-interfaces` script."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from argparse import ArgumentParser
from os import makedirs
import os.path
from random import randint
from textwrap import dedent

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    )
from maastesting.testcase import MAASTestCase
import metadataserver.deployment.configure_interfaces as script
from mock import (
    ANY,
    call,
    )
from testtools.matchers import (
    ContainsAll,
    Equals,
    FileContains,
    FileExists,
    )


class TestPrepareParser(MAASTestCase):

    def test__returns_parser(self):
        self.assertIsInstance(script.prepare_parser(), ArgumentParser)

    def test__accepts_empty_command_line(self):
        parser = script.prepare_parser()
        self.assertIsNotNone(parser.parse_args([]))

    def test__accepts_typical_command_line(self):
        parser = script.prepare_parser()
        config_dir = factory.make_name('etc-network')
        ip = factory.make_ipv6_address()
        mac = factory.getRandomMACAddress()
        args = parser.parse_args([
            '--config-dir=%s' % config_dir,
            '--update-interfaces',
            '--restart-interfaces',
            '--static-ip=%s=%s' % (ip, mac),
            ])
        self.expectThat(args.config_dir, Equals(config_dir))
        self.expectThat(args.static_ip, Equals([(ip, mac)]))
        self.assertTrue(args.update_interfaces)
        self.assertTrue(args.restart_interfaces)

    def test__leaves_dangerous_options_off_by_default(self):
        defaults = script.prepare_parser().parse_args([])
        self.assertFalse(defaults.update_interfaces)
        self.assertFalse(defaults.restart_interfaces)

    def test__parses_multiple_ip_mac_pairs(self):
        parser = script.prepare_parser()
        pairs = [
            (factory.make_ipv6_address(), factory.getRandomMACAddress())
            for _ in range(randint(2, 4))
            ]
        args = ['--static-ip=%s=%s' % pair for pair in pairs]
        self.assertItemsEqual(pairs, parser.parse_args(args).static_ip)

    def test__checks_for_obviously_malformed_ip_mac_pairs(self):
        ip = factory.make_ipv6_address()
        mac = factory.getRandomMACAddress()
        parser = script.prepare_parser()
        self.assertRaises(
            script.BadArgument,
            parser.parse_args, ['--static-ip', '%s+%s' % (ip, mac)])


class TestSplitIPPair(MAASTestCase):

    def test__splits_ip_mac_pairs(self):
        ip = factory.make_ipv6_address()
        mac = factory.getRandomMACAddress()
        self.assertEqual(
            (ip, mac),
            script.split_ip_mac_pair('%s=%s' % (ip, mac)))

    def test__normalises_macs(self):
        ip = factory.make_ipv6_address()
        mac = factory.getRandomMACAddress().upper()
        self.assertNotEqual(script.normalise_mac(mac), mac)
        self.assertEqual(
            (ip, script.normalise_mac(mac)),
            script.split_ip_mac_pair('%s=%s' % (ip, mac)))


class TestNormaliseMAC(MAASTestCase):

    def test__normalises(self):
        mac = factory.getRandomMACAddress()
        self.assertEqual(
            script.normalise_mac(mac.lower()),
            script.normalise_mac(mac.upper()))

    def test__is_idempotent(self):
        mac = factory.getRandomMACAddress()
        self.assertEqual(
            script.normalise_mac(mac),
            script.normalise_mac(script.normalise_mac(mac)))


class TestMapInterfacesByMAC(MAASTestCase):

    def patch_ip_link(self, output):
        patch = self.patch(script, 'check_output')
        patch.return_value = output
        return patch

    def test__calls_ip_link(self):
        ip_link = self.patch_ip_link('')
        script.map_interfaces_by_mac()
        self.assertThat(
            ip_link, MockCalledOnceWith([
                'ip',
                '-f', 'link',
                'link',
                ],
                env={'LC_ALL': 'C'}))

    def test__integrates_with_ip_link(self):
        result = script.map_interfaces_by_mac()
        self.assertIsInstance(result, dict)

    def test__parses_realistic_output(self):
        realistic_output = '\n'.join([
            (
                "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue "
                "state UNKNOWN mode DEFAULT group default "
            ),
            "    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00",
            (
                "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 "
                "qdisc pfifo_fast state UP mode DEFAULT group default "
                "qlen 1000"
            ),
            "    link/ether cc:5d:2e:6a:e5:eb brd ff:ff:ff:ff:ff:ff",
            (
                "3: eth1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 "
                "qdisc pfifo_fast state UP mode DEFAULT group default "
                "qlen 1000"
            ),
            "    link/ether 00:1e:0b:a1:6c:7b brd ff:ff:ff:ff:ff:ff",
            (
                "4: virbr0: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 "
                "qdisc noqueue state DOWN mode DEFAULT group default "
            ),
            "    link/ether c6:13:5d:51:42:ca brd ff:ff:ff:ff:ff:ff",
            ])
        self.patch_ip_link(realistic_output)

        expected_mapping = {
            '00:00:00:00:00:00': ['lo'],
            'cc:5d:2e:6a:e5:eb': ['eth0'],
            '00:1e:0b:a1:6c:7b': ['eth1'],
            'c6:13:5d:51:42:ca': ['virbr0'],
            }

        self.assertEqual(expected_mapping, script.map_interfaces_by_mac())

    def test__normalises_macs(self):
        interface = factory.make_name('eth')
        mac = factory.getRandomMACAddress().upper()
        self.assertNotEqual(script.normalise_mac(mac), mac)
        output = dedent("""\
            2: %s: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 state UP
                link/ether %s brd ff:ff:ff:ff:ff:ff
            """) % (interface, mac)
        self.patch_ip_link(output)
        self.assertEqual(
            [script.normalise_mac(mac)],
            list(script.map_interfaces_by_mac().keys()))


class TestMapAddressesByInterface(MAASTestCase):

    def test__combines_mappings(self):
        ip = factory.make_ipv6_address()
        mac = factory.getRandomMACAddress()
        interface = factory.make_name('eth')
        self.assertEqual(
            {interface: [ip]},
            script.map_addresses_by_interface(
                {mac: [interface]},
                [(ip, mac)]))

    def test__ignores_unknown_macs(self):
        ip = factory.make_ipv6_address()
        mac = factory.getRandomMACAddress()
        self.assertEqual(
            {},
            script.map_addresses_by_interface({}, [(ip, mac)]))

    def test__ignores_unknown_interfaces(self):
        ip = factory.make_ipv6_address()
        mac = factory.getRandomMACAddress()
        self.assertEqual(
            {},
            script.map_addresses_by_interface({mac: []}, [(ip, mac)]))

    def test__combines_addresses_per_interface(self):
        ip1 = factory.make_ipv6_address()
        ip2 = factory.make_ipv6_address()
        mac = factory.getRandomMACAddress()
        interface = factory.make_name('eth')
        mapping = script.map_addresses_by_interface(
            {mac: [interface]},
            [(ip1, mac), (ip2, mac)])
        self.assertItemsEqual([ip1, ip2], mapping[interface])


class TestComposeConfigStanza(MAASTestCase):

    def test__produces_interfaces_stanza(self):
        ip = factory.make_ipv6_address()
        interface = factory.make_name('eth')
        expected = dedent("""\
            iface %s inet6 static
            \tnetmask 64
            \taddress %s
            """) % (interface, ip)
        self.assertEqual(
            expected.strip(),
            script.compose_config_stanza(interface, [ip]).strip())

    def test__includes_all_given_addresses(self):
        ips = [factory.make_ipv6_address() for _ in range(3)]
        interface = factory.make_name('eth')
        self.assertThat(
            script.compose_config_stanza(interface, ips).strip(),
            ContainsAll("address %s" % ip for ip in ips))


class TestComposeConfigFile(MAASTestCase):

    def test__returns_config_file_text(self):
        ip = factory.make_ipv6_address()
        mac = factory.getRandomMACAddress()
        interface = factory.make_name('eth')
        self.assertIn(
            script.compose_config_stanza(interface, [ip]),
            script.compose_config_file({mac: [interface]}, {interface: [ip]}))


class TestLocateMAASConfig(MAASTestCase):

    def test__returns_typical_location(self):
        self.assertEqual(
            '/etc/network/interfaces.d/maas-config',
            script.locate_maas_config('/etc/network'))

    def test__obeys_config_dir(self):
        config_dir = factory.make_name('etc-network')
        self.assertEqual(
            '%s/interfaces.d/maas-config' % config_dir,
            script.locate_maas_config(config_dir))


class TestWriteFile(MAASTestCase):

    def test__writes_file(self):
        path = os.path.join(self.make_dir(), factory.make_name('file'))
        content = factory.make_name('content')
        script.write_file(path, content)
        self.assertThat(path, FileContains(content))

    def test__obeys_encoding(self):
        path = os.path.join(self.make_dir(), factory.make_name('file'))
        text = factory.make_name('\u0f00')
        script.write_file(path, text, encoding='utf-16')
        self.assertThat(path, FileContains(text.encode('utf-16')))

    def test__replaces_existing_file(self):
        path = self.make_file()
        content = factory.make_name('new-content')
        script.write_file(path, content)
        self.assertThat(path, FileContains(content))


class TestConfigureStaticAddresses(MAASTestCase):

    def patch_write_file(self):
        return self.patch_autospec(script, 'write_file')

    def patch_interfaces_by_mac(self, mapping):
        patch = self.patch(script, 'map_interfaces_by_mac')
        patch.return_value = mapping
        return patch

    def test__writes_to_interfaces_d(self):
        config_dir = self.make_dir()
        interfaces_d = os.path.join(config_dir, 'interfaces.d')
        makedirs(interfaces_d)
        script.configure_static_addresses(config_dir, [])
        self.assertThat(
            os.path.join(interfaces_d, 'maas-config'),
            FileExists())

    def test__writes_network_config(self):
        write_file = self.patch_write_file()
        ip = factory.make_ipv6_address()
        mac = factory.getRandomMACAddress()
        interface = factory.make_name('eth')
        self.patch_interfaces_by_mac({mac: [interface]})

        script.configure_static_addresses(
            factory.make_name('dir'), [(ip, mac)])

        self.assertThat(write_file, MockCalledOnceWith(ANY, ANY))
        [mock_call] = write_file.mock_calls
        _, args, _ = mock_call
        _, content = args
        self.assertIn("address %s" % ip, content)

    def test__returns_interfaces_with_addresses(self):
        ip = factory.make_ipv6_address()
        mac = factory.getRandomMACAddress()
        interface = factory.make_name('eth')
        config_dir = factory.make_name('dir')
        self.patch_write_file()
        self.patch_interfaces_by_mac({mac: [interface]})
        self.assertEqual(
            [interface],
            script.configure_static_addresses(config_dir, [(ip, mac)]))

    def test__ignores_interfaces_without_addresses(self):
        ip = factory.make_ipv6_address()
        mac = factory.getRandomMACAddress()
        config_dir = factory.make_name('dir')
        self.patch_write_file()
        self.patch_interfaces_by_mac({})
        self.assertEqual(
            [],
            script.configure_static_addresses(config_dir, [(ip, mac)]))


class TestUpdateInterfacesFile(MAASTestCase):

    def test__adds_source_line(self):
        old_content = factory.make_string()
        interfaces_file = self.make_file('interfaces', old_content)
        script.update_interfaces_file(os.path.dirname(interfaces_file))
        self.assertThat(
            interfaces_file,
            FileContains(dedent("""\
                %s

                source interfaces.d/maas-config
                """ % old_content)))

    def test__skips_if_maas_config_already_mentioned(self):
        old_content = dedent("""\
            %s

            source interfaces.d/maas-config
            """) % factory.make_string()
        interfaces_file = self.make_file('interfaces', old_content)
        script.update_interfaces_file(os.path.dirname(interfaces_file))
        self.assertThat(interfaces_file, FileContains(old_content))


class TestRestartInterfaces(MAASTestCase):

    def test__takes_interface_down_and_up(self):
        interface = factory.make_name('eth')
        check_call = self.patch(script, 'check_call')
        script.restart_interfaces([interface])
        self.assertThat(
            check_call, MockCallsMatch(
                call(['ifdown', interface]),
                call(['ifup', interface]),
                ))
