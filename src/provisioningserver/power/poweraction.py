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

from provisioningserver.utils import (
    escape_py_literal,
    locate_config,
    ShellTemplate,
    )
from provisioningserver.utils.network import find_ip_via_arp


class UnknownPowerType(Exception):
    """Raised when trying to process an unknown power type."""


class PowerActionFail(Exception):
    """Raised when there's a problem executing a power script."""

    def __init__(self, power_action, err):
        self.power_action = power_action
        self.err = err

    def __str__(self):
        message = "%s failed: %s" % (self.power_action.power_type, self.err)
        is_process_error = isinstance(self.err, subprocess.CalledProcessError)
        if is_process_error and self.err.output:
            # Add error output to the message.
            message += ":\n" + self.err.output.strip()
        return message


class PowerAction:
    """Actions for power-related operations.

    :param power_type: A power-type name, e.g. `ipmi`.

    The class is intended to be used in two phases:
    1. Instantiation, passing the power_type.
    2. .execute(), passing any template parameters required by the template.
    """

    def __init__(self, power_type):
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
            raise PowerActionFail(self, error)

    def run_shell(self, commands):
        """Execute raw shell script (as rendered from a template).

        :param commands: String containing shell script.
        :returns: Standard output and standard error returned by the execution
            of the shell script.
        :raises: :class:`PowerActionFail`
        """
        # This might need retrying but it could be better to leave that
        # to the individual scripts.
        try:
            output = subprocess.check_output(
                commands, shell=True, stderr=subprocess.STDOUT, close_fds=True)
        except subprocess.CalledProcessError as e:
            raise PowerActionFail(self, e)
        return output.strip()

    def execute(self, **context):
        """Execute the template.

        :returns: Standard output and standard error returned by the execution
            of the template.

        Any supplied parameters will be passed to the template as substitution
        values.
        """
        template = self.get_template()
        context = self.update_context(context)
        rendered = self.render_template(
            template=template, context=context)
        return self.run_shell(rendered)
