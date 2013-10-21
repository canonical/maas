# Copyright 2012-2013 Canonical Ltd.  This software is licensed under the
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

from celery.app import app_or_default
from provisioningserver.utils import (
    locate_config,
    ShellTemplate,
    )


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


def get_power_templates_dir():
    """Get the power-templates directory from the config."""
    return app_or_default().conf.POWER_TEMPLATES_DIR


def get_power_config_dir():
    """Get the power-config directory from the config."""
    return app_or_default().conf.POWER_CONFIG_DIR


class PowerAction:
    """Actions for power-related operations.

    :param power_type: A value from :class:`POWER_TYPE`.

    The class is intended to be used in two phases:
    1. Instantiation, passing the power_type.
    2. .execute(), passing any template parameters required by the template.
    """

    def __init__(self, power_type):
        self.path = os.path.join(
            self.template_basedir, power_type + ".template")
        if not os.path.exists(self.path):
            raise UnknownPowerType(power_type)

        self.power_type = power_type

    @property
    def template_basedir(self):
        """Directory where power templates are stored."""
        return get_power_templates_dir() or locate_config('templates/power')

    @property
    def config_basedir(self):
        """Directory where power config are stored."""
        # By default, power config lives in the same directory as power
        # templates.  This makes it easy to customize them together.
        return get_power_config_dir() or locate_config('templates/power')

    def get_template(self):
        with open(self.path, "rb") as f:
            return ShellTemplate(f.read(), name=self.path)

    def get_extra_context(self):
        """Extra context used when rending the power templates."""
        return {
            'config_dir': self.config_basedir,
        }

    def render_template(self, template, **kwargs):
        try:
            kwargs.update(self.get_extra_context())
            return template.substitute(kwargs)
        except NameError as error:
            raise PowerActionFail(self, error)

    def run_shell(self, commands):
        """Execute raw shell script (as rendered from a template).

        :param commands: String containing shell script.
        :raises: :class:`PowerActionFail`
        """
        # This might need retrying but it could be better to leave that
        # to the individual scripts.
        try:
            output = subprocess.check_output(
                commands, shell=True, stderr=subprocess.STDOUT, close_fds=True)
        except subprocess.CalledProcessError as e:
            raise PowerActionFail(self, e)
        # This output is only examined in tests, execute just ignores it
        return output

    def execute(self, **kwargs):
        """Execute the template.

        Any supplied parameters will be passed to the template as substitution
        values.
        """
        template = self.get_template()
        rendered = self.render_template(template, **kwargs)
        self.run_shell(rendered)
