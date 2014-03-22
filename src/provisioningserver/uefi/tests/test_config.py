# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.uefi.config`."""

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
from provisioningserver.pxe.tftppath import compose_image_path
from provisioningserver.tests.test_kernel_opts import make_kernel_parameters
from provisioningserver.uefi.config import render_uefi_config
from testtools.matchers import (
    IsInstance,
    MatchesAll,
    MatchesRegex,
    StartsWith,
    )


class TestRenderUEFIConfig(MAASTestCase):
    """Tests for `provisioningserver.uefi.config.render_uefi_config`."""

    def test_render(self):
        # Given the right configuration options, the UEFI configuration is
        # correctly rendered.
        params = make_kernel_parameters(purpose="install")
        output = render_uefi_config(kernel_params=params)
        # The output is always a Unicode string.
        self.assertThat(output, IsInstance(unicode))
        # The template has rendered without error. UEFI configurations
        # typically start with a DEFAULT line.
        self.assertThat(output, StartsWith("set default=\"0\""))
        # The UEFI parameters are all set according to the options.
        image_dir = compose_image_path(
            arch=params.arch, subarch=params.subarch,
            release=params.release, label=params.label, purpose=params.purpose)

        self.assertThat(
            output, MatchesAll(
                MatchesRegex(
                    r'.*^\s+linux  %s/linux .+?$' % re.escape(image_dir),
                    re.MULTILINE | re.DOTALL),
                MatchesRegex(
                    r'.*^\s+initrd %s/initrd[.]gz$' % re.escape(image_dir),
                    re.MULTILINE | re.DOTALL)))

    def test_render_with_extra_arguments_does_not_affect_output(self):
        # render_uefi_config() allows any keyword arguments as a safety valve.
        options = {
            "kernel_params": make_kernel_parameters(purpose="install"),
        }
        # Capture the output before sprinking in some random options.
        output_before = render_uefi_config(**options)
        # Sprinkle some magic in.
        options.update(
            (factory.make_name("name"), factory.make_name("value"))
            for _ in range(10))
        # Capture the output after sprinking in some random options.
        output_after = render_uefi_config(**options)
        # The generated template is the same.
        self.assertEqual(output_before, output_after)

    def test_render_uefi_config_with_local_purpose(self):
        # If purpose is "local", the config.localboot.template should be
        # used.
        options = {
            "kernel_params": make_kernel_parameters(purpose="local"),
            }
        output = render_uefi_config(**options)
        self.assertIn("chainloader +1", output)
