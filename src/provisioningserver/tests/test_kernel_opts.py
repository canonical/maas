# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test composition of kernel command lines."""

__all__ = [
    "make_kernel_parameters",
    ]

import os

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from mock import sentinel
from provisioningserver import kernel_opts
from provisioningserver.drivers import (
    Architecture,
    ArchitectureRegistry,
)
from provisioningserver.kernel_opts import (
    compose_arch_opts,
    compose_kernel_command_line,
    compose_preseed_opt,
    CURTIN_KERNEL_CMDLINE_NAME,
    get_curtin_kernel_cmdline_sep,
    get_ephemeral_name,
    get_last_directory,
    ISCSI_TARGET_NAME_PREFIX,
    KernelParameters,
    prefix_target_name,
)
from testtools.matchers import (
    Contains,
    ContainsAll,
    Not,
)


def make_kernel_parameters(testcase=None, **parms):
    """Make a randomly populated `KernelParameters` instance.

    If testcase is passed, we poke the generated arch/subarch into the
    ArchitectureRegistry and call addCleanup on the testcase to make sure
    it is removed after the test completes.
    """
    parms.update(
        {field: factory.make_name(field)
         for field in KernelParameters._fields
         if field not in parms})
    params = KernelParameters(**parms)

    if testcase is not None:
        name = "%s/%s" % (params.arch, params.subarch)
        if name in ArchitectureRegistry:
            # It's already there, no need to patch and risk overwriting
            # preset kernel options.
            return params
        resource = Architecture(name, name)
        ArchitectureRegistry.register_item(name, resource)

        testcase.addCleanup(
            ArchitectureRegistry.unregister_item, name)

    return params


class TestUtilitiesKernelOpts(MAASTestCase):

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
        self.assertIs(params._replace.__func__, params.__call__.__func__)

    def test_prefix_target_name_adds_prefix(self):
        prefix = factory.make_name('prefix')
        target = factory.make_name('tgt')
        self.patch(kernel_opts, 'ISCSI_TARGET_NAME_PREFIX', prefix)

        self.assertEqual(
            '%s:%s' % (prefix, target),
            prefix_target_name(target))

    def test_prefix_target_name_produces_exactly_one_separating_colon(self):
        target = factory.make_name('tgt')

        full_name = prefix_target_name(target)

        self.assertIn(':' + target, full_name)
        self.assertNotIn('::' + target, full_name)


class TestGetCurtinKernelCmdlineSepTest(MAASTestCase):

    def test_get_curtin_kernel_cmdline_sep_returns_curtin_value(self):
        sep = factory.make_name('separator')
        self.patch(
            kernel_opts.curtin, CURTIN_KERNEL_CMDLINE_NAME, sep)
        self.assertEqual(sep, get_curtin_kernel_cmdline_sep())

    def test_get_curtin_kernel_cmdline_sep_returns_default(self):
        original_sep = getattr(
            kernel_opts.curtin, CURTIN_KERNEL_CMDLINE_NAME,
            sentinel.missing)

        if original_sep != sentinel.missing:
            def restore_sep():
                setattr(
                    kernel_opts.curtin,
                    CURTIN_KERNEL_CMDLINE_NAME, original_sep)
            self.addCleanup(restore_sep)
            delattr(kernel_opts.curtin, CURTIN_KERNEL_CMDLINE_NAME)
        self.assertEqual('--', get_curtin_kernel_cmdline_sep())


