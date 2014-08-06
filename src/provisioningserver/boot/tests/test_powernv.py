# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.boot.powernv`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os
import re

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.boot import (
    BytesReader,
    powernv as powernv_module,
    )
from provisioningserver.boot.powernv import (
    ARP_HTYPE,
    format_bootif,
    PowerNVBootMethod,
    re_config_file,
    )
from provisioningserver.boot.tests.test_pxe import parse_pxe_config
from provisioningserver.boot.tftppath import compose_image_path
from provisioningserver.testing.config import set_tftp_root
from provisioningserver.tests.test_kernel_opts import make_kernel_parameters
from provisioningserver.tftp import TFTPBackend
from testtools.matchers import (
    IsInstance,
    MatchesAll,
    MatchesRegex,
    Not,
    StartsWith,
    )


def compose_config_path(mac):
    """Compose the TFTP path for a PowerNV PXE configuration file.

    The path returned is relative to the TFTP root, as it would be
    identified by clients on the network.

    :param mac: A MAC address, in IEEE 802 hyphen-separated form,
        corresponding to the machine for which this configuration is
        relevant. This relates to PXELINUX's lookup protocol.
    :return: Path for the corresponding PXE config file as exposed over
        TFTP.
    """
    # Not using os.path.join: this is a TFTP path, not a native path. Yes, in
    # practice for us they're the same. We always assume that the ARP HTYPE
    # (hardware type) that PXELINUX sends is Ethernet.
    return "ppc64el/pxelinux.cfg/{htype:02x}-{mac}".format(
        htype=ARP_HTYPE.ETHERNET, mac=mac)


def get_example_path_and_components():
    """Return a plausible path and its components.

    The path is intended to match `re_config_file`, and the components are
    the expected groups from a match.
    """
    components = {"mac": factory.getRandomMACAddress("-")}
    config_path = compose_config_path(components["mac"])
    return config_path, components


class TestPowerNVBootMethod(MAASTestCase):

    def make_tftp_root(self):
        """Set, and return, a temporary TFTP root directory."""
        tftproot = self.make_dir()
        self.useFixture(set_tftp_root(tftproot))
        return tftproot

    def test_compose_config_path_follows_maas_pxe_directory_layout(self):
        name = factory.make_name('config')
        self.assertEqual(
            'ppc64el/pxelinux.cfg/%02x-%s' % (ARP_HTYPE.ETHERNET, name),
            compose_config_path(name))

    def test_compose_config_path_does_not_include_tftp_root(self):
        tftproot = self.make_tftp_root()
        name = factory.make_name('config')
        self.assertThat(
            compose_config_path(name),
            Not(StartsWith(tftproot)))

    def test_bootloader_path(self):
        method = PowerNVBootMethod()
        self.assertEqual('pxelinux.0', method.bootloader_path)

    def test_bootloader_path_does_not_include_tftp_root(self):
        tftproot = self.make_tftp_root()
        method = PowerNVBootMethod()
        self.assertThat(
            method.bootloader_path,
            Not(StartsWith(tftproot)))

    def test_name(self):
        method = PowerNVBootMethod()
        self.assertEqual('powernv', method.name)

    def test_template_subdir(self):
        method = PowerNVBootMethod()
        self.assertEqual('pxe', method.template_subdir)

    def test_arch_octet(self):
        method = PowerNVBootMethod()
        self.assertEqual('00:0E', method.arch_octet)

    def test_path_prefix(self):
        method = PowerNVBootMethod()
        self.assertEqual('ppc64el/', method.path_prefix)


class TestPowerNVBootMethodMatchPath(MAASTestCase):
    """Tests for
    `provisioningserver.boot.powernv.PowerNVBootMethod.match_path`.
    """

    def test_match_path_pxe_config_with_mac(self):
        method = PowerNVBootMethod()
        config_path, expected = get_example_path_and_components()
        params = method.match_path(None, config_path)
        expected['arch'] = 'ppc64el'
        self.assertEqual(expected, params)

    def test_match_path_pxe_config_without_mac(self):
        method = PowerNVBootMethod()
        fake_mac = factory.getRandomMACAddress()
        self.patch(powernv_module, 'get_remote_mac').return_value = fake_mac
        config_path = 'ppc64el/pxelinux.cfg/default'
        params = method.match_path(None, config_path)
        expected = {
            'arch': 'ppc64el',
            'mac': fake_mac,
            }
        self.assertEqual(expected, params)

    def test_match_path_pxe_prefix_request(self):
        method = PowerNVBootMethod()
        fake_mac = factory.getRandomMACAddress()
        self.patch(powernv_module, 'get_remote_mac').return_value = fake_mac
        file_path = 'ppc64el/file'
        params = method.match_path(None, file_path)
        expected = {
            'arch': 'ppc64el',
            'mac': fake_mac,
            'path': file_path,
            }
        self.assertEqual(expected, params)


