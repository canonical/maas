# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.pxe`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os
import re

from maastesting.factory import factory
from maastesting.testcase import TestCase
import provisioningserver.pxe.pxeconfig
from provisioningserver.pxe.pxeconfig import (
    PXEConfig,
    PXEConfigFail,
    )
import tempita
from testtools.matchers import (
    FileContains,
    MatchesRegex,
    )


class TestPXEConfig(TestCase):
    """Tests for PXEConfig."""

    def configure_templates_dir(self, path=None):
        """Configure PXE_TEMPLATES_DIR to `path`."""
        self.patch(
            provisioningserver.pxe.pxeconfig, 'PXE_TEMPLATES_DIR', path)

    def test_init_sets_up_template_path(self):
        pxeconfig = PXEConfig(factory.make_name('arch'))
        self.assertEqual(
            os.path.join(pxeconfig.template_basedir, 'maas.template'),
            PXEConfig("armhf", "armadaxp").template)

    def test_template_basedir_defaults_to_local_dir(self):
        self.configure_templates_dir()
        arch = factory.make_name('arch')
        self.assertEqual(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 'templates'),
            PXEConfig(arch).template_basedir)

    def test_template_basedir_prefers_configured_value(self):
        temp_dir = self.make_dir()
        self.configure_templates_dir(temp_dir)
        arch = factory.make_name('arch')
        self.assertEqual(temp_dir, PXEConfig(arch).template_basedir)

    def test_get_template_retrieves_template(self):
        self.configure_templates_dir()
        pxeconfig = PXEConfig("i386")
        template = pxeconfig.get_template()
        self.assertIsInstance(template, tempita.Template)
        self.assertThat(pxeconfig.template, FileContains(template.content))

    def test_get_template_looks_for_template_in_template_basedir(self):
        contents = factory.getRandomString()
        template = self.make_file(name='maas.template', contents=contents)
        self.configure_templates_dir(os.path.dirname(template))
        arch = factory.make_name('arch')
        self.assertEqual(contents, PXEConfig(arch).get_template().content)

    def test_render_template(self):
        pxeconfig = PXEConfig("i386")
        template = tempita.Template("template: {{kernelimage}}")
        rendered = pxeconfig.render_template(template, kernelimage="myimage")
        self.assertEqual("template: myimage", rendered)

    def test_render_template_raises_PXEConfigFail(self):
        # If not enough arguments are supplied to fill in template
        # variables then a PXEConfigFail is raised.
        pxeconfig = PXEConfig("i386")
        template_name = factory.getRandomString()
        template = tempita.Template(
            "template: {{kernelimage}}", name=template_name)
        exception = self.assertRaises(
            PXEConfigFail, pxeconfig.render_template, template)
        self.assertThat(
            exception.message, MatchesRegex(
                "name 'kernelimage' is not defined at line \d+ column \d+ "
                "in file %s" % re.escape(template_name)))

    def test_get_config_returns_config(self):
        pxeconfig = PXEConfig("armhf", "armadaxp")
        template = pxeconfig.get_template()
        expected = pxeconfig.render_template(
            template, menutitle="menutitle", kernelimage="/my/kernel",
            append="append")

        self.assertEqual(
            pxeconfig.get_config(
                 menutitle="menutitle", kernelimage="/my/kernel",
                 append="append"),
            expected)
