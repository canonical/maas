# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the pxe boot method."""


from collections import OrderedDict
import os
import re

from testtools.matchers import (
    ContainsAll,
    MatchesAll,
    MatchesRegex,
    Not,
    StartsWith,
)
from twisted.python.filepath import FilePath

from maastesting.factory import factory
from maastesting.matchers import MockAnyCall, MockNotCalled
from maastesting.testcase import MAASTestCase
from provisioningserver import kernel_opts
from provisioningserver.boot import BytesReader
from provisioningserver.boot import pxe as pxe_module
from provisioningserver.boot.pxe import (
    ARP_HTYPE,
    maaslog,
    PXEBootMethod,
    re_config_file,
)
from provisioningserver.boot.testing import TFTPPath, TFTPPathAndComponents
from provisioningserver.boot.tftppath import compose_image_path
from provisioningserver.testing.config import ClusterConfigurationFixture
from provisioningserver.tests.test_kernel_opts import make_kernel_parameters
from provisioningserver.utils.fs import atomic_symlink, tempdir
from provisioningserver.utils.network import convert_host_to_uri_str


def compose_config_path(mac: str) -> TFTPPath:
    """Compose the TFTP path for a PXE configuration file.

    The path returned is relative to the TFTP root, as it would be
    identified by clients on the network.

    :param mac: A MAC address, in IEEE 802 hyphen-separated form,
        corresponding to the machine for which this configuration is
        relevant. This relates to PXELINUX's lookup protocol.
    :return: Path for the corresponding PXE config file as exposed over
        TFTP, as a byte string.
    """
    # Not using os.path.join: this is a TFTP path, not a native path. Yes, in
    # practice for us they're the same. We always assume that the ARP HTYPE
    # (hardware type) that PXELINUX sends is Ethernet.
    return "pxelinux.cfg/{htype:02x}-{mac}".format(
        htype=ARP_HTYPE.ETHERNET, mac=mac
    ).encode("ascii")


