# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.boot.uefi`."""

__all__ = []

from contextlib import contextmanager
import os
import re

from maastesting.factory import factory
from maastesting.matchers import MockCallsMatch
from maastesting.testcase import MAASTestCase
from mock import call
from provisioningserver.boot import (
    BootMethodInstallError,
    BytesReader,
    uefi as uefi_module,
    utils,
)
from provisioningserver.boot.testing import (
    TFTPPath,
    TFTPPathAndComponents,
)
from provisioningserver.boot.tftppath import compose_image_path
from provisioningserver.boot.uefi import (
    re_config_file,
    UEFIBootMethod,
)
from provisioningserver.tests.test_kernel_opts import make_kernel_parameters
from provisioningserver.utils import typed
from testtools.matchers import (
    ContainsAll,
    IsInstance,
    MatchesAll,
    MatchesRegex,
    StartsWith,
)


@typed
def compose_config_path(
        mac: str=None, arch: str=None, subarch: str=None) -> TFTPPath:
    """Compose the TFTP path for a UEFI configuration file.

    The path returned is relative to the TFTP root, as it would be
    identified by clients on the network.

    :param mac: A MAC address, in IEEE 802 colon-separated form,
        corresponding to the machine for which this configuration is
        relevant.
    :param arch: Architecture for the booting machine, for UEFI this is
        always amd64.
    :param subarch: Sub-architecture type, this is normally always generic.
    :return: Path for the corresponding PXE config file as exposed over
        TFTP, as a byte string.
    """
    if mac is not None:
        return "grub/grub.cfg-{mac}".format(mac=mac).encode("ascii")
    if arch is not None:
        if subarch is None:
            subarch = "generic"
        return "grub/grub.cfg-{arch}-{subarch}".format(
            arch=arch, subarch=subarch).encode("ascii")
    return "grub/grub.cfg".encode("ascii")


