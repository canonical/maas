# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the pxe boot method."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from collections import OrderedDict
import os
import re

from maastesting.factory import factory
from maastesting.matchers import MockCallsMatch
from maastesting.testcase import MAASTestCase
import mock
from provisioningserver import kernel_opts
from provisioningserver.boot import (
    BytesReader,
    pxe as pxe_module,
    )
from provisioningserver.boot.pxe import (
    ARP_HTYPE,
    BOOTLOADERS,
    PXEBootMethod,
    re_config_file,
    )
from provisioningserver.boot.tftppath import compose_image_path
from provisioningserver.testing.config import set_tftp_root
from provisioningserver.tests.test_kernel_opts import make_kernel_parameters
from testtools.matchers import (
    Contains,
    ContainsAll,
    IsInstance,
    MatchesAll,
    MatchesRegex,
    Not,
    SamePath,
    StartsWith,
    )


def compose_config_path(mac):
    """Compose the TFTP path for a PXE configuration file.

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
    return "pxelinux.cfg/{htype:02x}-{mac}".format(
        htype=ARP_HTYPE.ETHERNET, mac=mac)


class TestPXEBootMethod(MAASTestCase):

    def make_tftp_root(self):
        """Set, and return, a temporary TFTP root directory."""
        tftproot = self.make_dir()
        self.useFixture(set_tftp_root(tftproot))
        return tftproot

    def make_dummy_bootloader_sources(self, destination, loader_names):
        """install_bootloader requires real files to exist, this method
        creates them in the requested location.

        :return: list of created filenames
        """
        created = []
        for loader in loader_names:
            name = factory.make_file(destination, loader)
            created.append(name)
        return created

    def test_compose_config_path_follows_maas_pxe_directory_layout(self):
        name = factory.make_name('config')
        self.assertEqual(
            'pxelinux.cfg/%02x-%s' % (ARP_HTYPE.ETHERNET, name),
            compose_config_path(name))

    def test_compose_config_path_does_not_include_tftp_root(self):
        tftproot = self.make_tftp_root()
        name = factory.make_name('config')
        self.assertThat(
            compose_config_path(name),
            Not(StartsWith(tftproot)))

    def test_bootloader_path(self):
        method = PXEBootMethod()
        self.assertEqual('pxelinux.0', method.bootloader_path)

    def test_bootloader_path_does_not_include_tftp_root(self):
        tftproot = self.make_tftp_root()
        method = PXEBootMethod()
        self.assertThat(
            method.bootloader_path,
            Not(StartsWith(tftproot)))

    def test_name(self):
        method = PXEBootMethod()
        self.assertEqual('pxe', method.name)

    def test_template_subdir(self):
        method = PXEBootMethod()
        self.assertEqual('pxe', method.template_subdir)

    def test_arch_octet(self):
        method = PXEBootMethod()
        self.assertEqual('00:00', method.arch_octet)

    def test_locate_bootloader(self):
        # Put all the BOOTLOADERS except one in dir1, and the last in
        # dir2.
        dir1 = self.make_dir()
        dir2 = self.make_dir()
        dirs = [dir1, dir2]
        self.patch(pxe_module, "BOOTLOADER_DIRS", dirs)
        self.make_dummy_bootloader_sources(dir1, BOOTLOADERS[:-1])
        [displaced_loader] = self.make_dummy_bootloader_sources(
            dir2, BOOTLOADERS[-1:])
        method = PXEBootMethod()
        observed = method.locate_bootloader(BOOTLOADERS[-1])

        self.assertEqual(displaced_loader, observed)

    def test_locate_bootloader_returns_None_if_not_found(self):
        method = PXEBootMethod()
        self.assertIsNone(method.locate_bootloader("foo"))

    def test_install_bootloader_installs_to_destination(self):
        # Disable the symlink creation.
        self.patch(pxe_module, "SYSLINUX_DIRS", [])
        tftproot = self.make_tftp_root()
        source_dir = self.make_dir()
        self.patch(pxe_module, "BOOTLOADER_DIRS", [source_dir])
        self.make_dummy_bootloader_sources(source_dir, BOOTLOADERS)
        install_bootloader_call = self.patch(pxe_module, "install_bootloader")
        method = PXEBootMethod()
        method.install_bootloader(tftproot)

        expected = [
            mock.call(
                os.path.join(source_dir, bootloader),
                os.path.join(tftproot, bootloader)
            )
            for bootloader in BOOTLOADERS]
        self.assertThat(
            install_bootloader_call,
            MockCallsMatch(*expected))

    def test_locate_syslinux_dir_returns_dir(self):
        dir1 = self.make_dir()
        dir2 = self.make_dir()
        dirs = [dir1, dir2]
        self.patch(pxe_module, "SYSLINUX_DIRS", dirs)
        method = PXEBootMethod()
        found_dir = method.locate_syslinux_dir()
        self.assertEqual(dir1, found_dir)

    def test_install_bootloader_creates_symlink(self):
        # Disable the copying of the bootloaders.
        self.patch(pxe_module, "BOOTLOADERS", [])
        target_dir = self.make_dir()
        self.patch(pxe_module, "SYSLINUX_DIRS", [target_dir])
        tftproot = self.make_tftp_root()
        method = PXEBootMethod()
        method.install_bootloader(tftproot)
        syslinux_dir = os.path.join(tftproot, 'syslinux')
        self.assertThat(syslinux_dir, SamePath(target_dir))


def parse_pxe_config(text):
    """Parse a PXE config file.

    Returns a structure like the following, defining the sections::

      {"section_label": {"KERNEL": "...", "INITRD": "...", ...}, ...}

    Additionally, the returned dict - which is actually an `OrderedDict`, as
    are all mappings returned from this function - has a `header` attribute.
    This is an `OrderedDict` of the settings in the top part of the PXE config
    file, the part before any labelled sections.
    """
    result = OrderedDict()
    sections = re.split("^LABEL ", text, flags=re.MULTILINE)
    for index, section in enumerate(sections):
        elements = [
            line.split(None, 1) for line in section.splitlines()
            if line and not line.isspace()
            ]
        if index == 0:
            result.header = OrderedDict(elements)
        else:
            [label] = elements.pop(0)
            if label in result:
                raise AssertionError(
                    "Section %r already defined" % label)
            result[label] = OrderedDict(elements)
    return result


class TestParsePXEConfig(MAASTestCase):
    """Tests for `parse_pxe_config`."""

    def test_parse_with_no_header(self):
        config = parse_pxe_config("LABEL foo\nOPTION setting")
        self.assertEqual({"foo": {"OPTION": "setting"}}, config)
        self.assertEqual({}, config.header)

    def test_parse_with_no_labels(self):
        config = parse_pxe_config("OPTION setting")
        self.assertEqual({"OPTION": "setting"}, config.header)
        self.assertEqual({}, config)


class TestPXEBootMethodRender(MAASTestCase):
    """Tests for `provisioningserver.boot.pxe.PXEBootMethod.render`."""

    def test_get_reader_install(self):
        # Given the right configuration options, the PXE configuration is
        # correctly rendered.
        method = PXEBootMethod()
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

    def test_get_reader_install_mustang_dtb(self):
        # Architecture specific test.
        # Given the right configuration options, the PXE configuration is
        # correctly rendered for Mustang.
        method = PXEBootMethod()
        params = make_kernel_parameters(
            testcase=self, osystem="ubuntu", arch="arm64",
            subarch="xgene-uboot-mustang", purpose="install")
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
                    r'.*^\s+FDT %s/di-dtb$' % re.escape(image_dir),
                    re.MULTILINE | re.DOTALL),
                MatchesRegex(
                    r'.*^\s+APPEND .+?$',
                    re.MULTILINE | re.DOTALL)))

    def test_get_reader_xinstall_mustang_dtb(self):
        # Architecture specific test.
        # Given the right configuration options, the PXE configuration is
        # correctly rendered for Mustang.
        method = PXEBootMethod()
        params = make_kernel_parameters(
            testcase=self, osystem="ubuntu", arch="arm64",
            subarch="xgene-uboot-mustang", purpose="xinstall")
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
                    r'.*^\s+KERNEL %s/boot-kernel$' % re.escape(image_dir),
                    re.MULTILINE | re.DOTALL),
                MatchesRegex(
                    r'.*^\s+INITRD %s/boot-initrd$' % re.escape(image_dir),
                    re.MULTILINE | re.DOTALL),
                MatchesRegex(
                    r'.*^\s+FDT %s/boot-dtb$' % re.escape(image_dir),
                    re.MULTILINE | re.DOTALL),
                MatchesRegex(
                    r'.*^\s+APPEND .+?$',
                    re.MULTILINE | re.DOTALL)))

    def test_get_reader_with_extra_arguments_does_not_affect_output(self):
        # get_reader() allows any keyword arguments as a safety valve.
        method = PXEBootMethod()
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
        # If purpose is "local", the config.localboot.template should be
        # used.
        method = PXEBootMethod()
        options = {
            "backend": None,
            "kernel_params": make_kernel_parameters(purpose="local"),
            }
        output = method.get_reader(**options).read(10000)
        self.assertIn("LOCALBOOT 0", output)

    def test_get_reader_with_local_purpose_i386_arch(self):
        # Intel i386 is a special case and needs to use the chain.c32
        # loader as the LOCALBOOT PXE directive is unreliable.
        method = PXEBootMethod()
        options = {
            "backend": None,
            "kernel_params": make_kernel_parameters(
                arch="i386", purpose="local"),
        }
        output = method.get_reader(**options).read(10000)
        self.assertIn("chain.c32", output)
        self.assertNotIn("LOCALBOOT", output)

    def test_get_reader_with_local_purpose_amd64_arch(self):
        # Intel amd64 is a special case and needs to use the chain.c32
        # loader as the LOCALBOOT PXE directive is unreliable.
        method = PXEBootMethod()
        options = {
            "backend": None,
            "kernel_params": make_kernel_parameters(
                arch="amd64", purpose="local"),
        }
        output = method.get_reader(**options).read(10000)
        self.assertIn("chain.c32", output)
        self.assertNotIn("LOCALBOOT", output)


class TestPXEBootMethodRenderConfigScenarios(MAASTestCase):
    """Tests for `provisioningserver.boot.pxe.PXEBootMethod.render_config`."""

    scenarios = [
        ("commissioning", dict(purpose="commissioning")),
        ("xinstall", dict(purpose="xinstall")),
        ]

    def test_get_reader_scenarios(self):
        method = PXEBootMethod()
        get_ephemeral_name = self.patch(kernel_opts, "get_ephemeral_name")
        get_ephemeral_name.return_value = factory.make_name("ephemeral")
        osystem = factory.make_name('osystem')
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        options = {
            "backend": None,
            "kernel_params": make_kernel_parameters(
                testcase=self, osystem=osystem, subarch=subarch,
                arch=arch, purpose=self.purpose),
        }
        output = method.get_reader(**options).read(10000)
        config = parse_pxe_config(output)
        # The default section is defined.
        default_section_label = config.header["DEFAULT"]
        self.assertThat(config, Contains(default_section_label))
        default_section = dict(config[default_section_label])

        contains_arch_path = StartsWith("%s/%s/%s" % (osystem, arch, subarch))
        self.assertThat(default_section["KERNEL"], contains_arch_path)
        self.assertThat(default_section["INITRD"], contains_arch_path)
        self.assertEquals("2", default_section["IPAPPEND"])


class TestPXEBootMethodRenderConfigScenariosEnlist(MAASTestCase):

    def test_get_reader_scenarios(self):
        # The commissioning config uses an extra PXELINUX module to auto
        # select between i386 and amd64.
        method = PXEBootMethod()
        get_ephemeral_name = self.patch(kernel_opts, "get_ephemeral_name")
        get_ephemeral_name.return_value = factory.make_name("ephemeral")
        osystem = factory.make_name('osystem')
        options = {
            "backend": None,
            "kernel_params": make_kernel_parameters(
                testcase=self, osystem=osystem, subarch="generic",
                purpose='enlist'),
        }
        output = method.get_reader(**options).read(10000)
        config = parse_pxe_config(output)
        # The default section is defined.
        default_section_label = config.header["DEFAULT"]
        self.assertThat(config, Contains(default_section_label))
        default_section = config[default_section_label]
        # The default section uses the ifcpu64 module, branching to the "i386"
        # or "amd64" labels accordingly.
        self.assertEqual("ifcpu64.c32", default_section["KERNEL"])
        self.assertEqual(
            ["amd64", "--", "i386"],
            default_section["APPEND"].split())
        # Both "i386" and "amd64" sections exist.
        self.assertThat(config, ContainsAll(("i386", "amd64")))
        # Each section defines KERNEL, INITRD, and APPEND settings.  The
        # KERNEL and INITRD ones contain paths referring to their
        # architectures.
        for section_label in ("i386", "amd64"):
            section = config[section_label]
            self.assertThat(
                section, ContainsAll(("KERNEL", "INITRD", "APPEND")))
            contains_arch_path = StartsWith(
                "%s/%s/" % (osystem, section_label))
            self.assertThat(section["KERNEL"], contains_arch_path)
            self.assertThat(section["INITRD"], contains_arch_path)
            self.assertIn("APPEND", section)


class TestPXEBootMethodRegex(MAASTestCase):
    """Tests for `provisioningserver.boot.pxe.PXEBootMethod.re_config_file`."""

    @staticmethod
    def get_example_path_and_components():
        """Return a plausible path and its components.

        The path is intended to match `re_config_file`, and the components are
        the expected groups from a match.
        """
        components = {"mac": factory.make_mac_address("-"),
                      "arch": None,
                      "subarch": None}
        config_path = compose_config_path(components["mac"])
        return config_path, components

    def test_re_config_file_is_compatible_with_config_path_generator(self):
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

    def test_re_config_file_matches_classic_pxelinux_cfg(self):
        # The default config path is simply "pxelinux.cfg" (without
        # leading slash).  The regex matches this.
        mac = 'aa-bb-cc-dd-ee-ff'
        match = re_config_file.match('pxelinux.cfg/01-%s' % mac)
        self.assertIsNotNone(match)
        self.assertEqual({'mac': mac, 'arch': None, 'subarch': None},
                         match.groupdict())

    def test_re_config_file_matches_pxelinux_cfg_with_leading_slash(self):
        mac = 'aa-bb-cc-dd-ee-ff'
        match = re_config_file.match('/pxelinux.cfg/01-%s' % mac)
        self.assertIsNotNone(match)
        self.assertEqual({'mac': mac, 'arch': None, 'subarch': None},
                         match.groupdict())

    def test_re_config_file_does_not_match_non_config_file(self):
        self.assertIsNone(re_config_file.match('pxelinux.cfg/kernel'))

    def test_re_config_file_does_not_match_file_in_root(self):
        self.assertIsNone(re_config_file.match('01-aa-bb-cc-dd-ee-ff'))

    def test_re_config_file_does_not_match_file_not_in_pxelinux_cfg(self):
        self.assertIsNone(re_config_file.match('foo/01-aa-bb-cc-dd-ee-ff'))

    def test_re_config_file_with_default(self):
        match = re_config_file.match('pxelinux.cfg/default')
        self.assertIsNotNone(match)
        self.assertEqual(
            {'mac': None, 'arch': None, 'subarch': None},
            match.groupdict())

    def test_re_config_file_with_default_arch(self):
        arch = factory.make_name('arch', sep='')
        match = re_config_file.match('pxelinux.cfg/default.%s' % arch)
        self.assertIsNotNone(match)
        self.assertEqual(
            {'mac': None, 'arch': arch, 'subarch': None},
            match.groupdict())

    def test_re_config_file_with_default_arch_and_subarch(self):
        arch = factory.make_name('arch', sep='')
        subarch = factory.make_name('subarch', sep='')
        match = re_config_file.match(
            'pxelinux.cfg/default.%s-%s' % (arch, subarch))
        self.assertIsNotNone(match)
        self.assertEqual(
            {'mac': None, 'arch': arch, 'subarch': subarch},
            match.groupdict())