class TestPXEBootMethod(MAASTestCase):
    def make_tftp_root(self):
        """Set, and return, a temporary TFTP root directory."""
        tftproot = self.make_dir()
        self.useFixture(ClusterConfigurationFixture(tftp_root=tftproot))
        return FilePath(tftproot)

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
        mac = factory.make_mac_address("-")
        self.assertEqual(
            f"pxelinux.cfg/{ARP_HTYPE.ETHERNET:02x}-{mac}",
            compose_config_path(mac).decode("ascii"),
        )

    def test_compose_config_path_does_not_include_tftp_root(self):
        tftproot = self.make_tftp_root().asBytesMode()
        mac = factory.make_mac_address("-")
        self.assertThat(
            compose_config_path(mac), Not(StartsWith(tftproot.path))
        )

    def test_bootloader_path(self):
        method = PXEBootMethod()
        self.assertEqual("lpxelinux.0", method.bootloader_path)

    def test_bootloader_path_does_not_include_tftp_root(self):
        tftproot = self.make_tftp_root()
        method = PXEBootMethod()
        self.assertThat(method.bootloader_path, Not(StartsWith(tftproot.path)))

    def test_name(self):
        method = PXEBootMethod()
        self.assertEqual("pxe", method.name)

    def test_template_subdir(self):
        method = PXEBootMethod()
        self.assertEqual("pxe", method.template_subdir)

    def test_arch_octet(self):
        method = PXEBootMethod()
        self.assertEqual("00:00", method.arch_octet)

    def test_link_simplestream_bootloaders_creates_syslinux_link(self):
        method = PXEBootMethod()
        with tempdir() as tmp:
            stream_path = os.path.join(
                tmp,
                "bootloader",
                method.bios_boot_method,
                method.bootloader_arches[0],
            )
            os.makedirs(stream_path)
            for bootloader_file in method.bootloader_files:
                factory.make_file(stream_path, bootloader_file)

            method.link_bootloader(tmp)

            for bootloader_file in method.bootloader_files:
                bootloader_file_path = os.path.join(tmp, bootloader_file)
                self.assertTrue(os.path.islink(bootloader_file_path))
            syslinux_link = os.path.join(tmp, "syslinux")
            self.assertTrue(os.path.islink(syslinux_link))
            self.assertEqual(stream_path, os.path.realpath(syslinux_link))

    def test_link_simplestream_bootloaders_creates_lpxelinux_and_links(self):
        method = PXEBootMethod()
        with tempdir() as tmp:
            stream_path = os.path.join(
                tmp,
                "bootloader",
                method.bios_boot_method,
                method.bootloader_arches[0],
            )
            os.makedirs(stream_path)
            for bootloader_file in method.bootloader_files:
                factory.make_file(stream_path, bootloader_file)

            method.link_bootloader(tmp)

            self.assertTrue(os.path.exists(os.path.join(tmp, "lpxelinux.0")))
            self.assertTrue(os.path.islink(os.path.join(tmp, "pxelinux.0")))

    def test_link_bootloader_copies_previously_downloaded_files(self):
        method = PXEBootMethod()
        with tempdir() as tmp:
            new_dir = os.path.join(tmp, "new")
            current_dir = os.path.join(tmp, "current")
            os.makedirs(new_dir)
            os.makedirs(current_dir)
            factory.make_file(current_dir, method.bootloader_files[0])
            for bootloader_file in method.bootloader_files[1:]:
                factory.make_file(current_dir, bootloader_file)
            real_syslinux_dir = os.path.join(tmp, "syslinux")
            os.makedirs(real_syslinux_dir)
            atomic_symlink(
                real_syslinux_dir, os.path.join(current_dir, "syslinux")
            )

            method.link_bootloader(new_dir)

            for bootloader_file in method.bootloader_files:
                bootloader_file_path = os.path.join(new_dir, bootloader_file)
                self.assertTrue(os.path.isfile(bootloader_file_path))
            syslinux_link = os.path.join(new_dir, "syslinux")
            self.assertTrue(os.path.islink(syslinux_link))
            self.assertEqual(
                real_syslinux_dir, os.path.realpath(syslinux_link)
            )

    def test_link_bootloader_links_files_found_on_fs(self):
        method = PXEBootMethod()
        bootloader_dir = (
            "/var/lib/maas/boot-resources/snapshot-%s"
            % factory.make_name("snapshot")
        )

        def fake_exists(path):
            if "/usr/lib/syslinux/modules/bios" in path:
                return True
            else:
                return False

        self.patch(pxe_module.os.path, "exists").side_effect = fake_exists
        mock_atomic_copy = self.patch(pxe_module, "atomic_copy")
        mock_atomic_symlink = self.patch(pxe_module, "atomic_symlink")
        mock_shutil_copy = self.patch(pxe_module.shutil, "copy")

        method.link_bootloader(bootloader_dir)

        self.assertThat(mock_atomic_copy, MockNotCalled())
        self.assertThat(mock_shutil_copy, MockNotCalled())
        for bootloader_file in method.bootloader_files:
            bootloader_src = os.path.join(
                "/usr/lib/syslinux/modules/bios", bootloader_file
            )
            bootloader_dst = os.path.join(bootloader_dir, bootloader_file)
            self.assertThat(
                mock_atomic_symlink,
                MockAnyCall(bootloader_src, bootloader_dst),
            )
        self.assertThat(
            mock_atomic_symlink,
            MockAnyCall(
                "/usr/lib/syslinux/modules/bios",
                os.path.join(bootloader_dir, "syslinux"),
            ),
        )

    def test_link_bootloader_logs_missing_files(self):
        method = PXEBootMethod()
        mock_maaslog = self.patch(maaslog, "error")
        # If we don't mock the return value and the test system has the
        # pxelinux and syslinux-common package installed the fallback kicks
        # which makes PXE work but this test fail.
        self.patch(os.path, "exists").return_value = False
        self.patch(pxe_module, "atomic_symlink")
        method.link_bootloader("foo")
        self.assertTrue(mock_maaslog.called)


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
            line.split(None, 1)
            for line in section.splitlines()
            if line and not line.isspace()
        ]
        if index == 0:
            result.header = OrderedDict(elements)
        else:
            [label] = elements.pop(0)
            if label in result:
                raise AssertionError("Section %r already defined" % label)
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
        params = make_kernel_parameters(self, purpose="xinstall")
        fs_host = "http://%s:5248/images" % (
            convert_host_to_uri_str(params.fs_host)
        )
        output = method.get_reader(backend=None, kernel_params=params)
        # The output is a BytesReader.
        self.assertIsInstance(output, BytesReader)
        output = output.read(10000).decode("utf-8")
        # The template has rendered without error. PXELINUX configurations
        # typically start with a DEFAULT line.
        self.assertThat(output, StartsWith("DEFAULT "))
        # The PXE parameters are all set according to the options.
        image_dir = compose_image_path(
            osystem=params.osystem,
            arch=params.arch,
            subarch=params.subarch,
            release=params.release,
            label=params.label,
        )
        self.assertThat(
            output,
            MatchesAll(
                MatchesRegex(
                    r".*^\s+KERNEL %s/%s/%s$"
                    % (
                        re.escape(fs_host),
                        re.escape(image_dir),
                        params.kernel,
                    ),
                    re.MULTILINE | re.DOTALL,
                ),
                MatchesRegex(
                    r".*^\s+INITRD %s/%s/%s$"
                    % (
                        re.escape(fs_host),
                        re.escape(image_dir),
                        params.initrd,
                    ),
                    re.MULTILINE | re.DOTALL,
                ),
                MatchesRegex(r".*^\s+APPEND .+?$", re.MULTILINE | re.DOTALL),
            ),
        )

    def test_get_reader_install_mustang_dtb(self):
        # Architecture specific test.
        # Given the right configuration options, the PXE configuration is
        # correctly rendered for Mustang.
        method = PXEBootMethod()
        params = make_kernel_parameters(
            testcase=self,
            osystem="ubuntu",
            arch="arm64",
            subarch="xgene-uboot-mustang",
            purpose="xinstall",
        )
        output = method.get_reader(backend=None, kernel_params=params)
        # The output is a BytesReader.
        self.assertIsInstance(output, BytesReader)
        output = output.read(10000).decode("utf-8")
        # The template has rendered without error. PXELINUX configurations
        # typically start with a DEFAULT line.
        self.assertThat(output, StartsWith("DEFAULT "))
        # The PXE parameters are all set according to the options.
        image_dir = compose_image_path(
            osystem=params.osystem,
            arch=params.arch,
            subarch=params.subarch,
            release=params.release,
            label=params.label,
        )
        self.assertThat(
            output,
            MatchesAll(
                MatchesRegex(
                    r".*^\s+KERNEL %s/%s$"
                    % (re.escape(image_dir), params.kernel),
                    re.MULTILINE | re.DOTALL,
                ),
                MatchesRegex(
                    r".*^\s+INITRD %s/%s$"
                    % (re.escape(image_dir), params.initrd),
                    re.MULTILINE | re.DOTALL,
                ),
                MatchesRegex(
                    r".*^\s+FDT %s/%s$"
                    % (re.escape(image_dir), params.boot_dtb),
                    re.MULTILINE | re.DOTALL,
                ),
                MatchesRegex(r".*^\s+APPEND .+?$", re.MULTILINE | re.DOTALL),
            ),
        )

    def test_get_reader_xinstall_mustang_dtb(self):
        # Architecture specific test.
        # Given the right configuration options, the PXE configuration is
        # correctly rendered for Mustang.
        method = PXEBootMethod()
        params = make_kernel_parameters(
            testcase=self,
            osystem="ubuntu",
            arch="arm64",
            subarch="xgene-uboot-mustang",
            purpose="xinstall",
        )
        output = method.get_reader(backend=None, kernel_params=params)
        # The output is a BytesReader.
        self.assertIsInstance(output, BytesReader)
        output = output.read(10000).decode("utf-8")
        # The template has rendered without error. PXELINUX configurations
        # typically start with a DEFAULT line.
        self.assertThat(output, StartsWith("DEFAULT "))
        # The PXE parameters are all set according to the options.
        image_dir = compose_image_path(
            osystem=params.osystem,
            arch=params.arch,
            subarch=params.subarch,
            release=params.release,
            label=params.label,
        )
        self.assertThat(
            output,
            MatchesAll(
                MatchesRegex(
                    r".*^\s+KERNEL %s/%s$"
                    % (re.escape(image_dir), params.kernel),
                    re.MULTILINE | re.DOTALL,
                ),
                MatchesRegex(
                    r".*^\s+INITRD %s/%s$"
                    % (re.escape(image_dir), params.initrd),
                    re.MULTILINE | re.DOTALL,
                ),
                MatchesRegex(
                    r".*^\s+FDT %s/%s$"
                    % (re.escape(image_dir), params.boot_dtb),
                    re.MULTILINE | re.DOTALL,
                ),
                MatchesRegex(r".*^\s+APPEND .+?$", re.MULTILINE | re.DOTALL),
            ),
        )

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
            for _ in range(10)
        )
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
        self.assertIn(b"LOCALBOOT 0", output)

    def test_get_reader_with_local_purpose_i386_arch(self):
        # Intel i386 is a special case and needs to use the chain.c32
        # loader as the LOCALBOOT PXE directive is unreliable.
        method = PXEBootMethod()
        options = {
            "backend": None,
            "kernel_params": make_kernel_parameters(
                arch="i386", purpose="local"
            ),
        }
        output = method.get_reader(**options).read(10000)
        self.assertIn(b"chain.c32", output)
        self.assertNotIn(b"LOCALBOOT", output)

    def test_get_reader_with_local_purpose_amd64_arch(self):
        # Intel amd64 is a special case and needs to use the chain.c32
        # loader as the LOCALBOOT PXE directive is unreliable.
        method = PXEBootMethod()
        options = {
            "backend": None,
            "kernel_params": make_kernel_parameters(
                arch="amd64", purpose="local"
            ),
        }
        output = method.get_reader(**options).read(10000)
        self.assertIn(b"chain.c32", output)
        self.assertNotIn(b"LOCALBOOT", output)


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
        osystem = factory.make_name("osystem")
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        options = {
            "backend": None,
            "kernel_params": make_kernel_parameters(
                testcase=self,
                osystem=osystem,
                subarch=subarch,
                arch=arch,
                purpose=self.purpose,
            ),
        }
        fs_host = "http://%s:5248/images" % (
            convert_host_to_uri_str(options["kernel_params"].fs_host)
        )
        output = method.get_reader(**options).read(10000).decode("utf-8")
        config = parse_pxe_config(output)
        # The default section is defined.
        default_section_label = config.header["DEFAULT"]
        self.assertIn(default_section_label, config)
        default_section = dict(config[default_section_label])

        contains_arch_path = StartsWith(
            f"{fs_host}/{osystem}/{arch}/{subarch}"
        )
        self.assertThat(default_section["KERNEL"], contains_arch_path)
        self.assertThat(default_section["INITRD"], contains_arch_path)
        self.assertEqual("2", default_section["IPAPPEND"])


