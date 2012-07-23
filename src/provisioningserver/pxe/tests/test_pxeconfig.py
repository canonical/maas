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
from provisioningserver.pxe.tftppath import (
    compose_config_path,
    locate_tftp_path,
    )
from provisioningserver.testing.config import ConfigFixture
import tempita
from testtools.matchers import (
    Contains,
    FileContains,
    MatchesRegex,
    )


class TestPXEConfig(TestCase):
    """Tests for PXEConfig."""

    def setUp(self):
        super(TestPXEConfig, self).setUp()
        self.tftproot = self.make_dir()
        self.config = {"tftp": {"root": self.tftproot}}
        self.useFixture(ConfigFixture(self.config))

    def configure_templates_dir(self, path=None):
        """Configure PXE_TEMPLATES_DIR to `path`."""
        self.patch(
            provisioningserver.pxe.pxeconfig, 'PXE_TEMPLATES_DIR', path)

    def test_init_sets_up_paths(self):
        pxeconfig = PXEConfig("armhf", "armadaxp", tftproot=self.tftproot)

        expected_template = os.path.join(
            pxeconfig.template_basedir, 'maas.template')
        expected_target = os.path.dirname(
            locate_tftp_path(
                compose_config_path('armhf', 'armadaxp', 'default'),
                tftproot=self.tftproot))
        self.assertEqual(expected_template, pxeconfig.template)
        self.assertEqual(
            expected_target, os.path.dirname(pxeconfig.target_file))

    def test_init_with_no_subarch_makes_path_with_generic(self):
        pxeconfig = PXEConfig("i386", tftproot=self.tftproot)
        expected_target = os.path.dirname(
            locate_tftp_path(
                compose_config_path('i386', 'generic', 'default'),
                tftproot=self.tftproot))
        self.assertEqual(
            expected_target, os.path.dirname(pxeconfig.target_file))

    def test_init_with_no_mac_sets_default_filename(self):
        pxeconfig = PXEConfig("armhf", "armadaxp", tftproot=self.tftproot)
        expected_filename = locate_tftp_path(
            compose_config_path('armhf', 'armadaxp', 'default'),
            tftproot=self.tftproot)
        self.assertEqual(expected_filename, pxeconfig.target_file)

    def test_init_with_dodgy_mac(self):
        # !=5 colons is bad.
        bad_mac = "aa:bb:cc:dd:ee"
        exception = self.assertRaises(
            PXEConfigFail, PXEConfig, "armhf", "armadaxp", bad_mac,
            tftproot=self.tftproot)
        self.assertEqual(
            exception.message, "Expecting exactly five ':' chars, found 4")

    def test_init_with_mac_sets_filename(self):
        pxeconfig = PXEConfig(
            "armhf", "armadaxp", mac="00:a1:b2:c3:e4:d5",
            tftproot=self.tftproot)
        expected_filename = locate_tftp_path(
            compose_config_path('armhf', 'armadaxp', '00-a1-b2-c3-e4-d5'),
            tftproot=self.tftproot)
        self.assertEqual(expected_filename, pxeconfig.target_file)

    def test_template_basedir_defaults_to_local_dir(self):
        self.configure_templates_dir()
        arch = factory.make_name('arch')
        self.assertEqual(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 'templates'),
            PXEConfig(arch, tftproot=self.tftproot).template_basedir)

    def test_template_basedir_prefers_configured_value(self):
        temp_dir = self.make_dir()
        self.configure_templates_dir(temp_dir)
        arch = factory.make_name('arch')
        self.assertEqual(
            temp_dir,
            PXEConfig(arch, tftproot=self.tftproot).template_basedir)

    def test_get_template_retrieves_template(self):
        self.configure_templates_dir()
        pxeconfig = PXEConfig("i386", tftproot=self.tftproot)
        template = pxeconfig.get_template()
        self.assertIsInstance(template, tempita.Template)
        self.assertThat(pxeconfig.template, FileContains(template.content))

    def test_get_template_looks_for_template_in_template_basedir(self):
        contents = factory.getRandomString()
        template = self.make_file(name='maas.template', contents=contents)
        self.configure_templates_dir(os.path.dirname(template))
        arch = factory.make_name('arch')
        self.assertEqual(
            contents, PXEConfig(
                arch, tftproot=self.tftproot).get_template().content)

    def test_render_template(self):
        pxeconfig = PXEConfig("i386", tftproot=self.tftproot)
        template = tempita.Template("template: {{kernelimage}}")
        rendered = pxeconfig.render_template(template, kernelimage="myimage")
        self.assertEqual("template: myimage", rendered)

    def test_render_template_raises_PXEConfigFail(self):
        # If not enough arguments are supplied to fill in template
        # variables then a PXEConfigFail is raised.
        pxeconfig = PXEConfig("i386", tftproot=self.tftproot)
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
        tftproot = self.make_dir()
        pxeconfig = PXEConfig("armhf", "armadaxp", tftproot=tftproot)
        template = pxeconfig.get_template()
        expected = pxeconfig.render_template(
            template, menutitle="menutitle", kernelimage="/my/kernel",
            append="append")

        self.assertEqual(
            pxeconfig.get_config(
                 menutitle="menutitle", kernelimage="/my/kernel",
                 append="append"),
            expected)

    def test_write_config_writes_config(self):
        # Ensure that a rendered template is written to the right place.
        tftproot = self.make_dir()
        pxeconfig = PXEConfig("armhf", "armadaxp", tftproot=tftproot)
        pxeconfig.write_config(
            menutitle="menutitle", kernelimage="/my/kernel", append="append")

        template = pxeconfig.get_template()
        expected = pxeconfig.render_template(
            template, menutitle="menutitle", kernelimage="/my/kernel",
            append="append")

        self.assertThat(pxeconfig.target_file, FileContains(expected))

    def test_write_config_overwrites_config(self):
        tftproot = self.make_dir()
        pxeconfig = PXEConfig("amd64", "generic", tftproot=tftproot)
        pxeconfig.write_config(
            menutitle="oldtitle", kernelimage="/old/kernel", append="append")
        pxeconfig = PXEConfig("amd64", "generic", tftproot=tftproot)
        pxeconfig.write_config(
            menutitle="newtitle", kernelimage="/new/kernel", append="append")

        self.assertThat(
            pxeconfig.target_file,
            FileContains(matcher=Contains('newtitle')))
