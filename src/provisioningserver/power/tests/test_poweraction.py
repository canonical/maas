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
import re

from celeryconfig import POWER_TEMPLATES_DIR
from maastesting.factory import factory
from maastesting.testcase import TestCase
from provisioningserver.enum import POWER_TYPE
from provisioningserver.power.poweraction import (
    PowerAction,
    PowerActionFail,
    UnknownPowerType,
    )
from provisioningserver.utils import ShellTemplate
from testtools.matchers import (
    FileContains,
    MatchesRegex,
    )


class TestPowerAction(TestCase):
    """Tests for PowerAction."""

    def test_init_raises_for_unknown_powertype(self):
        powertype = factory.make_name("powertype", sep='')
        self.assertRaises(
            UnknownPowerType,
            PowerAction, powertype)

    def test_init_stores_ether_wake_type(self):
        pa = PowerAction(POWER_TYPE.WAKE_ON_LAN)
        self.assertEqual(POWER_TYPE.WAKE_ON_LAN, pa.power_type)

    def test_init_stores_template_path(self):
        power_type = POWER_TYPE.WAKE_ON_LAN
        basedir = POWER_TEMPLATES_DIR
        path = os.path.join(basedir, power_type + ".template")
        pa = PowerAction(power_type)
        self.assertEqual(path, pa.path)

    def test_get_template(self):
        # get_template() should find and read the template file.
        pa = PowerAction(POWER_TYPE.WAKE_ON_LAN)
        template = pa.get_template()
        self.assertIsInstance(template, ShellTemplate)
        with open(pa.path, "rb") as f:
            template_content = f.read()
        self.assertEqual(template_content, template.content)

    def test_render_template(self):
        # render_template() should take a template string and substitue
        # its variables.
        pa = PowerAction(POWER_TYPE.WAKE_ON_LAN)
        template = ShellTemplate("template: {{mac}}")
        rendered = pa.render_template(template, mac="mymac")
        self.assertEqual("template: mymac", rendered)

    def test_render_template_raises_PowerActionFail(self):
        # If not enough arguments are supplied to fill in template
        # variables then a PowerActionFail is raised.
        pa = PowerAction(POWER_TYPE.WAKE_ON_LAN)
        template_name = factory.getRandomString()
        template = ShellTemplate("template: {{mac}}", name=template_name)
        exception = self.assertRaises(
            PowerActionFail, pa.render_template, template)
        self.assertThat(
            exception.message, MatchesRegex(
                "name 'mac' is not defined at line \d+ column \d+ "
                "in file %s" % re.escape(template_name)))

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
        template = "echo working {{mac}} > {{outfile}}"
        path = self._create_template_file(template)

        self.run_action(path, mac="test", outfile=output_file)
        self.assertThat(output_file, FileContains("working test\n"))

    def test_execute_raises_PowerActionFail_when_script_fails(self):
        template = "this_is_not_valid_shell"
        path = self._create_template_file(template)
        exception = self.assertRaises(PowerActionFail, self.run_action, path)
        self.assertEqual(
            "ether_wake failed with return code 127", exception.message)

    def test_wake_on_lan_cannot_shut_down_node(self):
        pa = PowerAction(POWER_TYPE.WAKE_ON_LAN)
        self.assertRaises(
            PowerActionFail,
            pa.execute, power_change='off', mac=factory.getRandomMACAddress())

    def test_virsh_checks_vm_state(self):
        # We can't test the virsh template in detail (and it may be
        # customized), but by making it use "echo" instead of a real
        # virsh we can make it get a bogus answer from its status check.
        # The bogus answer is actually the rest of the virsh command
        # line.  It will complain about this and fail.
        action = PowerAction(POWER_TYPE.VIRSH)
        script = action.render_template(
            action.get_template(), power_change='on',
            power_address='qemu://example.com/', system_id='mysystem',
            power_id='mysystem', username='me', virsh='echo')
        stdout, stderr = action.run_shell(script)
        self.assertIn("Got unknown power state from virsh", stderr)