class TestPXEBootMethodRenderConfigScenariosEnlist(MAASTestCase):
    def test_get_reader_scenarios(self):
        # The commissioning config uses an extra PXELINUX module to auto
        # select between i386 and amd64.
        method = PXEBootMethod()
        get_ephemeral_name = self.patch(kernel_opts, "get_ephemeral_name")
        get_ephemeral_name.return_value = factory.make_name("ephemeral")
        osystem = factory.make_name("osystem")
        options = {
            "backend": None,
            "kernel_params": make_kernel_parameters(
                testcase=self,
                osystem=osystem,
                subarch="generic",
                purpose="enlist",
            ),
        }
        fs_host = "http://%s:5248/images" % (
            convert_host_to_uri_str(options["kernel_params"].fs_host)
        )
        output = method.get_reader(**options).read(10000).decode("utf-8")
        config = parse_pxe_config(output)
        # The default section is defined.
        default_section_label = config.header["DEFAULT"]
        self.assertIn(default_section_label, config)
        default_section = config[default_section_label]
        # The default section uses the ifcpu64 module, branching to the "i386"
        # or "amd64" labels accordingly.
        self.assertEqual("ifcpu64.c32", default_section["KERNEL"])
        self.assertEqual(
            ["amd64", "--", "i386"], default_section["APPEND"].split()
        )
        # Both "i386" and "amd64" sections exist.
        self.assertThat(config, ContainsAll(("i386", "amd64")))
        # Each section defines KERNEL, INITRD, and APPEND settings.  The
        # KERNEL and INITRD ones contain paths referring to their
        # architectures.
        for section_label in ("i386", "amd64"):
            section = config[section_label]
            self.assertThat(
                section, ContainsAll(("KERNEL", "INITRD", "APPEND"))
            )
            contains_arch_path = StartsWith(
                f"{fs_host}/{osystem}/{section_label}/"
            )
            self.assertThat(section["KERNEL"], contains_arch_path)
            self.assertThat(section["INITRD"], contains_arch_path)
            self.assertIn("APPEND", section)