class TestPowerNVBootMethodRenderConfig(MAASTestCase):
    """Tests for
    `provisioningserver.boot.powernv.PowerNVBootMethod.get_reader`
    """

    def test_get_reader_install(self):
        # Given the right configuration options, the PXE configuration is
        # correctly rendered.
        method = PowerNVBootMethod()
        params = make_kernel_parameters(self, purpose="install")
        output = method.get_reader(backend=None, kernel_params=params)
        # The output is a BytesReader.
        self.assertThat(output, IsInstance(BytesReader))
        output = output.read(10000)
        # The template has rendered without error. PXELINUX configurations
        # typically start with a DEFAULT line.
        self.assertThat(output, StartsWith("DEFAULT "))
        # The PXE parameters are all set according to the options.
        image_dir = compose_image_path(
            osystem=params.osystem, arch=params.arch, subarch=params.subarch,
            release=params.release, label=params.label)
        self.assertThat(
            output, MatchesAll(
                MatchesRegex(
                    r'.*^\s+KERNEL %s/di-kernel$' % re.escape(image_dir),
                    re.MULTILINE | re.DOTALL),
                MatchesRegex(
                    r'.*^\s+INITRD %s/di-initrd$' % re.escape(image_dir),
                    re.MULTILINE | re.DOTALL),
                MatchesRegex(
                    r'.*^\s+APPEND .+?$',
                    re.MULTILINE | re.DOTALL)))

    def test_get_reader_with_extra_arguments_does_not_affect_output(self):
        # get_reader() allows any keyword arguments as a safety valve.
        method = PowerNVBootMethod()
        options = {
            "backend": None,
            "kernel_params": make_kernel_parameters(self, purpose="install"),
        }
        # Capture the output before sprinking in some random options.
        output_before = method.get_reader(**options).read(10000)
        # Sprinkle some magic in.
        options.update(
            (factory.make_name("name"), factory.make_name("value"))
            for _ in range(10))
        # Capture the output after sprinking in some random options.
        output_after = method.get_reader(**options).read(10000)
        # The generated template is the same.
        self.assertEqual(output_before, output_after)

    def test_get_reader_with_local_purpose(self):
        # If purpose is "local", output should be empty string.
        method = PowerNVBootMethod()
        options = {
            "backend": None,
            "kernel_params": make_kernel_parameters(purpose="local"),
            }
        output = method.get_reader(**options).read(10000)
        self.assertIn("", output)

    def test_get_reader_appends_bootif(self):
        method = PowerNVBootMethod()
        fake_mac = factory.getRandomMACAddress()
        params = make_kernel_parameters(self, purpose="install")
        output = method.get_reader(
            backend=None, kernel_params=params, arch='ppc64el', mac=fake_mac)
        output = output.read(10000)
        config = parse_pxe_config(output)
        expected = 'BOOTIF=%s' % format_bootif(fake_mac)
        self.assertIn(expected, config['execute']['APPEND'])

    def test_format_bootif_replaces_colon(self):
        fake_mac = factory.getRandomMACAddress()
        self.assertEqual(
            '01-%s' % fake_mac.replace(':', '-').lower(),
            format_bootif(fake_mac))

    def test_format_bootif_makes_mac_address_lower(self):
        fake_mac = factory.getRandomMACAddress()
        fake_mac = fake_mac.upper()
        self.assertEqual(
            '01-%s' % fake_mac.replace(':', '-').lower(),
            format_bootif(fake_mac))


