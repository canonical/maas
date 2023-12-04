# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.boot.s390x`."""


import re
from unittest.mock import Mock

from twisted.python.filepath import FilePath

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.boot import BytesReader
from provisioningserver.boot import s390x as s390x_module
from provisioningserver.boot.s390x import (
    ARP_HTYPE,
    format_bootif,
    re_config_file,
    S390XBootMethod,
)
from provisioningserver.boot.testing import TFTPPathAndComponents
from provisioningserver.boot.tests.test_pxe import parse_pxe_config
from provisioningserver.boot.tftppath import compose_image_path
from provisioningserver.testing.config import ClusterConfigurationFixture
from provisioningserver.tests.test_kernel_opts import make_kernel_parameters


def compose_config_path(mac: str) -> bytes:
    """Compose the TFTP path for a S390x PXE configuration file.

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
    return "s390x/pxelinux.cfg/{htype:02x}-{mac}".format(
        htype=ARP_HTYPE.ETHERNET, mac=mac
    ).encode("ascii")


def get_example_path_and_components() -> TFTPPathAndComponents:
    """Return a plausible path and its components.

    The path is intended to match `re_config_file`, and the components are
    the expected groups from a match.
    """
    mac = factory.make_mac_address("-")
    return compose_config_path(mac), {"mac": mac.encode("ascii")}


class TestS390XBootMethod(MAASTestCase):
    def make_tftp_root(self):
        """Set, and return, a temporary TFTP root directory."""
        tftproot = self.make_dir()
        self.useFixture(ClusterConfigurationFixture(tftp_root=tftproot))
        return FilePath(tftproot)

    def test_compose_config_path_follows_maas_pxe_directory_layout(self):
        mac = factory.make_mac_address("-")
        self.assertEqual(
            f"s390x/pxelinux.cfg/{ARP_HTYPE.ETHERNET:02x}-{mac}",
            compose_config_path(mac).decode("ascii"),
        )

    def test_compose_config_path_does_not_include_tftp_root(self):
        tftproot = self.make_tftp_root().asBytesMode()
        mac = factory.make_mac_address("-")
        config_path = compose_config_path(mac)
        self.assertFalse(config_path.startswith(tftproot.path))

    def test_bootloader_path(self):
        method = S390XBootMethod()
        self.assertEqual("boots390x.bin", method.bootloader_path)

    def test_bootloader_path_does_not_include_tftp_root(self):
        tftproot = self.make_tftp_root()
        method = S390XBootMethod()
        self.assertFalse(method.bootloader_path.startswith(tftproot.path))

    def test_name(self):
        method = S390XBootMethod()
        self.assertEqual("s390x", method.name)

    def test_template_subdir(self):
        method = S390XBootMethod()
        self.assertEqual("pxe", method.template_subdir)

    def test_arch_octet(self):
        method = S390XBootMethod()
        self.assertEqual("00:1F", method.arch_octet)

    def test_path_prefix(self):
        method = S390XBootMethod()
        self.assertEqual("s390x/", method.path_prefix)


class TestS390XBootMethodMatchPath(MAASTestCase):
    """Tests for
    `provisioningserver.boot.s390x.S390XBootMethod.match_path`.
    """

    def test_match_path_pxe_config_with_mac(self):
        method = S390XBootMethod()
        config_path, args = get_example_path_and_components()
        params = method.match_path(None, config_path)
        expected = {"arch": "s390x", "mac": args["mac"].decode("ascii")}
        self.assertEqual(expected, params)

    def test_match_path_pxe_config_without_mac(self):
        method = S390XBootMethod()
        fake_mac = factory.make_mac_address("-")
        self.patch(s390x_module, "get_remote_mac").return_value = fake_mac
        config_path = b"s390x/pxelinux.cfg/default"
        params = method.match_path(None, config_path)
        expected = {"arch": "s390x", "mac": fake_mac}
        self.assertEqual(expected, params)

    def test_match_path_pxe_prefix_request(self):
        method = S390XBootMethod()
        fake_mac = factory.make_mac_address("-")
        self.patch(s390x_module, "get_remote_mac").return_value = fake_mac
        file_path = b"s390x/file"
        params = method.match_path(None, file_path)
        expected = {
            "arch": "s390x",
            "mac": fake_mac,
            # The "s390x/" prefix has been removed from the path.
            "path": file_path.decode("utf-8")[6:],
        }
        self.assertEqual(expected, params)


class TestS390XBootMethodRenderConfig(MAASTestCase):
    """Tests for
    `provisioningserver.boot.s390x.S390XBootMethod.get_reader`
    """

    def test_get_reader_install(self):
        # Given the right configuration options, the PXE configuration is
        # correctly rendered.
        method = S390XBootMethod()
        params = make_kernel_parameters(self, arch="s390x", purpose="xinstall")
        output = method.get_reader(backend=None, kernel_params=params)
        # The output is a BytesReader.
        self.assertIsInstance(output, BytesReader)
        output = output.read(10000).decode("utf-8")
        # The template has rendered without error. PXELINUX configurations
        # typically start with a DEFAULT line.
        self.assertTrue(output.startswith("DEFAULT "))
        # The PXE parameters are all set according to the options.
        image_dir = re.escape(
            compose_image_path(
                osystem=params.kernel_osystem,
                arch=params.arch,
                subarch=params.subarch,
                release=params.kernel_release,
                label=params.kernel_label,
            )
        )
        for regex in [
            rf"(?ms).*^\s+KERNEL {image_dir}/{params.kernel}$",
            rf"(?ms).*^\s+INITRD {image_dir}/{params.initrd}$",
            r"(?ms).*^\s+APPEND .+?$",
        ]:
            self.assertRegex(output, regex)

    def test_get_reader_with_extra_arguments_does_not_affect_output(self):
        # get_reader() allows any keyword arguments as a safety valve.
        method = S390XBootMethod()
        options = {
            "backend": None,
            "kernel_params": make_kernel_parameters(
                self, arch="s390x", purpose="install"
            ),
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
        # If purpose is "local", output should be empty string.
        method = S390XBootMethod()
        options = {
            "backend": None,
            "kernel_params": make_kernel_parameters(
                arch="amd64", purpose="local"
            ),
        }
        output = method.get_reader(**options).read(10000).decode("utf-8")
        self.assertIn("", output)

    def test_get_reader_appends_bootif(self):
        method = S390XBootMethod()
        fake_mac = factory.make_mac_address("-")
        params = make_kernel_parameters(self, arch="amd64", purpose="install")
        output = method.get_reader(
            backend=None, kernel_params=params, arch="s390x", mac=fake_mac
        )
        output = output.read(10000).decode("utf-8")
        config = parse_pxe_config(output)
        expected = "BOOTIF=%s" % format_bootif(fake_mac)
        self.assertIn(expected, config["execute"]["APPEND"])

    def test_format_bootif_replaces_colon(self):
        fake_mac = factory.make_mac_address("-")
        self.assertEqual(
            "01-%s" % fake_mac.replace(":", "-").lower(),
            format_bootif(fake_mac),
        )

    def test_format_bootif_makes_mac_address_lower(self):
        fake_mac = factory.make_mac_address("-")
        fake_mac = fake_mac.upper()
        self.assertEqual(
            "01-%s" % fake_mac.replace(":", "-").lower(),
            format_bootif(fake_mac),
        )


class TestS390XBootMethodPathPrefix(MAASTestCase):
    """Tests for `provisioningserver.boot.s390x.S390XBootMethod`."""

    def test_path_prefix_removed(self):
        temp_dir = FilePath(self.make_dir())
        backend = Mock(base=temp_dir)  # A `TFTPBackend`.

        # Create a file in the backend's base directory.
        data = factory.make_string().encode("ascii")
        temp_file = temp_dir.child("example")
        temp_file.setContent(data)

        method = S390XBootMethod()
        params = method.get_params(backend, b"s390x/example")
        self.assertEqual({"path": "example"}, params)
        reader = method.get_reader(backend, make_kernel_parameters(), **params)
        self.addCleanup(reader.finish)
        self.assertEqual(len(data), reader.size)
        self.assertEqual(data, reader.read(len(data)))
        self.assertEqual(b"", reader.read(1))

    def test_path_prefix_only_first_occurrence_removed(self):
        temp_dir = FilePath(self.make_dir())
        backend = Mock(base=temp_dir)  # A `TFTPBackend`.

        # Create a file nested within a "s390x" directory.
        data = factory.make_string().encode("ascii")
        temp_subdir = temp_dir.child("s390x")
        temp_subdir.createDirectory()
        temp_file = temp_subdir.child("example")
        temp_file.setContent(data)

        method = S390XBootMethod()
        params = method.get_params(backend, b"s390x/s390x/example")
        self.assertEqual({"path": "s390x/example"}, params)
        reader = method.get_reader(backend, make_kernel_parameters(), **params)
        self.addCleanup(reader.finish)
        self.assertEqual(len(data), reader.size)
        self.assertEqual(data, reader.read(len(data)))
        self.assertEqual(b"", reader.read(1))


class TestS390XBootMethodRegex(MAASTestCase):
    """Tests for
    `provisioningserver.boot.s390x.S390XBootMethod.re_config_file`.
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
        config_path = b"/" + config_path.lstrip(b"/")
        match = re_config_file.match(config_path)
        self.assertIsNotNone(match, config_path)
        self.assertEqual(args, match.groupdict())

    def test_re_config_file_without_leading_slash(self):
        # The regular expression for extracting components of the file path
        # doesn't care if there's no leading forward slash; the TFTP server is
        # easy on this point, so it makes sense to be also.
        config_path, args = get_example_path_and_components()
        # Ensure there's no leading slash.
        config_path = config_path.lstrip(b"/")
        match = re_config_file.match(config_path)
        self.assertIsNotNone(match, config_path)
        self.assertEqual(args, match.groupdict())

    def test_re_config_file_matches_classic_pxelinux_cfg(self):
        # The default config path is simply "pxelinux.cfg" (without
        # leading slash).  The regex matches this.
        mac = factory.make_mac_address("-").encode("ascii")
        match = re_config_file.match(b"s390x/pxelinux.cfg/01-%s" % mac)
        self.assertIsNotNone(match)
        self.assertEqual({"mac": mac}, match.groupdict())

    def test_re_config_file_matches_pxelinux_cfg_with_leading_slash(self):
        mac = factory.make_mac_address("-").encode("ascii")
        match = re_config_file.match(b"/s390x/pxelinux.cfg/01-%s" % mac)
        self.assertIsNotNone(match)
        self.assertEqual({"mac": mac}, match.groupdict())

    def test_re_config_file_matches_pxelinux_cfg_without_pxelinux_cfg(self):
        mac = factory.make_mac_address("-").encode("ascii")
        match = re_config_file.match(b"/s390x/01-%s" % mac)
        self.assertIsNotNone(match)
        self.assertEqual({"mac": mac}, match.groupdict())

    def test_re_config_file_does_not_match_non_config_file(self):
        self.assertIsNone(re_config_file.match(b"s390x/pxelinux.cfg/kernel"))

    def test_re_config_file_does_not_match_file_in_root(self):
        self.assertIsNone(re_config_file.match(b"01-aa-bb-cc-dd-ee-ff"))

    def test_re_config_file_does_not_match_file_not_in_pxelinux_cfg(self):
        self.assertIsNone(re_config_file.match(b"foo/01-aa-bb-cc-dd-ee-ff"))

    def test_re_config_file_with_default(self):
        match = re_config_file.match(b"s390x/pxelinux.cfg/default")
        self.assertIsNotNone(match)
        self.assertEqual({"mac": None}, match.groupdict())