class TestPXEBootMethodRegex(MAASTestCase):
    """Tests for `provisioningserver.boot.pxe.PXEBootMethod.re_config_file`."""

    @staticmethod
    def get_example_path_and_components() -> TFTPPathAndComponents:
        """Return a plausible path and its components.

        The path is intended to match `re_config_file`, and the components are
        the expected groups from a match.
        """
        mac = factory.make_mac_address("-")
        components = {
            "mac": mac.encode("ascii"),
            "hardware_uuid": None,
            "arch": None,
            "subarch": None,
        }
        config_path = compose_config_path(mac)
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

    def test_re_config_file_matches_classic_pxelinux_cfg(self):
        # The default config path is simply "pxelinux.cfg" (without
        # leading slash).  The regex matches this.
        mac = b"aa-bb-cc-dd-ee-ff"
        match = re_config_file.match(b"pxelinux.cfg/01-%s" % mac)
        self.assertIsNotNone(match)
        self.assertDictEqual(
            {"mac": mac, "hardware_uuid": None, "arch": None, "subarch": None},
            match.groupdict(),
        )

    def test_re_config_file_matches_pxelinux_cfg_with_leading_slash(self):
        mac = b"aa-bb-cc-dd-ee-ff"
        match = re_config_file.match(b"/pxelinux.cfg/01-%s" % mac)
        self.assertIsNotNone(match)
        self.assertDictEqual(
            {"mac": mac, "hardware_uuid": None, "arch": None, "subarch": None},
            match.groupdict(),
        )

    def test_re_config_file_matches_pxelinux_cfg_with_hardware_uuid(self):
        hardware_uuid = factory.make_UUID().encode()
        match = re_config_file.match(b"pxelinux.cfg/%s" % hardware_uuid)
        self.assertIsNotNone(match)
        self.assertDictEqual(
            {
                "mac": None,
                "hardware_uuid": hardware_uuid,
                "arch": None,
                "subarch": None,
            },
            match.groupdict(),
        )

    def test_re_config_file_does_not_match_non_config_file(self):
        self.assertIsNone(re_config_file.match(b"pxelinux.cfg/kernel"))

    def test_re_config_file_does_not_match_file_in_root(self):
        self.assertIsNone(re_config_file.match(b"01-aa-bb-cc-dd-ee-ff"))

    def test_re_config_file_does_not_match_file_not_in_pxelinux_cfg(self):
        self.assertIsNone(re_config_file.match(b"foo/01-aa-bb-cc-dd-ee-ff"))

    def test_re_config_file_with_default(self):
        match = re_config_file.match(b"pxelinux.cfg/default")
        self.assertIsNotNone(match)
        self.assertDictEqual(
            {
                "mac": None,
                "hardware_uuid": None,
                "arch": None,
                "subarch": None,
            },
            match.groupdict(),
        )

    def test_re_config_file_with_default_arch(self):
        arch = factory.make_name("arch", sep="").encode("ascii")
        match = re_config_file.match(b"pxelinux.cfg/default.%s" % arch)
        self.assertIsNotNone(match)
        self.assertDictEqual(
            {
                "mac": None,
                "hardware_uuid": None,
                "arch": arch,
                "subarch": None,
            },
            match.groupdict(),
        )

    def test_re_config_file_with_default_arch_and_subarch(self):
        arch = factory.make_name("arch", sep="").encode("ascii")
        subarch = factory.make_name("subarch", sep="").encode("ascii")
        match = re_config_file.match(
            b"pxelinux.cfg/default.%s-%s" % (arch, subarch)
        )
        self.assertIsNotNone(match)
        self.assertDictEqual(
            {
                "mac": None,
                "hardware_uuid": None,
                "arch": arch,
                "subarch": subarch,
            },
            match.groupdict(),
        )
