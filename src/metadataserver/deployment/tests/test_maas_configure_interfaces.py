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
from errno import (
    EACCES,
    ENOENT,
)
from os import (
    makedirs,
    remove,
)
import os.path
from random import randint
from textwrap import dedent

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
import metadataserver.deployment.maas_configure_interfaces as script
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
        gateway = factory.make_ipv6_address()
        mac = factory.make_mac_address()
        args = parser.parse_args([
            '--config-dir=%s' % config_dir,
            '--update-interfaces',
            '--restart-interfaces',
            '--static-ip=%s=%s' % (ip, mac),
            '--gateway=%s=%s' % (gateway, mac),
            '--name-interfaces',
            ])
        self.expectThat(args.config_dir, Equals(config_dir))
        self.expectThat(args.static_ip, Equals([(ip, mac)]))
        self.expectThat(args.gateway, Equals([(gateway, mac)]))
        self.assertTrue(args.update_interfaces)
        self.assertTrue(args.restart_interfaces)
        self.assertTrue(args.name_interfaces)

    def test__leaves_dangerous_options_off_by_default(self):
        defaults = script.prepare_parser().parse_args([])
        self.assertFalse(defaults.update_interfaces)
        self.assertFalse(defaults.restart_interfaces)
        self.assertFalse(defaults.name_interfaces)

    def test__parses_multiple_ip_mac_pairs(self):
        parser = script.prepare_parser()
        pairs = [
            (factory.make_ipv6_address(), factory.make_mac_address())
            for _ in range(randint(2, 4))
            ]
        args = ['--static-ip=%s=%s' % pair for pair in pairs]
        self.assertItemsEqual(pairs, parser.parse_args(args).static_ip)

    def test__checks_for_obviously_malformed_ip_mac_pairs(self):
        ip = factory.make_ipv6_address()
        mac = factory.make_mac_address()
        parser = script.prepare_parser()
        self.assertRaises(
            script.BadArgument,
            parser.parse_args, ['--static-ip', '%s+%s' % (ip, mac)])


def make_denormalised_mac():
    """Create a MAC address that is not in its normalised form."""
    return " %s " % factory.make_mac_address().upper()


class TestSplitIPPair(MAASTestCase):

    def test__splits_ip_mac_pairs(self):
        ip = factory.make_ipv6_address()
        mac = factory.make_mac_address()
        self.assertEqual(
            (ip, mac),
            script.split_ip_mac_pair('%s=%s' % (ip, mac)))

    def test__normalises_macs(self):
        ip = factory.make_ipv6_address()
        mac = make_denormalised_mac()
        self.assertNotEqual(script.normalise_mac(mac), mac)
        self.assertEqual(
            (ip, script.normalise_mac(mac)),
            script.split_ip_mac_pair('%s=%s' % (ip, mac)))


class TestNormaliseMAC(MAASTestCase):

    def test__normalises(self):
        mac = factory.make_mac_address()
        self.assertEqual(
            script.normalise_mac(mac.lower()),
            script.normalise_mac(mac.upper()))

    def test__is_idempotent(self):
        mac = factory.make_mac_address()
        self.assertEqual(
            script.normalise_mac(mac),
            script.normalise_mac(script.normalise_mac(mac)))

    def test__strips_whitespace(self):
        mac = factory.make_mac_address()
        self.assertEqual(mac, script.normalise_mac(' %s\n' % mac))


