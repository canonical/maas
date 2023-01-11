# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.boot`."""


import errno
import os
from unittest import mock
from urllib.parse import urlparse

import tempita
from twisted.internet.defer import inlineCallbacks, succeed
from twisted.python import context

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnce, MockCalledOnceWith
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver import boot
from provisioningserver.boot import (
    BootMethod,
    BytesReader,
    gen_template_filenames,
    get_main_archive_url,
    get_ports_archive_url,
    get_remote_mac,
    maaslog,
)
from provisioningserver.boot.tftppath import compose_image_path
from provisioningserver.kernel_opts import compose_kernel_command_line
from provisioningserver.rpc import region
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from provisioningserver.tests.test_kernel_opts import make_kernel_parameters
from provisioningserver.utils.fs import atomic_symlink, tempdir


class FakeBootMethod(BootMethod):

    name = factory.make_name("name")
    bios_boot_method = factory.make_name("bios_boot_method")
    template_subdir = factory.make_name("template_subdir")
    bootloader_arches = [factory.make_name("arch") for _ in range(2)]
    bootloader_path = factory.make_name("bootloader_path")
    bootloader_files = [factory.make_name("bootloader_file") for _ in range(3)]
    arch_octet = "00:00"
    user_class = None

    def match_path(self, backend, path):
        return {}

    def get_reader(backend, kernel_params, **extra):
        return BytesReader("")


