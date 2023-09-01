# Copyright 2019-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the ipxe boot method."""


import os
import re

from testtools.matchers import MatchesAll, MatchesRegex, Not, StartsWith
from twisted.python.filepath import FilePath

from maastesting.factory import factory
from maastesting.matchers import FileContains
from maastesting.testcase import MAASTestCase
from provisioningserver.boot import BytesReader
from provisioningserver.boot.ipxe import (
    CONFIG_FILE,
    IPXEBootMethod,
    re_config_file,
)
from provisioningserver.boot.testing import TFTPPath, TFTPPathAndComponents
from provisioningserver.boot.tftppath import compose_image_path
from provisioningserver.testing.config import ClusterConfigurationFixture
from provisioningserver.tests.test_kernel_opts import make_kernel_parameters
from provisioningserver.utils.fs import tempdir
from provisioningserver.utils.network import convert_host_to_uri_str


def compose_config_path(mac: str) -> TFTPPath:
    """Compose the TFTP/HTTP path for a iPXE configuration file.

    The path returned is relative to root, as it would be
    identified by clients on the network.

    :param mac: A MAC address.
    :return: Path for the corresponding iPXE config file as exposed over
        TFTP/HTTP, as a byte string.
    """
    return f"ipxe.cfg-{mac}".encode("ascii")


class TestIPXEBootMethod(MAASTestCase):
    def make_tftp_root(self):
        """Set, and return, a temporary TFTP root directory."""
        tftproot = self.make_dir()
        self.useFixture(ClusterConfigurationFixture(tftp_root=tftproot))
        return FilePath(tftproot)

    def test_compose_config_path_follows_maas_pxe_directory_layout(self):
        mac = factory.make_mac_address()
        self.assertEqual(
            "ipxe.cfg-%s" % mac, compose_config_path(mac).decode("ascii")
        )

    def test_compose_config_path_does_not_include_tftp_root(self):
        tftproot = self.make_tftp_root().asBytesMode()
        mac = factory.make_mac_address()
        self.assertThat(
            compose_config_path(mac), Not(StartsWith(tftproot.path))
        )

    def test_bootloader_path(self):
        method = IPXEBootMethod()
        self.assertEqual("ipxe.cfg", method.bootloader_path)

    def test_bootloader_path_does_not_include_tftp_root(self):
        tftproot = self.make_tftp_root()
        method = IPXEBootMethod()
        self.assertThat(method.bootloader_path, Not(StartsWith(tftproot.path)))

    def test_name(self):
        method = IPXEBootMethod()
        self.assertEqual("ipxe", method.name)

    def test_template_subdir(self):
        method = IPXEBootMethod()
        self.assertEqual("ipxe", method.template_subdir)

    def test_arch_octet(self):
        method = IPXEBootMethod()
        self.assertIsNone(method.arch_octet)

    def test_user_class(self):
        method = IPXEBootMethod()
        self.assertEqual("iPXE", method.user_class)

    def test_link_bootloader_creates_ipxe_cfg(self):
        method = IPXEBootMethod()
        with tempdir() as tmp:
            method.link_bootloader(tmp)

            cfg_file_path = os.path.join(tmp, "ipxe.cfg")
            self.assertTrue(cfg_file_path, FileContains(CONFIG_FILE))


class TestIPXEBootMethodRender(MAASTestCase):
    """Tests for `provisioningserver.boot.ipxe.IPXEBootMethod.render`."""

    def test_get_reader_install(self):
        # Given the right configuration options, the PXE configuration is
        # correctly rendered.
        method = IPXEBootMethod()
        params = make_kernel_parameters(self, purpose="xinstall")
        fs_host = "http://%s:5248/images" % (
            convert_host_to_uri_str(params.fs_host)
        )
        output = method.get_reader(backend=None, kernel_params=params)
        # The output is a BytesReader.
        self.assertIsInstance(output, BytesReader)
        output = output.read(10000).decode("utf-8")
        # The template has rendered without error. iPXE configurations
        # start with #ipxe.
        self.assertThat(output, StartsWith("#!ipxe"))
        # The iPXE parameters are all set according to the options.
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
                    r".*^\s*kernel %s/%s/%s$"
                    % (
                        re.escape(fs_host),
                        re.escape(image_dir),
                        params.kernel,
                    ),
                    re.MULTILINE | re.DOTALL,
                ),
                MatchesRegex(
                    r".*^\s*initrd %s/%s/%s$"
                    % (
                        re.escape(fs_host),
                        re.escape(image_dir),
                        params.initrd,
                    ),
                    re.MULTILINE | re.DOTALL,
                ),
                MatchesRegex(r".*^\s*imgargs .+?$", re.MULTILINE | re.DOTALL),
            ),
        )

    def test_get_reader_with_local_purpose(self):
        # If purpose is "local", the config.localboot.template should be
        # used.
        method = IPXEBootMethod()
        options = {
            "backend": None,
            "kernel_params": make_kernel_parameters(purpose="local"),
        }
        output = method.get_reader(**options).read(10000)
        self.assertIn(b"sanboot --no-describe --drive 0x80", output)


class TestIPXEBootMethodRegex(MAASTestCase):
    "Tests for `provisioningserver.boot.ipxe.IPXEBootMethod.re_config_file`." ""

    @staticmethod
    def get_example_path_and_components() -> TFTPPathAndComponents:
        """Return a plausible path and its components.

        The path is intended to match `re_config_file`, and the components are
        the expected groups from a match.
        """
        mac = factory.make_mac_address()
        components = {
            "mac": mac.encode("ascii"),
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

    def test_re_config_file_matches_ipxe_cfg(self):
        # The default config path is simply "ipxe.cfg" (without
        # leading slash).  The regex matches this.
        mac = b"aa:bb:cc:dd:ee:ff"
        match = re_config_file.match(b"ipxe.cfg-%s" % mac)
        self.assertIsNotNone(match)
        self.assertDictEqual(
            {"mac": mac, "arch": None, "subarch": None}, match.groupdict()
        )

    def test_re_config_file_matches_ipxe_cfg_with_leading_slash(self):
        mac = b"aa:bb:cc:dd:ee:ff"
        match = re_config_file.match(b"/ipxe.cfg-%s" % mac)
        self.assertIsNotNone(match)
        self.assertDictEqual(
            {"mac": mac, "arch": None, "subarch": None}, match.groupdict()
        )

    def test_re_config_file_does_not_match_non_config_file(self):
        self.assertIsNone(re_config_file.match(b"ipxe.cfg-kernel"))

    def test_re_config_file_does_not_match_file_in_root(self):
        self.assertIsNone(re_config_file.match(b"aa:bb:cc:dd:ee:ff"))

    def test_re_config_file_with_default_arch(self):
        arch = factory.make_name("arch", sep="").encode("ascii")
        match = re_config_file.match(b"ipxe.cfg-default-%s" % arch)
        self.assertIsNotNone(match)
        self.assertDictEqual(
            {"mac": None, "arch": arch, "subarch": None}, match.groupdict()
        )

    def test_re_config_file_with_default_arch_and_subarch(self):
        arch = factory.make_name("arch", sep="").encode("ascii")
        subarch = factory.make_name("subarch", sep="").encode("ascii")
        match = re_config_file.match(
            b"ipxe.cfg-default-%s-%s" % (arch, subarch)
        )
        self.assertIsNotNone(match)
        self.assertDictEqual(
            {"mac": None, "arch": arch, "subarch": subarch}, match.groupdict()
        )
