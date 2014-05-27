# Copyright 2005-2014 Canonical Ltd.  This software is licensed under the
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
    "BootSourcesFixture",
    "ConfigFixture",
    "ConfigFixtureBase",
    "set_tftp_root",
    ]

from os import path

from fixtures import (
    EnvironmentVariableFixture,
    Fixture,
    )
from maastesting.fixtures import TempDirectory
from provisioningserver.config import Config
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
    """Fixture to substitute for :class:`Config` in tests."""

    schema = Config


class BootSourcesFixture(Fixture):
    """Fixture to substitute for :class:`BootSources` in tests.

    :ivar sources: A list of dicts defining boot sources.
    :ivar name: Base name for the file that will hold the YAML
        representation of `sources`.  It will be in a temporary directory.
    :ivar filename: Full path to the YAML file.
    """

    def __init__(self, sources, name='sources.yaml'):
        super(BootSourcesFixture, self).__init__()
        self.sources = sources
        self.name = name

    def setUp(self):
        super(BootSourcesFixture, self).setUp()
        self.dir = self.useFixture(TempDirectory()).path
        self.filename = path.join(self.dir, self.name)
        with open(self.filename, 'wb') as stream:
            yaml.safe_dump(self.sources, stream=stream)


def set_tftp_root(tftproot):
    """Create a `ConfigFixture` fixture that sets the TFTP root directory.

    Add the resulting fixture to your test using `self.useFixture`.
    """
    return ConfigFixture({'tftp': {'resource_root': tftproot}})
