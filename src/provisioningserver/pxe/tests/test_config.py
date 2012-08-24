# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.pxe.config`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import errno
from os import path
import re

from maastesting.factory import factory
from maastesting.testcase import TestCase
import mock
import posixpath
from provisioningserver.pxe import config
from provisioningserver.pxe.config import render_pxe_config
from provisioningserver.pxe.tftppath import compose_image_path
from provisioningserver.tests.test_kernel_opts import make_kernel_parameters
from testtools.matchers import (
    IsInstance,
    MatchesAll,
    MatchesRegex,
    StartsWith,
    )


class TestFunctions(TestCase):
    """Test for functions in `provisioningserver.pxe.config`."""

    def test_gen_pxe_template_filenames(self):
        purpose = factory.make_name("purpose")
        arch, subarch = factory.make_names("arch", "subarch")
        expected = [
            "config.%s.%s.%s.template" % (purpose, arch, subarch),
            "config.%s.%s.template" % (purpose, arch),
            "config.%s.template" % (purpose, ),
            "config.template",
            ]
        observed = config.gen_pxe_template_filenames(purpose, arch, subarch)
        self.assertSequenceEqual(expected, list(observed))

    @mock.patch("tempita.Template.from_filename")
    @mock.patch.object(config, "gen_pxe_template_filenames")
    def test_get_pxe_template(self, gen_filenames, from_filename):
        purpose = factory.make_name("purpose")
        arch, subarch = factory.make_names("arch", "subarch")
        filename = factory.make_name("filename")
        # Set up the mocks that we've patched in.
        gen_filenames.return_value = [filename]
        from_filename.return_value = mock.sentinel.template
        # The template returned matches the return value above.
        template = config.get_pxe_template(purpose, arch, subarch)
        self.assertEqual(mock.sentinel.template, template)
        # gen_pxe_template_filenames is called to obtain filenames.
        gen_filenames.assert_called_once_with(purpose, arch, subarch)
        # Tempita.from_filename is called with an absolute path derived from
        # the filename returned from gen_pxe_template_filenames.
        from_filename.assert_called_once_with(
            path.join(config.template_dir, filename), encoding="UTF-8")

    def test_get_pxe_template_gets_default(self):
        # There will not be a template matching the following purpose, arch,
        # and subarch, so get_pxe_template() returns the default template.
        purpose = factory.make_name("purpose")
        arch, subarch = factory.make_names("arch", "subarch")
        template = config.get_pxe_template(purpose, arch, subarch)
        self.assertEqual(
            path.join(config.template_dir, "config.template"),
            template.name)

    @mock.patch.object(config, "gen_pxe_template_filenames")
    def test_get_pxe_template_not_found(self, gen_filenames):
        # It is a critical and unrecoverable error if the default PXE template
        # is not found.
        gen_filenames.return_value = []
        self.assertRaises(
            AssertionError, config.get_pxe_template,
            *factory.make_names("purpose", "arch", "subarch"))

    @mock.patch("tempita.Template.from_filename")
    def test_get_pxe_templates_only_suppresses_ENOENT(self, from_filename):
        # The IOError arising from trying to load a template that doesn't
        # exist is suppressed, but other errors are not.
        from_filename.side_effect = IOError()
        from_filename.side_effect.errno = errno.EACCES
        self.assertRaises(
            IOError, config.get_pxe_template,
            *factory.make_names("purpose", "arch", "subarch"))


class TestRenderPXEConfig(TestCase):
    """Tests for `provisioningserver.pxe.config.render_pxe_config`."""

    def test_render(self):
        # Given the right configuration options, the PXE configuration is
        # correctly rendered.
        bootpath = factory.make_name("bootpath")
        params = make_kernel_parameters()
        output = render_pxe_config(bootpath=bootpath, kernel_params=params)
        # The output is always a Unicode string.
        self.assertThat(output, IsInstance(unicode))
        # The template has rendered without error. PXELINUX configurations
        # typically start with a DEFAULT line.
        self.assertThat(output, StartsWith("DEFAULT "))
        # The PXE parameters are all set according to the options.
        image_dir = compose_image_path(
            arch=params.arch, subarch=params.subarch,
            release=params.release, purpose=params.purpose)
        image_dir = posixpath.relpath(image_dir, bootpath)
        self.assertThat(
            output, MatchesAll(
                MatchesRegex(
                    r'.*^\s+KERNEL %s/linux$' % re.escape(image_dir),
                    re.MULTILINE | re.DOTALL),
                MatchesRegex(
                    r'.*^\s+INITRD %s/initrd[.]gz$' % re.escape(image_dir),
                    re.MULTILINE | re.DOTALL),
                MatchesRegex(
                    r'.*^\s+APPEND .+?$',
                    re.MULTILINE | re.DOTALL)))

    def test_render_with_extra_arguments_does_not_affect_output(self):
        # render_pxe_config() allows any keyword arguments as a safety valve.
        options = {
            "bootpath": factory.make_name("bootpath"),
            "kernel_params": make_kernel_parameters(),
            }
        # Capture the output before sprinking in some random options.
        output_before = render_pxe_config(**options)
        # Sprinkle some magic in.
        options.update(
            (factory.make_name("name"), factory.make_name("value"))
            for _ in range(10))
        # Capture the output after sprinking in some random options.
        output_after = render_pxe_config(**options)
        # The generated template is the same.
        self.assertEqual(output_before, output_after)

    def test_render_pxe_config_with_local_purpose(self):
        # If purpose is "local", the config.localboot.template should be
        # used.
        options = {
            "bootpath": factory.make_name("bootpath"),
            "kernel_params":
                make_kernel_parameters()._replace(purpose="local"),
            }
        output = render_pxe_config(**options)
        self.assertIn("LOCALBOOT 0", output)

    def test_render_pxe_config_with_local_purpose_i386_arch(self):
        # Intel i386 is a special case and needs to use the chain.c32
        # loader as the LOCALBOOT PXE directive is unreliable.
        options = {
            "bootpath": factory.make_name("bootpath"),
            "kernel_params": make_kernel_parameters()._replace(
                arch="i386", purpose="local"),
            }
        output = render_pxe_config(**options)
        self.assertIn("chain.c32", output)
        self.assertNotIn("LOCALBOOT", output)

    def test_render_pxe_config_with_local_purpose_amd64_arch(self):
        # Intel amd64 is a special case and needs to use the chain.c32
        # loader as the LOCALBOOT PXE directive is unreliable.
        options = {
            "bootpath": factory.make_name("bootpath"),
            "kernel_params": make_kernel_parameters()._replace(
                arch="amd64", purpose="local"),
            }
        output = render_pxe_config(**options)
        self.assertIn("chain.c32", output)
        self.assertNotIn("LOCALBOOT", output)
