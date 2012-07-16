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

from maastesting.factory import factory
from maastesting.testcase import TestCase
from provisioningserver.enum import POWER_TYPE
import provisioningserver.power.poweraction
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

    def configure_templates_dir(self, path=None):
        """Configure POWER_TEMPLATES_DIR to `path`."""
        self.patch(
            provisioningserver.power.poweraction, 'POWER_TEMPLATES_DIR', path)

    def test_init_raises_for_unknown_powertype(self):
        powertype = factory.make_name("powertype", sep='')
        self.assertRaises(
            UnknownPowerType,
            PowerAction, powertype)

    def test_init_stores_ether_wake_type(self):
        pa = PowerAction(POWER_TYPE.WAKE_ON_LAN)
        self.assertEqual(POWER_TYPE.WAKE_ON_LAN, pa.power_type)

    def test_init_stores_template_path(self):
        self.configure_templates_dir()
        power_type = POWER_TYPE.WAKE_ON_LAN
        pa = PowerAction(power_type)
        path = os.path.join(pa.template_basedir, power_type + ".template")
        self.assertEqual(path, pa.path)

    def test_template_basedir_defaults_to_local_dir(self):
        self.configure_templates_dir()
        self.assertEqual(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 'templates'),
            PowerAction(POWER_TYPE.WAKE_ON_LAN).template_basedir)

    def test_template_basedir_prefers_configured_value(self):
        power_type = POWER_TYPE.WAKE_ON_LAN
        template_name = '%s.template' % power_type
        template = self.make_file(name=template_name)
        template_dir = os.path.dirname(template)
        self.configure_templates_dir(template_dir)
        self.assertEqual(
            template_dir,
            PowerAction(POWER_TYPE.WAKE_ON_LAN).template_basedir)

    def test_get_template_retrieves_template(self):
        self.configure_templates_dir()
        pa = PowerAction(POWER_TYPE.WAKE_ON_LAN)
        template = pa.get_template()
        self.assertIsInstance(template, ShellTemplate)
        self.assertThat(pa.path, FileContains(template.content))

    def test_get_template_looks_for_template_in_template_basedir(self):
        contents = factory.getRandomString()
        power_type = POWER_TYPE.WAKE_ON_LAN
        template_name = '%s.template' % power_type
        template = self.make_file(name=template_name, contents=contents)
        self.configure_templates_dir(os.path.dirname(template))
        self.assertEqual(
            contents,
            PowerAction(power_type).get_template().content)

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
        """Create a temporary template file with the given contents."""
        return self.make_file("testscript.sh", template)

    def run_action(self, path, **kwargs):
        pa = PowerAction(POWER_TYPE.WAKE_ON_LAN)
        pa.path = path
        pa.execute(**kwargs)

    def test_execute(self):
        # execute() should run the template through a shell.
        output_file = self.make_file(
            name='output', contents="(Output should go here)")
        template = "echo working {{mac}} > {{outfile}}"
        path = self._create_template_file(template)

        self.run_action(path, mac="test", outfile=output_file)
        self.assertThat(output_file, FileContains("working test\n"))

    def test_execute_raises_PowerActionFail_when_script_fails(self):
        path = self._create_template_file("this_is_not_valid_shell")
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

    def test_ipmi_checks_state(self):
        action = PowerAction(POWER_TYPE.IPMI)
        script = action.render_template(
            action.get_template(), power_change='on',
            power_address='mystystem', power_user='me', power_pass='me',
            power_ipmi_interface='lan', ipmitool='echo')
        stdout, stderr = action.run_shell(script)
        self.assertIn("Got unknown power state from ipmitool", stderr)

    def test_ipmi_lan_checks_state(self):
        action = PowerAction(POWER_TYPE.IPMI_LAN)
        script = action.render_template(
            action.get_template(), power_change='on',
            power_address='mystystem', power_user='me', power_pass='me',
            power_ipmi_interface='lanplus', ipmitool='echo')
        stdout, stderr = action.run_shell(script)
        self.assertIn("Got unknown power state from ipmitool", stderr)
