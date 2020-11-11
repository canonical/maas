# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Fixtures for working with local configuration in the cluster."""

from os import path

from fixtures import EnvironmentVariableFixture, Fixture
import yaml

from maastesting.fixtures import TempDirectory
from provisioningserver.config import BootSources, ClusterConfiguration


class ConfigFixtureBase(Fixture):
    """Base class for creating configuration testing fixtures.

    Subclass this to create a fixture class that'll help with testing
    configuration schemas.

    :cvar schema: A subclass of
        :class:`provisioningserver.config.ConfigBase`.
    """

    schema = None  # Customise this in subclasses.

    def __init__(self, config=None, name="config.yaml"):
        super().__init__()
        self.config = {} if config is None else config
        self.name = name

    def setUp(self):
        super().setUp()
        # Create a real configuration file, and populate it.
        self.dir = self.useFixture(TempDirectory()).path
        self.filename = path.join(self.dir, self.name)
        with open(self.filename, "wb") as stream:
            yaml.safe_dump(self.config, stream=stream, encoding="utf-8")
        # Export this filename to the environment, so that subprocesses will
        # pick up this configuration. Define the new environment as an
        # instance variable so that users of this fixture can use this to
        # extend custom subprocess environments.
        self.environ = {self.schema.envvar: self.filename}
        for name, value in self.environ.items():
            self.useFixture(EnvironmentVariableFixture(name, value))


class BootSourcesFixture(ConfigFixtureBase):
    """Fixture to substitute for :class:`BootSources` in tests.

    :ivar sources: A list of dicts defining boot sources.
    :ivar name: Base name for the file that will hold the YAML
        representation of `sources`.  It will be in a temporary directory.
    :ivar filename: Full path to the YAML file.
    """

    schema = BootSources

    def __init__(self, sources=None, name="sources.yaml"):
        super().__init__(config=sources, name=name)


class ConfigurationFixtureBase(Fixture):
    """Base class for new-style configuration testing fixtures.

    Subclass this to create a fixture class that'll help with testing
    new-style configuration objects.

    :cvar configuration: A subclass of
        :class:`provisioningserver.config.Configuration`.
    """

    configuration = None  # Customise this in subclasses.

    def __init__(self, **options):
        super().__init__()
        self.options = options

    def setUp(self):
        super().setUp()
        # Create a real configuration file, and populate it.
        self.path = path.join(
            self.useFixture(TempDirectory()).path,
            path.basename(self.configuration.DEFAULT_FILENAME),
        )
        with self.configuration.open_for_update(self.path) as config:
            for key, value in self.options.items():
                setattr(config, key, value)
        # Export this filename to the environment, so that subprocesses will
        # pick up this configuration. Define the new environment as an
        # instance variable so that users of this fixture can use this to
        # extend custom subprocess environments.
        self.environ = {self.configuration.envvar: self.path}
        for name, value in self.environ.items():
            self.useFixture(EnvironmentVariableFixture(name, value))


class ClusterConfigurationFixture(ConfigurationFixtureBase):
    """Fixture to configure local cluster settings in tests."""

    configuration = ClusterConfiguration
