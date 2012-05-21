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

from maas.celeryconfig import POWER_TEMPLATES_DIR


class UnknownPowerType(Exception):
    """Raised when trying to process an unknown power type."""


class PowerActionFail(Exception):
    """Raised when there's a problem executing a power script."""


class PowerAction:
    """Actions for power-related operations.

    :param power_type: A value from :class:`POWER_TYPE`.

    The class is intended to be used in two phases:
    1. Instatiation, passing the power_type.
    2. .execute(), passing any template parameters required by the template.
    """

    def __init__(self, power_type):
        basedir = POWER_TEMPLATES_DIR
        self.path = os.path.join(basedir, power_type + ".template")
        if not os.path.exists(self.path):
            raise UnknownPowerType

        self.power_type = power_type

    def get_template(self):
        with open(self.path, "r") as f:
            template = f.read()
        return template

    def render_template(self, template, **kwargs):
        try:
            rendered = template % kwargs
        except KeyError, e:
            raise PowerActionFail(
                "Template is missing at least the %s parameter." % e.message)
        return rendered

    def execute(self, **kwargs):
        """Execute the template.

        Any supplied parameters will be passed to the template as substitution
        values.
        """
        template = self.get_template()
        rendered = self.render_template(template, **kwargs)

        # This might need retrying but it could be better to leave that
        # to the individual scripts.
        try:
            proc = subprocess.Popen(
                rendered, shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, close_fds=True)
        except OSError, e:
            raise PowerActionFail(e)

        stdout, stderr = proc.communicate()
        # TODO: log output on errors
        code = proc.returncode
        if code != 0:
            raise PowerActionFail("%s failed with return code %s" % (
                self.power_type, code))