class TestBootMethod(MAASTestCase):
    """Test for `BootMethod` in `provisioningserver.boot`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    @inlineCallbacks
    def test_get_remote_mac(self):
        remote_host = factory.make_ipv4_address()
        call_context = {
            "local": (factory.make_ipv4_address(), factory.pick_port()),
            "remote": (remote_host, factory.pick_port()),
        }

        mock_find = self.patch(boot, "find_mac_via_arp")
        yield context.call(call_context, get_remote_mac)
        self.assertThat(mock_find, MockCalledOnceWith(remote_host))

    def test_gen_template_filenames(self):
        purpose = factory.make_name("purpose")
        arch, subarch = factory.make_names("arch", "subarch")
        expected = [
            "config.%s.%s.%s.template" % (purpose, arch, subarch),
            "config.%s.%s.template" % (purpose, arch),
            "config.%s.template" % (purpose,),
            "config.template",
        ]
        observed = gen_template_filenames(purpose, arch, subarch)
        self.assertSequenceEqual(expected, list(observed))

    def test_get_pxe_template(self):
        method = FakeBootMethod()
        purpose = factory.make_name("purpose")
        arch, subarch = factory.make_names("arch", "subarch")
        filename = factory.make_name("filename")
        # Set up the mocks that we've patched in.
        gen_filenames = self.patch(boot, "gen_template_filenames")
        gen_filenames.return_value = [filename]
        from_filename = self.patch(tempita.Template, "from_filename")
        from_filename.return_value = mock.sentinel.template
        # The template returned matches the return value above.
        template = method.get_template(purpose, arch, subarch)
        self.assertEqual(mock.sentinel.template, template)
        # gen_pxe_template_filenames is called to obtain filenames.
        gen_filenames.assert_called_once_with(purpose, arch, subarch)
        # Tempita.from_filename is called with an absolute path derived from
        # the filename returned from gen_pxe_template_filenames.
        from_filename.assert_called_once_with(
            os.path.join(method.get_template_dir(), filename), encoding="UTF-8"
        )

    def test_get_template_gets_default_if_available(self):
        # If there is no template matching the purpose, arch, and subarch,
        # but there is a completely generic template, then get_pxe_template()
        # falls back to that as the default.
        templates_dir = self.make_dir()
        method = FakeBootMethod()
        method.get_template_dir = lambda: templates_dir
        generic_template = factory.make_file(templates_dir, "config.template")
        purpose = factory.make_name("purpose")
        arch, subarch = factory.make_names("arch", "subarch")
        self.assertEqual(
            generic_template, method.get_template(purpose, arch, subarch).name
        )

    def test_get_template_not_found(self):
        mock_try_send_rack_event = self.patch(boot, "try_send_rack_event")
        # It is a critical and unrecoverable error if the default template
        # is not found.
        templates_dir = self.make_dir()
        method = FakeBootMethod()
        method.get_template_dir = lambda: templates_dir
        self.assertRaises(
            AssertionError,
            method.get_template,
            *factory.make_names("purpose", "arch", "subarch")
        )
        self.assertThat(mock_try_send_rack_event, MockCalledOnce())

    def test_get_templates_only_suppresses_ENOENT(self):
        # The IOError arising from trying to load a template that doesn't
        # exist is suppressed, but other errors are not.
        method = FakeBootMethod()
        from_filename = self.patch(tempita.Template, "from_filename")
        from_filename.side_effect = IOError()
        from_filename.side_effect.errno = errno.EACCES
        self.assertRaises(
            IOError,
            method.get_template,
            *factory.make_names("purpose", "arch", "subarch")
        )

    def test_link_bootloader_links_simplestream_bootloader_files(self):
        method = FakeBootMethod()
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

    def test_link_bootloader_logs_missing_simplestream_file(self):
        method = FakeBootMethod()
        mock_maaslog = self.patch(maaslog, "error")
        mock_try_send_rack_event = self.patch(boot, "try_send_rack_event")
        with tempdir() as tmp:
            stream_path = os.path.join(
                tmp,
                "bootloader",
                method.bios_boot_method,
                method.bootloader_arches[0],
            )
            os.makedirs(stream_path)
            for bootloader_file in method.bootloader_files[1:]:
                factory.make_file(stream_path, bootloader_file)

            method.link_bootloader(tmp)

            self.assertThat(mock_maaslog, MockCalledOnce())
            self.assertThat(mock_try_send_rack_event, MockCalledOnce())

    def test_link_bootloader_copies_previous_downloaded_files(self):
        method = FakeBootMethod()
        with tempdir() as tmp:
            new_dir = os.path.join(tmp, "new")
            current_dir = os.path.join(tmp, "current")
            os.makedirs(new_dir)
            os.makedirs(current_dir)
            for bootloader_file in method.bootloader_files:
                factory.make_file(current_dir, bootloader_file)

            method.link_bootloader(new_dir)

            for bootloader_file in method.bootloader_files:
                bootloader_file_path = os.path.join(new_dir, bootloader_file)
                self.assertTrue(os.path.isfile(bootloader_file_path))

    def test_link_bootloader_links_bootloaders_found_elsewhere_on_fs(self):
        method = FakeBootMethod()
        with tempdir() as tmp:
            bootresources_dir = os.path.join(tmp, "boot-resources")
            new_dir = os.path.join(bootresources_dir, "new")
            current_dir = os.path.join(bootresources_dir, "current")
            os.makedirs(new_dir)
            os.makedirs(current_dir)
            for bootloader_file in method.bootloader_files:
                factory.make_file(tmp, bootloader_file)
                atomic_symlink(
                    os.path.join(tmp, bootloader_file),
                    os.path.join(current_dir, bootloader_file),
                )

            method.link_bootloader(new_dir)

            for bootloader_file in method.bootloader_files:
                bootloader_file_path = os.path.join(new_dir, bootloader_file)
                self.assertTrue(os.path.islink(bootloader_file_path))

    def test_link_bootloader_logs_missing_previous_downloaded_files(self):
        method = FakeBootMethod()
        mock_maaslog = self.patch(maaslog, "error")
        mock_try_send_rack_event = self.patch(boot, "try_send_rack_event")
        with tempdir() as tmp:
            new_dir = os.path.join(tmp, "new")
            current_dir = os.path.join(tmp, "current")
            os.makedirs(new_dir)
            os.makedirs(current_dir)
            for bootloader_file in method.bootloader_files[1:]:
                factory.make_file(current_dir, bootloader_file)

            method.link_bootloader(new_dir)

            self.assertThat(mock_maaslog, MockCalledOnce())
            self.assertThat(mock_try_send_rack_event, MockCalledOnce())

    def test_compose_template_namespace(self):
        kernel_params = make_kernel_parameters()
        method = FakeBootMethod()
        image_dir = compose_image_path(
            kernel_params.osystem,
            kernel_params.arch,
            kernel_params.subarch,
            kernel_params.release,
            kernel_params.label,
        )

        template_namespace = method.compose_template_namespace(kernel_params)

        self.assertEqual(
            "%s/%s" % (image_dir, kernel_params.initrd),
            template_namespace["initrd_path"](kernel_params),
        )
        self.assertEqual(
            compose_kernel_command_line(kernel_params),
            template_namespace["kernel_command"](kernel_params),
        )
        self.assertEqual(kernel_params, template_namespace["kernel_params"])
        self.assertEqual(
            "%s/%s" % (image_dir, kernel_params.kernel),
            template_namespace["kernel_path"](kernel_params),
        )
        self.assertIsNone(template_namespace["dtb_path"](kernel_params))

    def test_compose_template_namespace_returns_filetype_when_missing(self):
        kernel_params = make_kernel_parameters(
            subarch="xgene-uboot-mustang",
            kernel=None,
            initrd=None,
            boot_dtb=None,
        )
        method = FakeBootMethod()
        image_dir = compose_image_path(
            kernel_params.osystem,
            kernel_params.arch,
            kernel_params.subarch,
            kernel_params.release,
            kernel_params.label,
        )

        template_namespace = method.compose_template_namespace(kernel_params)

        self.assertEqual(
            "%s/boot-initrd" % image_dir,
            template_namespace["initrd_path"](kernel_params),
        )
        self.assertEqual(
            compose_kernel_command_line(kernel_params),
            template_namespace["kernel_command"](kernel_params),
        )
        self.assertEqual(kernel_params, template_namespace["kernel_params"])
        self.assertEqual(
            "%s/boot-kernel" % image_dir,
            template_namespace["kernel_path"](kernel_params),
        )
        self.assertEqual(
            "%s/boot-dtb" % image_dir,
            template_namespace["dtb_path"](kernel_params),
        )

    def test_compose_template_namespace_returns_dtb_file_when_arm(self):
        kernel_params = make_kernel_parameters(subarch="xgene-uboot-mustang")
        method = FakeBootMethod()
        image_dir = compose_image_path(
            kernel_params.osystem,
            kernel_params.arch,
            kernel_params.subarch,
            kernel_params.release,
            kernel_params.label,
        )

        template_namespace = method.compose_template_namespace(kernel_params)

        self.assertEqual(
            "%s/%s" % (image_dir, kernel_params.initrd),
            template_namespace["initrd_path"](kernel_params),
        )
        self.assertEqual(
            compose_kernel_command_line(kernel_params),
            template_namespace["kernel_command"](kernel_params),
        )
        self.assertEqual(kernel_params, template_namespace["kernel_params"])
        self.assertEqual(
            "%s/%s" % (image_dir, kernel_params.kernel),
            template_namespace["kernel_path"](kernel_params),
        )
        self.assertEqual(
            "%s/%s" % (image_dir, kernel_params.boot_dtb),
            template_namespace["dtb_path"](kernel_params),
        )


class TestGetArchiveUrl(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def patch_rpc_methods(self, return_value=None):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(region.GetArchiveMirrors)
        protocol.GetArchiveMirrors.return_value = return_value
        return protocol, connecting

    @inlineCallbacks
    def test_get_main_archive_url(self):
        mirrors = {
            "main": urlparse(factory.make_url("ports")),
            "ports": urlparse(factory.make_url("ports")),
        }
        return_value = succeed(mirrors)
        protocol, connecting = self.patch_rpc_methods(return_value)
        self.addCleanup((yield connecting))
        value = yield get_main_archive_url()
        expected_url = mirrors["main"].geturl()
        self.assertEqual(expected_url, value)

    @inlineCallbacks
    def test_get_ports_archive_url(self):
        mirrors = {
            "main": urlparse(factory.make_url("ports")),
            "ports": urlparse(factory.make_url("ports")),
        }
        return_value = succeed(mirrors)
        protocol, connecting = self.patch_rpc_methods(return_value)
        self.addCleanup((yield connecting))
        value = yield get_ports_archive_url()
        expected_url = mirrors["ports"].geturl()
        self.assertEqual(expected_url, value)