class TestMapInterfacesByMAC(MAASTestCase):

    def patch_listdir(self, listings):
        """Replace `os.listdir` with a fake that returns the given listings.

        :param listings: A dict mapping directory paths to their contents.
        """
        self.patch(script, 'listdir', listings.__getitem__)

    def patch_read_file(self, files):
        """Replace `read_file` with a fake that returns the given files.

        :param files: A dict mapping file paths to their contents.
        """
        self.patch(script, 'read_file', files.__getitem__)

    def test__parses_realistic_output(self):
        self.patch_listdir(
            {'/sys/class/net': ['eth0', 'eth1', 'lo', 'virbr0']})
        self.patch_read_file({
            '/sys/class/net/eth0/address': b'cc:5d:2e:6a:e5:eb',
            '/sys/class/net/eth1/address': b'00:1e:0b:a1:6c:7b',
            '/sys/class/net/lo/address': b'00:00:00:00:00:00',
            '/sys/class/net/virbr0/address': b'c6:13:5d:51:42:ca',
            })
        expected_mapping = {
            '00:00:00:00:00:00': ['lo'],
            'cc:5d:2e:6a:e5:eb': ['eth0'],
            '00:1e:0b:a1:6c:7b': ['eth1'],
            'c6:13:5d:51:42:ca': ['virbr0'],
            }

        self.assertEqual(expected_mapping, script.map_interfaces_by_mac())

    def test__integrates_with_real_sys_class_net(self):
        real_interfaces = script.map_interfaces_by_mac()
        self.assertIsInstance(real_interfaces, dict)
        self.assertNotEqual({}, real_interfaces)

    def test__normalises_macs(self):
        interface = factory.make_name('eth')
        mac = make_denormalised_mac()
        self.assertNotEqual(script.normalise_mac(mac), mac)
        self.patch_listdir({'/sys/class/net': [interface]})
        self.patch_read_file({'/sys/class/net/%s/address' % interface: mac})
        self.assertEqual(
            [script.normalise_mac(mac)],
            list(script.map_interfaces_by_mac().keys()))

    def test__ignores_interfaces_without_addresses(self):
        interface = factory.make_name('eth')
        self.patch_listdir({'/sys/class/net': [interface]})
        self.patch_autospec(script, 'read_file').side_effect = (
            IOError(ENOENT, "Deliberate error: No such file or directory."))
        self.assertEqual({}, script.map_interfaces_by_mac())

    def test__propagates_other_IOErrors(self):
        interface = factory.make_name('eth')
        self.patch_listdir({'/sys/class/net': [interface]})
        self.patch_autospec(script, 'read_file').side_effect = (
            IOError(EACCES, "Deliberate error: Permission denied."))
        self.assertRaises(IOError, script.map_interfaces_by_mac)

    def test__propagates_other_exceptions(self):
        class FakeError(Exception):
            """Some other type of exception that the script isn't expecting."""

        interface = factory.make_name('eth')
        self.patch_listdir({'/sys/class/net': [interface]})
        self.patch_autospec(script, 'read_file').side_effect = FakeError()
        self.assertRaises(FakeError, script.map_interfaces_by_mac)


class TestMapAddressesByInterface(MAASTestCase):

    def test__combines_mappings(self):
        ip = factory.make_ipv6_address()
        mac = factory.make_mac_address()
        interface = factory.make_name('eth')
        self.assertEqual(
            {interface: [ip]},
            script.map_addresses_by_interface(
                {mac: [interface]},
                [(ip, mac)]))

    def test__ignores_unknown_macs(self):
        ip = factory.make_ipv6_address()
        mac = factory.make_mac_address()
        self.assertEqual(
            {},
            script.map_addresses_by_interface({}, [(ip, mac)]))

    def test__ignores_unknown_interfaces(self):
        ip = factory.make_ipv6_address()
        mac = factory.make_mac_address()
        self.assertEqual(
            {},
            script.map_addresses_by_interface({mac: []}, [(ip, mac)]))

    def test__combines_addresses_per_interface(self):
        ip1 = factory.make_ipv6_address()
        ip2 = factory.make_ipv6_address()
        mac = factory.make_mac_address()
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
            script.compose_config_stanza(interface, [ip], []).strip())

    def test__includes_all_given_addresses(self):
        ips = [factory.make_ipv6_address() for _ in range(3)]
        interface = factory.make_name('eth')
        self.assertThat(
            script.compose_config_stanza(interface, ips, []).strip(),
            ContainsAll("address %s" % ip for ip in ips))

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
            script.compose_config_stanza(interface, [ip], [gateway]).strip())


