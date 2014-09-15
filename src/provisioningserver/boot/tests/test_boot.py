# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.boot`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import errno
import os

from fixtures import EnvironmentVariableFixture
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
    )
import mock
from provisioningserver import (
    boot,
    config,
    )
from provisioningserver.boot import (
    BootMethod,
    BytesReader,
    compose_poweroff_command,
    gen_template_filenames,
    get_remote_mac,
    )
from provisioningserver.tests.test_kernel_opts import make_kernel_parameters
import tempita
from twisted.internet.defer import inlineCallbacks
from twisted.python import context


class FakeBootMethod(BootMethod):

    name = "fake"
    template_subdir = "fake"
    bootloader_path = "fake.efi"
    arch_octet = "00:00"

    def match_path(self, backend, path):
        return {}

    def get_reader(backend, kernel_params, **extra):
        return BytesReader("")

    def install_bootloader():
        pass


class TestBootMethod(MAASTestCase):
    """Test for `BootMethod` in `provisioningserver.boot`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    @inlineCallbacks
    def test_get_remote_mac(self):
        remote_host = factory.make_ipv4_address()
        call_context = {
            "local": (
                factory.make_ipv4_address(),
                factory.pick_port()),
            "remote": (
                remote_host,
                factory.pick_port()),
            }

        mock_find = self.patch(boot, 'find_mac_via_arp')
        yield context.call(call_context, get_remote_mac)
        self.assertThat(mock_find, MockCalledOnceWith(remote_host))

    def test_gen_template_filenames(self):
        purpose = factory.make_name("purpose")
        arch, subarch = factory.make_names("arch", "subarch")
        expected = [
            "config.%s.%s.%s.template" % (purpose, arch, subarch),
            "config.%s.%s.template" % (purpose, arch),
            "config.%s.template" % (purpose, ),
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
            os.path.join(method.get_template_dir(), filename),
            encoding="UTF-8")

    def make_fake_templates_dir(self, method):
        """Set up a fake templates dir, and return its path."""
        fake_etc_maas = self.make_dir()
        self.useFixture(EnvironmentVariableFixture(
            'MAAS_CONFIG_DIR', fake_etc_maas))
        fake_templates = os.path.join(
            fake_etc_maas, 'templates/%s' % method.template_subdir)
        os.makedirs(fake_templates)
        return fake_templates

    def test_get_template_gets_default_if_available(self):
        # If there is no template matching the purpose, arch, and subarch,
        # but there is a completely generic template, then get_pxe_template()
        # falls back to that as the default.
        method = FakeBootMethod()
        templates_dir = self.make_fake_templates_dir(method)
        generic_template = factory.make_file(templates_dir, 'config.template')
        purpose = factory.make_name("purpose")
        arch, subarch = factory.make_names("arch", "subarch")
        self.assertEqual(
            generic_template,
            method.get_template(purpose, arch, subarch).name)

    def test_get_template_not_found(self):
        # It is a critical and unrecoverable error if the default template
        # is not found.
        method = FakeBootMethod()
        self.make_fake_templates_dir(method)
        self.assertRaises(
            AssertionError, method.get_template,
            *factory.make_names("purpose", "arch", "subarch"))

    def test_get_templates_only_suppresses_ENOENT(self):
        # The IOError arising from trying to load a template that doesn't
        # exist is suppressed, but other errors are not.
        method = FakeBootMethod()
        from_filename = self.patch(tempita.Template, "from_filename")
        from_filename.side_effect = IOError()
        from_filename.side_effect.errno = errno.EACCES
        self.assertRaises(
            IOError, method.get_template,
            *factory.make_names("purpose", "arch", "subarch"))

    def test_compose_poweroff_command_for_syslinux_6(self):
        storage_dir = self.make_dir()
        syslinux_path = os.path.join(storage_dir, "current", "syslinux")
        os.makedirs(syslinux_path)
        factory.make_file(syslinux_path, "poweroff.c32", contents=None)
        self.patch(config, 'BOOT_RESOURCES_STORAGE', storage_dir)
        self.assertEqual(
            "COM32 /syslinux/poweroff.c32",
            compose_poweroff_command())

    def test_compose_poweroff_command_for_syslinux_4(self):
        storage_dir = self.make_dir()
        syslinux_path = os.path.join(storage_dir, "current", "syslinux")
        os.makedirs(syslinux_path)
        factory.make_file(syslinux_path, "poweroff.com", contents=None)
        self.patch(config, 'BOOT_RESOURCES_STORAGE', storage_dir)
        self.assertEqual(
            "KERNEL /syslinux/poweroff.com",
            compose_poweroff_command())

    def test_compose_template_namespace_includes_poweroff(self):
        fake_poweroff = factory.make_name('poweroff')
        self.patch(
            boot, 'compose_poweroff_command').return_value = fake_poweroff
        method = FakeBootMethod()
        kernel_params = make_kernel_parameters(purpose="poweroff")
        namespace = method.compose_template_namespace(kernel_params)
        self.assertEqual(fake_poweroff, namespace['poweroff'])
