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
import tempita

from celeryconfig import (
    PXE_TARGET_DIR,
    PXE_TEMPLATES_DIR,
    )
from maastesting.factory import factory
from maastesting.testcase import TestCase
from provisioningserver.pxe.pxeconfig import (
    PXEConfig,
    PXEConfigFail,
    )
from testtools.matchers import (
    FileContains,
    MatchesRegex,
    )


class TestPXEConfig(TestCase):
    """Tests for PXEConfig."""

    def test_init_sets_up_paths(self):
        pxeconfig = PXEConfig("armhf", "armadaxp")

        expected_template = os.path.join(PXE_TEMPLATES_DIR, "maas.template")
        expected_target = os.path.join(
            PXE_TARGET_DIR, "armhf", "armadaxp", "pxelinux.cfg")
        self.assertEqual(expected_template, pxeconfig.template)
        self.assertEqual(expected_target, pxeconfig.target_dir)

    def test_init_with_no_subarch_makes_path_with_generic(self):
        pxeconfig = PXEConfig("i386")
        expected_target = os.path.join(
            PXE_TARGET_DIR, "i386", "generic", "pxelinux.cfg")
        self.assertEqual(expected_target, pxeconfig.target_dir)

    def test_init_with_no_mac_sets_default_filename(self):
        pxeconfig = PXEConfig("armhf", "armadaxp")
        expected_filename = os.path.join(
            PXE_TARGET_DIR, "armhf", "armadaxp", "pxelinux.cfg", "default")
        self.assertEqual(expected_filename, pxeconfig.target_file)

    def test_init_with_dodgy_mac(self):
        # !=5 colons is bad.
        bad_mac = "aa:bb:cc:dd:ee"
        exception = self.assertRaises(
            PXEConfigFail, PXEConfig, "armhf", "armadaxp", bad_mac)
        self.assertEqual(
            exception.message, "Expecting exactly five ':' chars, found 4")

    def test_init_with_mac_sets_filename(self):
        pxeconfig = PXEConfig("armhf", "armadaxp", mac="00:a1:b2:c3:e4:d5")
        expected_filename = os.path.join(
            PXE_TARGET_DIR, "armhf", "armadaxp", "pxelinux.cfg",
            "00-a1-b2-c3-e4-d5")
        self.assertEqual(expected_filename, pxeconfig.target_file)

    def test_get_template(self):
        pxeconfig = PXEConfig("i386")
        template = pxeconfig.get_template()
        self.assertIsInstance(template, tempita.Template)
        self.assertThat(pxeconfig.template, FileContains(template.content))

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

    def test_write_config(self):
        # Ensure that a rendered template is written to the right place.
        out_dir = self.make_dir()
        self.patch(PXEConfig, 'target_basedir', out_dir)
        pxeconfig = PXEConfig("armhf", "armadaxp")
        pxeconfig.write_config(
            menutitle="menutitle", kernelimage="/my/kernel", append="append")

        template = pxeconfig.get_template()
        expected = pxeconfig.render_template(
            template, menutitle="menutitle", kernelimage="/my/kernel",
            append="append")

        self.assertThat(pxeconfig.target_file, FileContains(expected))