class TestPowerNVBootMethodPathPrefix(MAASTestCase):
    """Tests for
    `provisioningserver.boot.powernv.PowerNVBootMethod.get_reader`.
    """

    def test_get_reader_path_prefix(self):
        data = factory.getRandomString().encode("ascii")
        temp_file = self.make_file(name="example", contents=data)
        temp_dir = os.path.dirname(temp_file)
        backend = TFTPBackend(temp_dir, "http://nowhere.example.com/")
        method = PowerNVBootMethod()
        options = {
            'backend': backend,
            'kernel_params': make_kernel_parameters(),
            'path': 'ppc64el/example',
        }
        reader = method.get_reader(**options)
        self.addCleanup(reader.finish)
        self.assertEqual(len(data), reader.size)
        self.assertEqual(data, reader.read(len(data)))
        self.assertEqual(b"", reader.read(1))

    def test_get_reader_path_prefix_only_removes_first_occurrence(self):
        data = factory.getRandomString().encode("ascii")
        temp_dir = self.make_dir()
        temp_subdir = os.path.join(temp_dir, 'ppc64el')
        os.mkdir(temp_subdir)
        factory.make_file(temp_subdir, "example", data)
        backend = TFTPBackend(temp_dir, "http://nowhere.example.com/")
        method = PowerNVBootMethod()
        options = {
            'backend': backend,
            'kernel_params': make_kernel_parameters(),
            'path': 'ppc64el/ppc64el/example',
        }
        reader = method.get_reader(**options)
        self.addCleanup(reader.finish)
        self.assertEqual(len(data), reader.size)
        self.assertEqual(data, reader.read(len(data)))
        self.assertEqual(b"", reader.read(1))


class TestPowerNVBootMethodRegex(MAASTestCase):
    """Tests for
    `provisioningserver.boot.powernv.PowerNVBootMethod.re_config_file`.
    """

    def test_re_config_file_is_compatible_with_config_path_generator(self):
        # The regular expression for extracting components of the file path is
        # compatible with the PXE config path generator.
        for iteration in range(10):
            config_path, args = get_example_path_and_components()
            match = re_config_file.match(config_path)
            self.assertIsNotNone(match, config_path)
            self.assertEqual(args, match.groupdict())

    def test_re_config_file_with_leading_slash(self):
        # The regular expression for extracting components of the file path
        # doesn't care if there's a leading forward slash; the TFTP server is
        # easy on this point, so it makes sense to be also.
        config_path, args = get_example_path_and_components()
        # Ensure there's a leading slash.
        config_path = "/" + config_path.lstrip("/")
        match = re_config_file.match(config_path)
        self.assertIsNotNone(match, config_path)
        self.assertEqual(args, match.groupdict())

    def test_re_config_file_without_leading_slash(self):
        # The regular expression for extracting components of the file path
        # doesn't care if there's no leading forward slash; the TFTP server is
        # easy on this point, so it makes sense to be also.
        config_path, args = get_example_path_and_components()
        # Ensure there's no leading slash.
        config_path = config_path.lstrip("/")
        match = re_config_file.match(config_path)
        self.assertIsNotNone(match, config_path)
        self.assertEqual(args, match.groupdict())

    def test_re_config_file_matches_classic_pxelinux_cfg(self):
        # The default config path is simply "pxelinux.cfg" (without
        # leading slash).  The regex matches this.
        mac = 'aa-bb-cc-dd-ee-ff'
        match = re_config_file.match('ppc64el/pxelinux.cfg/01-%s' % mac)
        self.assertIsNotNone(match)
        self.assertEqual({'mac': mac}, match.groupdict())

    def test_re_config_file_matches_pxelinux_cfg_with_leading_slash(self):
        mac = 'aa-bb-cc-dd-ee-ff'
        match = re_config_file.match('/ppc64el/pxelinux.cfg/01-%s' % mac)
        self.assertIsNotNone(match)
        self.assertEqual({'mac': mac}, match.groupdict())

    def test_re_config_file_does_not_match_non_config_file(self):
        self.assertIsNone(re_config_file.match('ppc64el/pxelinux.cfg/kernel'))

    def test_re_config_file_does_not_match_file_in_root(self):
        self.assertIsNone(re_config_file.match('01-aa-bb-cc-dd-ee-ff'))

    def test_re_config_file_does_not_match_file_not_in_pxelinux_cfg(self):
        self.assertIsNone(re_config_file.match('foo/01-aa-bb-cc-dd-ee-ff'))

    def test_re_config_file_with_default(self):
        match = re_config_file.match('ppc64el/pxelinux.cfg/default')
        self.assertIsNotNone(match)
        self.assertEqual({'mac': None}, match.groupdict())
