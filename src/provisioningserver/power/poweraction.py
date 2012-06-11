# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Actions for power-related operations."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "PowerAction",
    "PowerActionFail",
    "UnknownPowerType",
    ]


import os
import subprocess

from celeryconfig import POWER_TEMPLATES_DIR
from provisioningserver.utils import ShellTemplate


class UnknownPowerType(Exception):
    """Raised when trying to process an unknown power type."""


class PowerActionFail(Exception):
    """Raised when there's a problem executing a power script."""


class PowerAction:
    """Actions for power-related operations.

    :param power_type: A value from :class:`POWER_TYPE`.

    The class is intended to be used in two phases:
    1. Instantiation, passing the power_type.
    2. .execute(), passing any template parameters required by the template.
    """

    def __init__(self, power_type):
        basedir = POWER_TEMPLATES_DIR
        self.path = os.path.join(basedir, power_type + ".template")
        if not os.path.exists(self.path):
            raise UnknownPowerType(power_type)

        self.power_type = power_type

    def get_template(self):
        with open(self.path, "rb") as f:
            return ShellTemplate(f.read(), name=self.path)

    def render_template(self, template, **kwargs):
        try:
            return template.substitute(kwargs)
        except NameError as error:
            raise PowerActionFail(*error.args)

    def run_shell(self, commands):
        """Execute raw shell script (as rendered from a template).

        :param commands: String containing shell script.
        :param **kwargs: Keyword arguments are passed on to the template as
            substitution values.
        :return: Tuple of strings: stdout, stderr.
        """
        # This might need retrying but it could be better to leave that
        # to the individual scripts.
        try:
            proc = subprocess.Popen(
                commands, shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, close_fds=True)
        except OSError as e:
            raise PowerActionFail(e)

        stdout, stderr = proc.communicate()
        # TODO: log output on errors
        code = proc.returncode
        if code != 0:
            raise PowerActionFail("%s failed with return code %s" % (
                self.power_type, code))
        return stdout, stderr

    def execute(self, **kwargs):
        """Execute the template.

        Any supplied parameters will be passed to the template as substitution
        values.
        """
        template = self.get_template()
        rendered = self.render_template(template, **kwargs)
        self.run_shell(rendered)
