# Copyright 2005-2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the psmaas TAP."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "ConfigFixture",
    ]

from os import path

from fixtures import (
    EnvironmentVariableFixture,
    Fixture,
    TempDir,
    )
from maastesting.factory import factory
import yaml


class ConfigFixture(Fixture):

    def __init__(self, config=None):
        super(ConfigFixture, self).__init__()
        # The smallest config snippet that will validate.
        self.config = {
            "password": factory.getRandomString(),
            }
        if config is not None:
            self.config.update(config)

    def setUp(self):
        super(ConfigFixture, self).setUp()
        # Create a real configuration file, and populate it.
        self.dir = self.useFixture(TempDir()).path
        self.filename = path.join(self.dir, "config.yaml")
        with open(self.filename, "wb") as stream:
            yaml.safe_dump(self.config, stream=stream)
        # Export this filename to the environment, so that subprocesses will
        # pick up this configuration. Define the new environment as an
        # instance variable so that users of this fixture can use this to
        # extend custom subprocess environments.
        self.environ = {"MAAS_PROVISIONING_SETTINGS": self.filename}
        for name, value in self.environ.items():
            self.useFixture(EnvironmentVariableFixture(name, value))