class TestComposeConfigFile(MAASTestCase):

    def test__returns_config_file_text(self):
        ip = factory.make_ipv6_address()
        mac = factory.make_mac_address()
        interface = factory.make_name('eth')
        self.assertIn(
            script.compose_config_stanza(interface, [ip], []),
            script.compose_config_file(
                {mac: [interface]}, {interface: [ip]}, {}))


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

    def make_config_dir(self, interfaces_content=''):
        """Create an `/etc/network` lookalike directory.

        The directory will contain an `interfaces` file (with the given
        contents), and an `interfaces.d` directory.
        """
        config_dir = self.make_dir()
        makedirs(os.path.join(config_dir, 'interfaces.d'))
        factory.make_file(config_dir, 'interfaces', interfaces_content)
        return config_dir

    def patch_write_file(self):
        return self.patch_autospec(script, 'write_file')

    def test__skips_if_network_interfaces_does_not_exist(self):
        config_dir = self.make_config_dir()
        remove(os.path.join(config_dir, 'interfaces'))
        write_file = self.patch_write_file()
        result = script.configure_static_addresses(
            config_dir, ip_mac_pairs=[], gateway_mac_pairs=[],
            interfaces_by_mac={})
        self.expectThat(result, Equals([]))
        self.expectThat(write_file, MockNotCalled())

    def test__skips_if_config_dir_does_not_exist(self):
        config_dir = os.path.join(self.make_dir(), factory.make_name('nondir'))
        write_file = self.patch_write_file()
        result = script.configure_static_addresses(
            config_dir, ip_mac_pairs=[], gateway_mac_pairs=[],
            interfaces_by_mac={})
        self.expectThat(result, Equals([]))
        self.expectThat(write_file, MockNotCalled())

    def test__writes_to_interfaces_d(self):
        config_dir = self.make_config_dir()
        script.configure_static_addresses(
            config_dir, ip_mac_pairs=[], gateway_mac_pairs=[],
            interfaces_by_mac={})
        self.assertThat(
            os.path.join(config_dir, 'interfaces.d', 'maas-config'),
            FileExists())

    def test__writes_network_config(self):
        write_file = self.patch_write_file()
        ip = factory.make_ipv6_address()
        mac = factory.make_mac_address()
        interface = factory.make_name('eth')
        config_dir = self.make_config_dir()

        script.configure_static_addresses(
            config_dir, ip_mac_pairs=[(ip, mac)], gateway_mac_pairs=[],
            interfaces_by_mac={mac: [interface]})

        self.assertThat(write_file, MockCalledOnceWith(ANY, ANY))
        [mock_call] = write_file.mock_calls
        _, args, _ = mock_call
        _, content = args
        self.assertIn("address %s" % ip, content)

    def test__returns_interfaces_with_addresses(self):
        ip = factory.make_ipv6_address()
        mac = factory.make_mac_address()
        interface = factory.make_name('eth')
        config_dir = self.make_config_dir()
        self.patch_write_file()
        self.assertEqual(
            [interface],
            script.configure_static_addresses(
                config_dir, ip_mac_pairs=[(ip, mac)], gateway_mac_pairs=[],
                interfaces_by_mac={mac: [interface]}))

    def test__ignores_interfaces_without_addresses(self):
        ip = factory.make_ipv6_address()
        mac = factory.make_mac_address()
        config_dir = self.make_config_dir()
        self.patch_write_file()
        self.assertEqual(
            [],
            script.configure_static_addresses(
                config_dir, ip_mac_pairs=[(ip, mac)], gateway_mac_pairs=[],
                interfaces_by_mac={}))


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


class TestGenerateUdevRule(MAASTestCase):

    def test__generates_udev_rule(self):
        interface = factory.make_name('eth')
        mac = factory.make_mac_address()
        expected_rule = (
            'SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", '
            'ATTR{address}=="%(mac)s", NAME="%(interface)s"'
            ) % {'mac': mac, 'interface': interface}
        self.assertEqual(
            expected_rule,
            script.generate_udev_rule(interface, mac).strip())


class TestNameInterfaces(MAASTestCase):

    def patch_write_file(self):
        return self.patch_autospec(script, 'write_file')

    def test__writes_udev_file(self):
        interface = factory.make_name('eth')
        mac = factory.make_mac_address()
        write_file = self.patch_write_file()
        script.name_interfaces({mac: [interface]})
        self.assertThat(
            write_file,
            MockCalledOnceWith(
                '/etc/udev/rules.d/70-persistent-net.rules', ANY))

    def test__writes_udev_rules(self):
        interface = factory.make_name('eth')
        mac = factory.make_mac_address()
        write_file = self.patch_write_file()
        script.name_interfaces({mac: [interface]})
        [call] = write_file.mock_calls
        _, args, _ = call
        _, content = args
        self.assertIn('NAME="%s"' % interface, content)

    def test__skips_loopback_but_names_other_interfaces(self):
        # Testing the loopback interface together with a "regular" network
        # interface.  Without the regular interface, a code change could
        # accidentally cause the patched generate_udev_rule never to be called
        # at all.  If it weren't for the extra interface, the test wouldn't
        # notice.
        self.patch_write_file()
        lo_interface = 'lo'
        lo_mac = '00:00:00:00:00:00'
        proper_interface = factory.make_name('eth')
        proper_mac = factory.make_mac_address()
        generate_udev_rule = self.patch_autospec(script, 'generate_udev_rule')
        generate_udev_rule.return_value = "(udev rule)"
        script.name_interfaces(
            {
                lo_mac: [lo_interface],
                proper_mac: [proper_interface],
            })
        self.assertThat(
            generate_udev_rule,
            MockCalledOnceWith(proper_interface, proper_mac))

    def test__skips_if_udev_rules_d_does_not_exist(self):
        interface = factory.make_name('eth')
        mac = factory.make_mac_address()
        write_file = self.patch_write_file()
        write_file.side_effect = IOError(
            ENOENT, "Deliberate error: No such file or directory.")
        # The exception occurs but does not get propagated.
        script.name_interfaces({mac: [interface]})
        self.assertThat(write_file, MockCalledOnceWith(ANY, ANY))

    def test__propagates_similar_but_different_errors_writing_file(self):
        interface = factory.make_name('eth')
        mac = factory.make_mac_address()
        write_file = self.patch_write_file()
        write_file.side_effect = IOError(
            EACCES, "Deliberate error: Permission denied.")
        self.assertRaises(
            IOError,
            script.name_interfaces, {mac: [interface]})
