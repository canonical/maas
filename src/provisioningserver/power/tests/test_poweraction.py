# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.power`.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os
from maastesting.factory import factory
from maastesting.testcase import TestCase
from testtools.matchers import FileContains
from textwrap import dedent

from django.conf import settings
from provisioningserver.enum import POWER_TYPE
from provisioningserver.power.poweraction import (
    PowerAction,
    PowerActionFail,
    UnknownPowerType,
    )


class TestPowerAction(TestCase):
    """Tests for PowerAction."""

    def test_init_raises_for_unknown_powertype(self):
        powertype = "powertype" + factory.getRandomString()
        self.assertRaises(
            UnknownPowerType,
            PowerAction, powertype)

    def test_init_stores_ether_wake_type(self):
        pa = PowerAction(POWER_TYPE.WAKE_ON_LAN)
        self.assertEqual(POWER_TYPE.WAKE_ON_LAN, pa.power_type)

    def test_init_stores_template_path(self):
        power_type = POWER_TYPE.WAKE_ON_LAN
        basedir = settings.POWER_TEMPLATES_DIR
        path = os.path.join(basedir, power_type + ".template")
        pa = PowerAction(power_type)
        self.assertEqual(path, pa.path)

    def test_get_template(self):
        # get_template() should find and read the template file.
        pa = PowerAction(POWER_TYPE.WAKE_ON_LAN)
        with open(pa.path, "r") as f:
            template = f.read()
        self.assertEqual(template, pa.get_template())

    def test_render_template(self):
        # render_template() should take a template string and substitue
        # its variables.
        pa = PowerAction(POWER_TYPE.WAKE_ON_LAN)
        template = "template: %(mac)s"
        rendered = pa.render_template(template, mac="mymac")
        self.assertEqual(
            template % dict(mac="mymac"), rendered)

    def test_render_template_raises_PowerActionFail(self):
        # If not enough arguments are supplied to fill in template
        # variables then a PowerActionFail is raised.
        pa = PowerAction(POWER_TYPE.WAKE_ON_LAN)
        template = "template: %(mac)s"
        exception = self.assertRaises(
            PowerActionFail, pa.render_template, template)
        self.assertEqual(
            "Template is missing at least the mac parameter.",
            exception.message)

    def _create_template_file(self, template):
        return self.make_file("testscript.sh", template)

    def run_action(self, path, **kwargs):
        pa = PowerAction(POWER_TYPE.WAKE_ON_LAN)
        pa.path = path
        pa.execute(**kwargs)

    def test_execute(self):
        # execute() should run the template through a shell.

        # Create a template in a temp dir.
        tempdir = self.make_dir()
        output_file = os.path.join(tempdir, "output")
        template = dedent("""\
            #!/bin/sh
            echo working %(mac)s >""")
        template += output_file
        path = self._create_template_file(template)

        self.run_action(path, mac="test")
        self.assertThat(output_file, FileContains("working test\n"))

    def test_execute_raises_PowerActionFail_when_script_fails(self):
        template = "this_is_not_valid_shell"
        path = self._create_template_file(template)
        exception = self.assertRaises(PowerActionFail, self.run_action, path)
        self.assertEqual(
            "ether_wake failed with return code 127", exception.message)
