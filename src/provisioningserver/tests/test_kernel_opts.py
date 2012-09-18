# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test composition of kernel command lines."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "make_kernel_parameters",
    ]

import os

from maastesting.factory import factory
from maastesting.matchers import ContainsAll
from maastesting.testcase import TestCase
from provisioningserver import kernel_opts
from provisioningserver.kernel_opts import (
    compose_kernel_command_line,
    compose_preseed_opt,
    EphemeralImagesDirectoryNotFound,
    get_last_directory,
    ISCSI_TARGET_NAME_PREFIX,
    KernelParameters,
    )
from provisioningserver.testing.config import ConfigFixture
from testtools.matchers import (
    Contains,
    Not,
    )


def make_kernel_parameters(**parms):
    """Make a randomly populated `KernelParameters` instance."""
    parms.update(
        {field: factory.make_name(field)
         for field in KernelParameters._fields
         if field not in parms})
    return KernelParameters(**parms)


class TestUtilitiesKernelOpts(TestCase):

    def test_get_last_directory(self):
        root = self.make_dir()
        dir1 = os.path.join(root, '20120405')
        dir2 = os.path.join(root, '20120105')
        dir3 = os.path.join(root, '20120403')
        os.makedirs(dir1)
        os.makedirs(dir2)
        os.makedirs(dir3)
        self.assertEqual(dir1, get_last_directory(root))

    def test_kernel_parameters_callable(self):
        # KernelParameters instances are callable; an alias for _replace().
        params = make_kernel_parameters()
        self.assertTrue(callable(params))
        self.assertIs(params._replace.im_func, params.__call__.im_func)


class TestKernelOpts(TestCase):

    def test_compose_kernel_command_line_includes_preseed_url(self):
        params = make_kernel_parameters()
        self.assertIn(
            "auto url=%s" % params.preseed_url,
            compose_kernel_command_line(params))

    def test_install_compose_kernel_command_line_includes_name_domain(self):
        params = make_kernel_parameters(purpose="install")
        self.assertThat(
            compose_kernel_command_line(params),
            ContainsAll([
                "hostname=%s" % params.hostname,
                "domain=%s" % params.domain,
                ]))

    def test_install_compose_kernel_command_line_includes_locale(self):
        params = make_kernel_parameters(purpose="install")
        locale = "en_US"
        self.assertIn(
            "locale=%s" % locale,
            compose_kernel_command_line(params))

    def test_install_compose_kernel_command_line_includes_log_settings(self):
        params = make_kernel_parameters(purpose="install")
        # Port 514 (UDP) is syslog.
        log_port = "514"
        self.assertThat(
            compose_kernel_command_line(params),
            ContainsAll([
                "log_host=%s" % params.log_host,
                "log_port=%s" % log_port,
                ]))

    def test_install_compose_kernel_command_line_includes_di_settings(self):
        params = make_kernel_parameters(purpose="install")
        self.assertThat(
            compose_kernel_command_line(params),
            Contains("text priority=critical"))

    def test_install_compose_kernel_command_line_inc_purpose_opts(self):
        # The result of compose_kernel_command_line includes the purpose
        # options for a non "commissioning" node.
        params = make_kernel_parameters(purpose="install")
        self.assertIn(
            "netcfg/choose_interface=auto",
            compose_kernel_command_line(params))

    def test_commissioning_compose_kernel_command_line_inc_purpose_opts(self):
        # The result of compose_kernel_command_line includes the purpose
        # options for a non "commissioning" node.
        get_ephemeral_name = self.patch(kernel_opts, "get_ephemeral_name")
        get_ephemeral_name.return_value = "RELEASE-ARCH"
        params = make_kernel_parameters(purpose="commissioning")
        cmdline = compose_kernel_command_line(params)
        self.assertThat(
            cmdline,
            ContainsAll([
                "root=LABEL=cloudimg-rootfs",
                "iscsi_initiator=",
                "overlayroot=tmpfs",
                "ip=dhcp")

    def test_compose_kernel_command_line_inc_common_opts(self):
        # Test that some kernel arguments appear on both commissioning
        # and install command lines.
        get_ephemeral_name = self.patch(kernel_opts, "get_ephemeral_name")
        get_ephemeral_name.return_value = "RELEASE-ARCH"
        expected = ["console=tty1", "console=ttyS0", "nomodeset"]

        params = make_kernel_parameters(
            purpose="commissioning", arch="i386")
        cmdline = compose_kernel_command_line(params)
        self.assertThat(cmdline, ContainsAll(expected))

        params = make_kernel_parameters(
            purpose="install", arch="i386")
        cmdline = compose_kernel_command_line(params)
        self.assertThat(cmdline, ContainsAll(expected))

    def create_ephemeral_info(self, name, arch, release):
        """Create a pseudo-real ephemeral info file."""
        ephemeral_info = """
            release=%s
            stream=ephemeral
            label=release
            serial=20120424
            arch=%s
            name=%s
            """ % (release, arch, name)
        ephemeral_root = self.make_dir()
        config = {"boot": {"ephemeral": {"directory": ephemeral_root}}}
        self.useFixture(ConfigFixture(config))
        ephemeral_dir = os.path.join(
            ephemeral_root, release, 'ephemeral', arch, release)
        os.makedirs(ephemeral_dir)
        factory.make_file(
            ephemeral_dir, name='info', contents=ephemeral_info)

    def test_compose_kernel_command_line_inc_purpose_opts_comm_node(self):
        # The result of compose_kernel_command_line includes the purpose
        # options for a "commissioning" node.
        ephemeral_name = factory.make_name("ephemeral")
        params = make_kernel_parameters(purpose="commissioning")
        self.create_ephemeral_info(
            ephemeral_name, params.arch, params.release)
        self.assertThat(
            compose_kernel_command_line(params),
            ContainsAll([
                "iscsi_target_name=%s:%s" % (
                    ISCSI_TARGET_NAME_PREFIX, ephemeral_name),
                "iscsi_target_port=3260",
                "iscsi_target_ip=%s" % params.fs_host,
                ]))

    def test_compose_kernel_command_line_reports_error_about_missing_dir(self):
        params = make_kernel_parameters(purpose="commissioning")
        missing_dir = factory.make_name('missing-dir')
        config = {"boot": {"ephemeral": {"directory": missing_dir}}}
        self.useFixture(ConfigFixture(config))
        self.assertRaises(
            EphemeralImagesDirectoryNotFound,
            compose_kernel_command_line, params)

    def test_compose_preseed_kernel_opt_returns_kernel_option(self):
        dummy_preseed_url = factory.make_name("url")
        self.assertEqual(
            "auto url=%s" % dummy_preseed_url,
            compose_preseed_opt(dummy_preseed_url))

    def test_compose_kernel_command_line_inc_arm_specific_option(self):
        params = make_kernel_parameters(arch="armhf", subarch="highbank")
        self.assertThat(
            compose_kernel_command_line(params),
            Contains("console=ttyAMA0"))

    def test_compose_kernel_command_line_not_inc_arm_specific_option(self):
        params = make_kernel_parameters(arch="i386")
        self.assertThat(
            compose_kernel_command_line(params),
            Not(Contains("console=ttyAMA0")))
