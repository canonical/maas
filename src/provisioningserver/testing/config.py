# Copyright 2005-2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the psmaas TAP."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "BootConfigFixture",
    "ConfigFixture",
    "ConfigFixtureBase",
    ]

from os import path

from fixtures import (
    EnvironmentVariableFixture,
    Fixture,
    )
from maastesting.fixtures import TempDirectory
from provisioningserver.config import (
    BootConfig,
    Config,
    )
import yaml


class ConfigFixtureBase(Fixture):
    """Base class for creating configuration testing fixtures.

    Subclass this to create a fixture class that'll help with testing
    configuration schemas.

    :cvar schema: A subclass of
        :class:`provisioningserver.config.ConfigBase`.
    """

    schema = None  # Customise this in subclasses.

    def __init__(self, config=None, name='pserv.yaml'):
        super(ConfigFixtureBase, self).__init__()
        self.config = {} if config is None else config
        self.name = name

    def setUp(self):
        super(ConfigFixtureBase, self).setUp()
        # Create a real configuration file, and populate it.
        self.dir = self.useFixture(TempDirectory()).path
        self.filename = path.join(self.dir, self.name)
        with open(self.filename, "wb") as stream:
            yaml.safe_dump(self.config, stream=stream)
        # Export this filename to the environment, so that subprocesses will
        # pick up this configuration. Define the new environment as an
        # instance variable so that users of this fixture can use this to
        # extend custom subprocess environments.
        self.environ = {self.schema.envvar: self.filename}
        for name, value in self.environ.items():
            self.useFixture(EnvironmentVariableFixture(name, value))


class ConfigFixture(ConfigFixtureBase):
    """Fixture to help with testing :class:`Config`."""

    schema = Config


class BootConfigFixture(ConfigFixtureBase):
    """Fixture to help with testing :class:`BootConfig`."""

    schema = BootConfig
