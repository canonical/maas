# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Actions for power-related operations."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "PowerAction",
    "PowerActionFail",
    "UnknownPowerType",
    ]


import os
import subprocess

from provisioningserver.drivers.power import (
    builtin_power_drivers,
    PowerDriverRegistry,
)
from provisioningserver.utils import (
    escape_py_literal,
    locate_config,
    ShellTemplate,
)
from provisioningserver.utils.network import find_ip_via_arp


def is_power_driver(power_type):
    for power_driver in builtin_power_drivers:
        if power_type == power_driver.name:
            return True
    return False


class UnknownPowerType(Exception):
    """Raised when trying to process an unknown power type."""


class PowerActionFail(Exception):
    """Raised when there's a problem executing a power script."""

    @classmethod
    def from_action(cls, power_action, err):
        message = "%s failed" % power_action.power_type
        is_process_error = isinstance(err, subprocess.CalledProcessError)
        # If the failure is a CalledProcessError, be careful not to call
        # its __str__ as this will include the actual template text
        # (which is the 'command' that was run).
        if is_process_error:
            message += " with return code %s" % err.returncode
            if err.output:
                message += ":\n" + (
                    err.output.decode("utf-8", "replace").strip())
        else:
            message += ":\n%s" % err
        return cls(message)


class PowerAction:
    """Actions for power-related operations.

    :param power_type: A power-type name, e.g. `ipmi`.

    The class is intended to be used in two phases:
    1. Instantiation, passing the power_type.
    2. .execute(), passing any parameters required by the template
       or Python power driver.
    """

    def __init__(self, power_type):
        self.power_driver = is_power_driver(power_type)
        if not self.power_driver:
            self.path = os.path.join(
                self.get_template_basedir(), power_type + ".template")
            if not os.path.exists(self.path):
                raise UnknownPowerType(power_type)

        self.power_type = power_type

    def get_template_basedir(self):
        """Directory where power templates are stored."""
        return locate_config('templates/power')

    def get_config_basedir(self):
        """Directory where power config are stored."""
        # By default, power config lives in the same directory as power
        # templates.  This makes it easy to customize them together.
        return locate_config('templates/power')

    def get_template(self):
        with open(self.path, "rb") as f:
            return ShellTemplate(f.read(), name=self.path)

    def update_context(self, context):
        """Add and manipulate `context` as necessary."""
        context['config_dir'] = self.get_config_basedir()
        context['escape_py_literal'] = escape_py_literal
        if 'mac_address' in context:
            mac_address = context['mac_address']
            ip_address = find_ip_via_arp(mac_address)
            context['ip_address'] = ip_address
        else:
            context.setdefault('ip_address', None)
        return context

    def render_template(self, template, context):
        try:
            return template.substitute(context)
        except NameError as error:
            raise PowerActionFail.from_action(self, error)

    def run_shell(self, commands):
        """Execute raw shell script (as rendered from a template).

        :param commands: String containing shell script.
        :return: Standard output and standard error returned by the execution
            of the shell script.
        :raises: :class:`PowerActionFail`
        """
        # This might need retrying but it could be better to leave that
        # to the individual scripts.
        shell = ("/bin/sh",)
        process = subprocess.Popen(
            shell, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, close_fds=True)
        output, _ = process.communicate(commands)
        if process.wait() == 0:
            return output.strip()
        else:
            raise PowerActionFail.from_action(
                self, subprocess.CalledProcessError(
                    process.returncode, shell, output))

    def execute(self, **context):
        """Execute the power template or the power driver.

        :return: Standard output and standard error returned by the execution
            of the template.

        Any supplied parameters will be passed to the template or power
        driver as substitution values.
        """
        if self.power_driver:
            return self.execute_power_driver(**context)
        else:
            return self.execute_power_template(**context)

    def execute_power_template(self, **context):
        template = self.get_template()
        context = self.update_context(context)
        rendered = self.render_template(
            template=template, context=context)
        return self.run_shell(rendered)

    def execute_power_driver(self, **context):
        power_driver = PowerDriverRegistry[self.power_type]
        # Needed for MACs and IPs
        context = self.update_context(context)
        power_change = context.get('power_change')
        if power_change in ('on', 'off'):
            return power_driver.perform_power(context)
        elif power_change == 'query':
            return power_driver.query(context)
        else:
            raise PowerActionFail(
                "Invalid power change %s" % power_change)