class TestUEFIBootMethodRender(MAASTestCase):
    """Tests for `provisioningserver.boot.uefi.UEFIBootMethod.render`."""

    def test_get_reader(self):
        # Given the right configuration options, the UEFI configuration is
        # correctly rendered.
        method = UEFIBootMethod()
        params = make_kernel_parameters(purpose="install")
        output = method.get_reader(backend=None, kernel_params=params)
        # The output is a BytesReader.
        self.assertThat(output, IsInstance(BytesReader))
        output = output.read(10000).decode("utf-8")
        # The template has rendered without error. UEFI configurations
        # typically start with a DEFAULT line.
        self.assertThat(output, StartsWith("set default=\"0\""))
        # The UEFI parameters are all set according to the options.
        image_dir = compose_image_path(
            osystem=params.osystem, arch=params.arch, subarch=params.subarch,
            release=params.release, label=params.label)

        self.assertThat(
            output, MatchesAll(
                MatchesRegex(
                    r'.*^\s+linux  %s/di-kernel .+?$' % re.escape(image_dir),
                    re.MULTILINE | re.DOTALL),
                MatchesRegex(
                    r'.*^\s+initrd %s/di-initrd$' % re.escape(image_dir),
                    re.MULTILINE | re.DOTALL)))

    def test_get_reader_with_extra_arguments_does_not_affect_output(self):
        # get_reader() allows any keyword arguments as a safety valve.
        method = UEFIBootMethod()
        options = {
            "backend": None,
            "kernel_params": make_kernel_parameters(purpose="install"),
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
        # If purpose is "local", the config.localboot.template should be
        # used.
        method = UEFIBootMethod()
        options = {
            "backend": None,
            "kernel_params": make_kernel_parameters(
                purpose="local", arch="amd64"),
            }
        output = method.get_reader(**options).read(10000).decode("utf-8")
        self.assertIn("chainloader /efi/ubuntu/shimx64.efi", output)

    def test_get_reader_with_enlist_purpose(self):
        # If purpose is "enlist", the config.enlist.template should be
        # used.
        method = UEFIBootMethod()
        params = make_kernel_parameters(
            purpose="enlist", arch="amd64")
        options = {
            "backend": None,
            "kernel_params": params,
            }
        output = method.get_reader(**options).read(10000).decode("utf-8")
        self.assertThat(output, ContainsAll(
            [
                "menuentry 'Enlist'",
                "%s/%s/%s" % (params.osystem, params.arch, params.subarch),
                "boot-kernel",
            ]))

    def test_get_reader_with_commissioning_purpose(self):
        # If purpose is "commissioning", the config.commissioning.template
        # should be used.
        method = UEFIBootMethod()
        params = make_kernel_parameters(
            purpose="commissioning", arch="amd64")
        options = {
            "backend": None,
            "kernel_params": params,
            }
        output = method.get_reader(**options).read(10000).decode("utf-8")
        self.assertThat(output, ContainsAll(
            [
                "menuentry 'Commission'",
                "%s/%s/%s" % (params.osystem, params.arch, params.subarch),
                "boot-kernel",
            ]))


class TestUEFIBootMethodRegex(MAASTestCase):
    """Tests `provisioningserver.boot.uefi.UEFIBootMethod.re_config_file`."""

    @staticmethod
    @typed
    def get_example_path_and_components() -> TFTPPathAndComponents:
        """Return a plausible UEFI path and its components.

        The path is intended to match `re_config_file`, and
        the components are the expected groups from a match.
        """
        mac = factory.make_mac_address(":")
        return compose_config_path(mac), {
            "mac": mac.encode("ascii"), "arch": None, "subarch": None}

    def test_re_config_file_is_compatible_with_cfg_path_generator(self):
        # The regular expression for extracting components of the file path is
        # compatible with the PXE config path generator.
        for iteration in range(10):
            config_path, args = self.get_example_path_and_components()
            match = re_config_file.match(config_path)
            self.assertIsNotNone(match, config_path)
            self.assertEqual(args, match.groupdict())

    def test_re_config_file_with_leading_slash(self):
        # The regular expression for extracting components of the file path
        # doesn't care if there's a leading forward slash; the TFTP server is
        # easy on this point, so it makes sense to be also.
        config_path, args = self.get_example_path_and_components()
        # Ensure there's a leading slash.
        config_path = b"/" + config_path.lstrip(b"/")
        match = re_config_file.match(config_path)
        self.assertIsNotNone(match, config_path)
        self.assertEqual(args, match.groupdict())

    def test_re_config_file_without_leading_slash(self):
        # The regular expression for extracting components of the file path
        # doesn't care if there's no leading forward slash; the TFTP server is
        # easy on this point, so it makes sense to be also.
        config_path, args = self.get_example_path_and_components()
        # Ensure there's no leading slash.
        config_path = config_path.lstrip(b"/")
        match = re_config_file.match(config_path)
        self.assertIsNotNone(match, config_path)
        self.assertEqual(args, match.groupdict())

    def test_re_config_file_matches_classic_grub_cfg(self):
        # The default config path is simply "grub.cfg-{mac}" (without
        # leading slash).  The regex matches this.
        mac = b'aa:bb:cc:dd:ee:ff'
        match = re_config_file.match(b'grub/grub.cfg-%s' % mac)
        self.assertIsNotNone(match)
        self.assertEqual(
            {'mac': mac, 'arch': None, 'subarch': None},
            match.groupdict())

    def test_re_config_file_matches_grub_cfg_with_leading_slash(self):
        mac = b'aa:bb:cc:dd:ee:ff'
        match = re_config_file.match(b'/grub/grub.cfg-%s' % mac)
        self.assertIsNotNone(match)
        self.assertEqual(
            {'mac': mac, 'arch': None, 'subarch': None},
            match.groupdict())

    def test_re_config_file_does_not_match_default_grub_config_file(self):
        self.assertIsNone(re_config_file.match(b'grub/grub.cfg'))

    def test_re_config_file_with_default(self):
        match = re_config_file.match(b'grub/grub.cfg-default')
        self.assertIsNotNone(match)
        self.assertEqual(
            {'mac': None, 'arch': None, 'subarch': None},
            match.groupdict())

    def test_re_config_file_with_default_arch(self):
        arch = factory.make_name('arch', sep='').encode("ascii")
        match = re_config_file.match(b'grub/grub.cfg-default-%s' % arch)
        self.assertIsNotNone(match)
        self.assertEqual(
            {'mac': None, 'arch': arch, 'subarch': None},
            match.groupdict())

    def test_re_config_file_with_default_arch_and_subarch(self):
        arch = factory.make_name('arch', sep='').encode("ascii")
        subarch = factory.make_name('subarch', sep='').encode("ascii")
        match = re_config_file.match(
            b'grub/grub.cfg-default-%s-%s' % (arch, subarch))
        self.assertIsNotNone(match)
        self.assertEqual(
            {'mac': None, 'arch': arch, 'subarch': subarch},
            match.groupdict())


class TestUEFIBootMethod(MAASTestCase):
    """Tests `provisioningserver.boot.uefi.UEFIBootMethod`."""

    def test_install_bootloader_get_package_raises_error(self):
        method = UEFIBootMethod()
        self.patch(uefi_module, 'get_main_archive_url')
        self.patch(utils, 'get_updates_package').return_value = (None, None)
        self.assertRaises(
            BootMethodInstallError, method.install_bootloader, "bogus")

    def test_install_bootloader(self):
        method = UEFIBootMethod()
        shim_filename = factory.make_name('shim-signed')
        shim_data = factory.make_bytes()
        grub_filename = factory.make_name('grub-efi-amd64-signed')
        grub_data = factory.make_bytes()
        tmp = self.make_dir()
        dest = self.make_dir()

        @contextmanager
        def tempdir():
            try:
                yield tmp
            finally:
                pass

        mock_get_main_archive_url = self.patch(
            uefi_module, 'get_main_archive_url')
        mock_get_main_archive_url.return_value = 'http://archive.ubuntu.com'
        mock_get_updates_package = self.patch(utils, 'get_updates_package')
        mock_get_updates_package.side_effect = [
            (shim_data, shim_filename),
            (grub_data, grub_filename),
            ]
        self.patch(uefi_module, 'call_and_check')
        self.patch(uefi_module, 'tempdir').side_effect = tempdir

        mock_install_bootloader = self.patch(
            uefi_module, 'install_bootloader')

        method.install_bootloader(dest)

        with open(os.path.join(tmp, shim_filename), 'rb') as stream:
            saved_shim_data = stream.read()
        self.assertEqual(shim_data, saved_shim_data)

        with open(os.path.join(tmp, grub_filename), 'rb') as stream:
            saved_grub_data = stream.read()
        self.assertEqual(grub_data, saved_grub_data)

        shim_expected = os.path.join(
            tmp, "usr", "lib", "shim", "shim.efi.signed")
        shim_dest_expected = os.path.join(dest, method.bootloader_path)
        grub_expected = os.path.join(
            tmp, "usr", "lib", "grub", "x86_64-efi-signed",
            "grubnetx64.efi.signed")
        grub_dest_expected = os.path.join(dest, "grubx64.efi")
        self.assertThat(
            mock_install_bootloader,
            MockCallsMatch(
                call(shim_expected, shim_dest_expected),
                call(grub_expected, grub_dest_expected)))