class TestKernelOpts(MAASTestCase):

    def make_kernel_parameters(self, *args, **kwargs):
        return make_kernel_parameters(self, *args, **kwargs)

    def test_compose_kernel_command_line_includes_preseed_url(self):
        params = self.make_kernel_parameters()
        self.assertIn(
            "auto url=%s" % params.preseed_url,
            compose_kernel_command_line(params))

    def test_install_compose_kernel_command_line_includes_name_domain(self):
        params = self.make_kernel_parameters(purpose="install")
        self.assertThat(
            compose_kernel_command_line(params),
            ContainsAll([
                "hostname=%s" % params.hostname,
                "domain=%s" % params.domain,
                ]))

    def test_install_compose_kernel_command_line_omits_domain_if_omitted(self):
        params = self.make_kernel_parameters(purpose="install", domain=None)
        kernel_command_line = compose_kernel_command_line(params)
        self.assertIn("hostname=%s" % params.hostname, kernel_command_line)
        self.assertNotIn('domain=', kernel_command_line)

    def test_install_compose_kernel_command_line_includes_locale(self):
        params = self.make_kernel_parameters(purpose="install")
        locale = "en_US"
        self.assertIn(
            "locale=%s" % locale,
            compose_kernel_command_line(params))

    def test_install_compose_kernel_command_line_includes_log_settings(self):
        params = self.make_kernel_parameters(purpose="install")
        # Port 514 (UDP) is syslog.
        log_port = "514"
        self.assertThat(
            compose_kernel_command_line(params),
            ContainsAll([
                "log_host=%s" % params.log_host,
                "log_port=%s" % log_port,
                ]))

    def test_install_compose_kernel_command_line_includes_di_settings(self):
        params = self.make_kernel_parameters(purpose="install")
        self.assertThat(
            compose_kernel_command_line(params),
            Contains("text priority=critical"))

    def test_install_compose_kernel_command_line_inc_purpose_opts(self):
        # The result of compose_kernel_command_line includes the purpose
        # options for a non "commissioning" node.
        params = self.make_kernel_parameters(purpose="install")
        self.assertIn(
            "netcfg/choose_interface=auto",
            compose_kernel_command_line(params))

    def test_xinstall_compose_kernel_command_line_inc_purpose_opts(self):
        # The result of compose_kernel_command_line includes the purpose
        # options for a non "xinstall" node.
        params = self.make_kernel_parameters(purpose="xinstall")
        cmdline = compose_kernel_command_line(params)
        self.assertThat(
            cmdline,
            ContainsAll([
                "root=/dev/disk/by-path/ip-",
                "iscsi_initiator=",
                "overlayroot=tmpfs",
                "ip=::::%s:BOOTIF" % params.hostname]))

    def test_commissioning_compose_kernel_command_line_inc_purpose_opts(self):
        # The result of compose_kernel_command_line includes the purpose
        # options for a non "commissioning" node.
        params = self.make_kernel_parameters(purpose="commissioning")
        cmdline = compose_kernel_command_line(params)
        self.assertThat(
            cmdline,
            ContainsAll([
                "root=/dev/disk/by-path/ip-",
                "iscsi_initiator=",
                "overlayroot=tmpfs",
                "ip=::::%s:BOOTIF" % params.hostname]))

    def test_enlist_compose_kernel_command_line_inc_purpose_opts(self):
        # The result of compose_kernel_command_line includes the purpose
        # options for a non "commissioning" node.
        params = self.make_kernel_parameters(purpose="enlist")
        cmdline = compose_kernel_command_line(params)
        self.assertThat(
            cmdline,
            ContainsAll([
                "root=/dev/disk/by-path/ip-",
                "iscsi_initiator=",
                "overlayroot=tmpfs",
                "ip=::::%s:BOOTIF" % params.hostname]))

    def test_commissioning_compose_kernel_command_line_inc_extra_opts(self):
        mock_get_curtin_sep = self.patch(
            kernel_opts, 'get_curtin_kernel_cmdline_sep')
        sep = factory.make_name('sep')
        mock_get_curtin_sep.return_value = sep
        extra_opts = "special console=ABCD -- options to pass"
        params = self.make_kernel_parameters(extra_opts=extra_opts)
        cmdline = compose_kernel_command_line(params)
        # There should be KERNEL_CMDLINE_COPY_TO_INSTALL_SEP surrounded by
        # spaces before the options, but otherwise added verbatim.
        self.assertThat(cmdline, Contains(' %s ' % sep + extra_opts))

    def test_commissioning_compose_kernel_handles_extra_opts_None(self):
        params = self.make_kernel_parameters(extra_opts=None)
        cmdline = compose_kernel_command_line(params)
        self.assertNotIn(cmdline, "None")

    def test_compose_kernel_command_line_inc_common_opts(self):
        # Test that some kernel arguments appear on commissioning, install
        # and xinstall command lines.
        expected = ["nomodeset"]

        params = self.make_kernel_parameters(
            purpose="commissioning", arch="i386")
        cmdline = compose_kernel_command_line(params)
        self.assertThat(cmdline, ContainsAll(expected))

        params = self.make_kernel_parameters(
            purpose="xinstall", arch="i386")
        cmdline = compose_kernel_command_line(params)
        self.assertThat(cmdline, ContainsAll(expected))

        params = self.make_kernel_parameters(
            purpose="install", arch="i386")
        cmdline = compose_kernel_command_line(params)
        self.assertThat(cmdline, ContainsAll(expected))

    def test_compose_kernel_command_line_inc_purpose_opts_xinstall_node(self):
        # The result of compose_kernel_command_line includes the purpose
        # options for a "xinstall" node.
        params = self.make_kernel_parameters(purpose="xinstall")
        ephemeral_name = get_ephemeral_name(
            params.osystem, params.arch, params.subarch,
            params.release, params.label)
        self.assertThat(
            compose_kernel_command_line(params),
            ContainsAll([
                "iscsi_target_name=%s:%s" % (
                    ISCSI_TARGET_NAME_PREFIX, ephemeral_name),
                "iscsi_target_port=3260",
                "iscsi_target_ip=%s" % params.fs_host,
                ]))

    def test_compose_kernel_command_line_inc_purpose_opts_comm_node(self):
        # The result of compose_kernel_command_line includes the purpose
        # options for a "commissioning" node.
        params = self.make_kernel_parameters(purpose="commissioning")
        ephemeral_name = get_ephemeral_name(
            params.osystem, params.arch, params.subarch,
            params.release, params.label)
        self.assertThat(
            compose_kernel_command_line(params),
            ContainsAll([
                "iscsi_target_name=%s:%s" % (
                    ISCSI_TARGET_NAME_PREFIX, ephemeral_name),
                "iscsi_target_port=3260",
                "iscsi_target_ip=%s" % params.fs_host,
                ]))

    def test_compose_preseed_kernel_opt_returns_kernel_option(self):
        dummy_preseed_url = factory.make_name("url")
        self.assertEqual(
            "auto url=%s" % dummy_preseed_url,
            compose_preseed_opt(dummy_preseed_url))

    def test_compose_kernel_command_line_inc_arm_specific_option(self):
        params = self.make_kernel_parameters(arch="armhf", subarch="highbank")
        self.assertThat(
            compose_kernel_command_line(params),
            Contains("console=ttyAMA0"))

    def test_compose_kernel_command_line_not_inc_arm_specific_option(self):
        params = self.make_kernel_parameters(arch="i386")
        self.assertThat(
            compose_kernel_command_line(params),
            Not(Contains("console=ttyAMA0")))

    def test_compose_arch_opts_copes_with_unknown_subarch(self):
        # Pass a None testcase so that the architecture doesn't get
        # registered.
        params = make_kernel_parameters(
            testcase=None,
            arch=factory.make_name("arch"),
            subarch=factory.make_name("subarch"))
        self.assertEqual([], compose_arch_opts(params))
