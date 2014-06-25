# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.power`.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os
import re

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from mock import Mock
import provisioningserver.power.poweraction
from provisioningserver.power.poweraction import (
    PowerAction,
    PowerActionFail,
    UnknownPowerType,
    )
from provisioningserver.utils import (
    locate_config,
    ShellTemplate,
    )
from testtools.matchers import (
    FileContains,
    MatchesException,
    Raises,
    )


class TestPowerAction(MAASTestCase):
    """Tests for PowerAction."""

    def configure_templates_dir(self, path=None):
        """Configure POWER_TEMPLATES_DIR to `path`."""
        self.patch(
            provisioningserver.power.poweraction, 'get_power_templates_dir',
            Mock(return_value=path))

    def test_init_raises_for_unknown_powertype(self):
        powertype = factory.make_name("powertype", sep='')
        self.assertRaises(
            UnknownPowerType,
            PowerAction, powertype)

    def test_init_stores_ether_wake_type(self):
        pa = PowerAction('ether_wake')
        self.assertEqual('ether_wake', pa.power_type)

    def test_init_stores_template_path(self):
        self.configure_templates_dir()
        power_type = 'ether_wake'
        pa = PowerAction(power_type)
        path = os.path.join(pa.template_basedir, power_type + ".template")
        self.assertEqual(path, pa.path)

    def test_template_basedir_defaults_to_config_dir(self):
        self.configure_templates_dir()
        power_type = 'ether_wake'
        self.assertEqual(
            locate_config('templates/power'),
            PowerAction(power_type).template_basedir)

    def test_template_basedir_prefers_configured_value(self):
        power_type = 'ether_wake'
        template_name = '%s.template' % power_type
        template = self.make_file(name=template_name)
        template_dir = os.path.dirname(template)
        self.configure_templates_dir(template_dir)
        self.assertEqual(
            template_dir,
            PowerAction('ether_wake').template_basedir)

    def test_get_template_retrieves_template(self):
        self.configure_templates_dir()
        pa = PowerAction('ether_wake')
        template = pa.get_template()
        self.assertIsInstance(template, ShellTemplate)
        self.assertThat(pa.path, FileContains(template.content))

    def test_get_template_looks_for_template_in_template_basedir(self):
        contents = factory.getRandomString()
        power_type = 'ether_wake'
        template_name = '%s.template' % power_type
        template = self.make_file(name=template_name, contents=contents)
        self.configure_templates_dir(os.path.dirname(template))
        self.assertEqual(
            contents,
            PowerAction(power_type).get_template().content)

    def test_render_template(self):
        # render_template() should take a template string and substitue
        # its variables.
        pa = PowerAction('ether_wake')
        template = ShellTemplate("template: {{mac}}")
        rendered = pa.render_template(template, mac="mymac")
        self.assertEqual("template: mymac", rendered)

    def test_render_template_raises_PowerActionFail(self):
        # If not enough arguments are supplied to fill in template
        # variables then a PowerActionFail is raised.
        pa = PowerAction('ether_wake')
        template_name = factory.getRandomString()
        template = ShellTemplate("template: {{mac}}", name=template_name)
        self.assertThat(
            lambda: pa.render_template(template),
            Raises(MatchesException(
                PowerActionFail,
                ".*name 'mac' is not defined at line \d+ column \d+ "
                "in file %s" % re.escape(template_name))))

    def _create_template_file(self, template):
        """Create a temporary template file with the given contents."""
        return self.make_file("testscript.sh", template)

    def run_action(self, path, **kwargs):
        pa = PowerAction('ether_wake')
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
        self.assertThat(
            lambda: self.run_action(path),
            Raises(MatchesException(
                PowerActionFail, "ether_wake failed.* return.* 127")))

    def test_execute_raises_PowerActionFail_with_output(self):
        path = self._create_template_file("echo reason for failure; exit 1")
        self.assertThat(
            lambda: self.run_action(path),
            Raises(
                MatchesException(PowerActionFail, ".*:\nreason for failure")))

    def test_wake_on_lan_cannot_shut_down_node(self):
        pa = PowerAction('ether_wake')
        self.assertRaises(
            PowerActionFail,
            pa.execute, power_change='off', mac=factory.getRandomMACAddress())

    def test_fence_cdu_checks_state(self):
        # We can't test the fence_cdu template in detail (and it may be
        # customized), but by making it use "echo" instead of a real
        # fence_cdu we can make it get a bogus answer from its status check.
        # The bogus answer is actually the rest of the fence_cdu command
        # line.  It will complain about this and fail.
        action = PowerAction("fence_cdu")
        script = action.render_template(
            action.get_template(), power_change='on',
            power_address='mysystem', power_id='system',
            power_user='me', power_pass='me', fence_cdu='echo')
        output = action.run_shell(script)
        self.assertIn("Got unknown power state from fence_cdu", output)

    def configure_power_config_dir(self, path=None):
        """Configure POWER_CONFIG_DIR to `path`."""
        self.patch(
            provisioningserver.power.poweraction, 'get_power_config_dir',
            Mock(return_value=path))

    def test_config_basedir_defaults_to_local_dir(self):
        self.configure_power_config_dir()
        power_type = 'ether_wake'
        self.assertEqual(
            locate_config('templates/power'),
            PowerAction(power_type).config_basedir)

    def test_ipmi_script_includes_config_dir(self):
        conf_dir = factory.make_name('power_config_dir')
        self.configure_power_config_dir(conf_dir)
        action = PowerAction('ipmi')
        script = action.render_template(
            action.get_template(), power_change='on',
            power_address='mystystem', power_user='me', power_pass='me',
            ipmipower='echo', ipmi_chassis_config='echo', config_dir='dir',
            ipmi_config='file.conf', power_driver='LAN', ip_address='')
        self.assertIn(conf_dir, script)

    def test_moonshot_checks_state(self):
        # We can't test the moonshot template in detail (and it may be
        # customized), but by making it use "echo" instead of a real
        # ipmi we can make it get a bogus answer from its status check.
        # The bogus answer is actually the rest of the ipmi command
        # line.  It will complain about this and fail.
        action = PowerAction("moonshot")
        script = action.render_template(
            action.get_template(), power_change='on',
            power_address='mysystem', power_user='me',
            power_pass='me', power_hwaddress='me', ipmitool='echo')
        output = action.run_shell(script)
        self.assertIn("Got unknown power state from ipmipower", output)

    def test_ucsm_renders_template(self):
        # I'd like to assert that escape_py_literal is being used here,
        # but it's not obvious how to mock things in the template
        # rendering namespace so I passed on that.
        action = PowerAction('ucsm')
        script = action.render_template(
            action.get_template(), power_address='foo',
            power_user='bar', power_pass='baz',
            uuid=factory.getRandomUUID(), power_change='on')
        self.assertIn('power_control_ucsm', script)

    def test_mscm_renders_template(self):
        # I'd like to assert that escape_py_literal is being used here,
        # but it's not obvious how to mock things in the template
        # rendering namespace so I passed on that.
        action = PowerAction('mscm')
        script = action.render_template(
            action.get_template(), power_address='foo',
            power_user='bar', power_pass='baz',
            node_id='c1n1', power_change='on')
        self.assertIn('power_control_mscm', script)
