# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.boot.uefi`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import re

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.boot.tftppath import compose_image_path
from provisioningserver.boot.uefi import (
    re_config_file,
    UEFIBootMethod,
    )
from provisioningserver.tests.test_kernel_opts import make_kernel_parameters
from testtools.matchers import (
    IsInstance,
    MatchesAll,
    MatchesRegex,
    StartsWith,
    )


def compose_config_path(mac=None, arch=None, subarch=None):
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
        TFTP.
    """
    if mac is not None:
        return "grub/grub.cfg-{mac}".format(mac=mac)
    if arch is not None:
        if subarch is None:
            subarch = "generic"
        return "grub/grub.cfg-{arch}-{subarch}".format(
            arch=arch, subarch=subarch)
    return "grub/grub.cfg"


class TestRenderUEFIConfig(MAASTestCase):
    """Tests for `provisioningserver.boot.uefi.UEFIBootMethod`."""

    def test_render(self):
        # Given the right configuration options, the UEFI configuration is
        # correctly rendered.
        method = UEFIBootMethod()
        params = make_kernel_parameters(purpose="install")
        output = method.render_config(kernel_params=params)
        # The output is always a Unicode string.
        self.assertThat(output, IsInstance(unicode))
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

    def test_render_with_extra_arguments_does_not_affect_output(self):
        # render_config() allows any keyword arguments as a safety valve.
        method = UEFIBootMethod()
        options = {
            "kernel_params": make_kernel_parameters(purpose="install"),
        }
        # Capture the output before sprinking in some random options.
        output_before = method.render_config(**options)
        # Sprinkle some magic in.
        options.update(
            (factory.make_name("name"), factory.make_name("value"))
            for _ in range(10))
        # Capture the output after sprinking in some random options.
        output_after = method.render_config(**options)
        # The generated template is the same.
        self.assertEqual(output_before, output_after)

    def test_render_config_with_local_purpose(self):
        # If purpose is "local", the config.localboot.template should be
        # used.
        method = UEFIBootMethod()
        options = {
            "kernel_params": make_kernel_parameters(
                purpose="local", arch="amd64"),
            }
        output = method.render_config(**options)
        self.assertIn("configfile /efi/ubuntu/grub.cfg", output)


class TestUEFIBootMethodRegex(MAASTestCase):
    """Tests `provisioningserver.boot.uefi.UEFIBootMethod.re_config_file`."""

    @staticmethod
    def get_example_path_and_components():
        """Return a plausible UEFI path and its components.

        The path is intended to match `re_config_file`, and
        the components are the expected groups from a match.
        """
        components = {"mac": factory.getRandomMACAddress(":"),
                      "arch": None,
                      "subarch": None}
        config_path = compose_config_path(components["mac"])
        return config_path, components

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
        config_path = "/" + config_path.lstrip("/")
        match = re_config_file.match(config_path)
        self.assertIsNotNone(match, config_path)
        self.assertEqual(args, match.groupdict())

    def test_re_config_file_without_leading_slash(self):
        # The regular expression for extracting components of the file path
        # doesn't care if there's no leading forward slash; the TFTP server is
        # easy on this point, so it makes sense to be also.
        config_path, args = self.get_example_path_and_components()
        # Ensure there's no leading slash.
        config_path = config_path.lstrip("/")
        match = re_config_file.match(config_path)
        self.assertIsNotNone(match, config_path)
        self.assertEqual(args, match.groupdict())

    def test_re_config_file_matches_classic_grub_cfg(self):
        # The default config path is simply "grub.cfg-{mac}" (without
        # leading slash).  The regex matches this.
        mac = 'aa:bb:cc:dd:ee:ff'
        match = re_config_file.match('grub/grub.cfg-%s' % mac)
        self.assertIsNotNone(match)
        self.assertEqual({'mac': mac, 'arch': None, 'subarch': None},
                         match.groupdict())

    def test_re_config_file_matches_grub_cfg_with_leading_slash(self):
        mac = 'aa:bb:cc:dd:ee:ff'
        match = re_config_file.match(
            '/grub/grub.cfg-%s' % mac)
        self.assertIsNotNone(match)
        self.assertEqual({'mac': mac, 'arch': None, 'subarch': None},
                         match.groupdict())

    def test_re_config_file_does_not_match_default_grub_config_file(self):
        self.assertIsNone(re_config_file.match('grub/grub.cfg'))

    def test_re_config_file_with_default(self):
        match = re_config_file.match('grub/grub.cfg-default')
        self.assertIsNotNone(match)
        self.assertEqual(
            {'mac': None, 'arch': None, 'subarch': None},
            match.groupdict())

    def test_re_config_file_with_default_arch(self):
        arch = factory.make_name('arch', sep='')
        match = re_config_file.match('grub/grub.cfg-default-%s' % arch)
        self.assertIsNotNone(match)
        self.assertEqual(
            {'mac': None, 'arch': arch, 'subarch': None},
            match.groupdict())

    def test_re_config_file_with_default_arch_and_subarch(self):
        arch = factory.make_name('arch', sep='')
        subarch = factory.make_name('subarch', sep='')
        match = re_config_file.match(
            'grub/grub.cfg-default-%s-%s' % (arch, subarch))
        self.assertIsNotNone(match)
        self.assertEqual(
            {'mac': None, 'arch': arch, 'subarch': subarch},
            match.groupdict())
