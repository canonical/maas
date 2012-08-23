# Copyright 2005-2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for provisioning configuration."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from copy import deepcopy
from functools import partial
from getpass import getuser
import os
from textwrap import dedent

from fixtures import EnvironmentVariableFixture
import formencode
from maastesting.factory import factory
from maastesting.testcase import TestCase
from provisioningserver.config import Config
from provisioningserver.testing.config import ConfigFixture
from testtools.matchers import (
    DirExists,
    FileExists,
    MatchesException,
    Raises,
    )
import yaml


class TestConfigFixture(TestCase):
    """Tests for `provisioningserver.testing.config.ConfigFixture`."""

    def exercise_fixture(self, fixture):
        # ConfigFixture arranges a minimal configuration on disk, and exports
        # the configuration filename to the environment so that subprocesses
        # can find it.
        with fixture:
            self.assertThat(fixture.dir, DirExists())
            self.assertThat(fixture.filename, FileExists())
            self.assertEqual(
                {"MAAS_PROVISIONING_SETTINGS": fixture.filename},
                fixture.environ)
            self.assertEqual(
                fixture.filename, os.environ["MAAS_PROVISIONING_SETTINGS"])
            with open(fixture.filename, "rb") as stream:
                self.assertEqual(fixture.config, yaml.safe_load(stream))

    def test_use_minimal(self):
        # With no arguments, ConfigFixture arranges a minimal configuration.
        fixture = ConfigFixture()
        self.exercise_fixture(fixture)

    def test_use_with_config(self):
        # Given a configuration, ConfigFixture can arrange a minimal global
        # configuration with the additional options merged in.
        dummy_logfile = factory.make_name("logfile")
        fixture = ConfigFixture({"logfile": dummy_logfile})
        self.assertEqual(dummy_logfile, fixture.config["logfile"])
        self.exercise_fixture(fixture)


class TestConfig_DEFAULT_FILENAME(TestCase):
    """Tests for `provisioningserver.config.Config.DEFAULT_FILENAME`."""

    def setUp(self):
        super(TestConfig_DEFAULT_FILENAME, self).setUp()
        # Start with a clean environment every time.
        fixture = EnvironmentVariableFixture("MAAS_PROVISIONING_SETTINGS")
        self.useFixture(fixture)

    def test_get_with_environment_empty(self):
        self.assertEqual("/etc/maas/pserv.yaml", Config.DEFAULT_FILENAME)

    def test_get_with_environment_set(self):
        dummy_filename = factory.make_name("config")
        fixture = EnvironmentVariableFixture(
            "MAAS_PROVISIONING_SETTINGS", dummy_filename)
        self.useFixture(fixture)
        self.assertEqual(dummy_filename, Config.DEFAULT_FILENAME)

    def test_set(self):
        dummy_filename = factory.make_name("config")
        Config.DEFAULT_FILENAME = dummy_filename
        self.assertEqual(dummy_filename, Config.DEFAULT_FILENAME)

    def test_delete(self):
        Config.DEFAULT_FILENAME = factory.make_name("config")
        del Config.DEFAULT_FILENAME
        # The filename reverts; see test_get_with_environment_empty.
        self.assertEqual("/etc/maas/pserv.yaml", Config.DEFAULT_FILENAME)
        # The delete does not fail when called multiple times.
        del Config.DEFAULT_FILENAME


class TestConfig(TestCase):
    """Tests for `provisioningserver.config.Config`."""

    default_production_config = {
        'boot': {
            'ephemeral': {
                'directory': '/var/lib/maas/ephemeral',
                },
            },
        'broker': {
            'host': 'localhost',
            'port': 5673,
            'username': getuser(),
            'password': 'test',
            'vhost': '/',
            },
        'logfile': 'pserv.log',
        'oops': {
            'directory': '',
            'reporter': '',
            },
        'tftp': {
            'generator': 'http://localhost/MAAS/api/1.0/pxeconfig/',
            'port': 69,
            'root': "/var/lib/tftpboot",
            },
        }

    default_development_config = deepcopy(default_production_config)
    default_development_config.update(logfile="/dev/null")
    default_development_config["oops"].update(
        directory="logs/oops", reporter="maas-pserv")
    default_development_config["tftp"].update(
        port=5244, generator="http://localhost:5243/api/1.0/pxeconfig/")

    def test_defaults(self):
        # The default configuration is production-ready.
        observed = Config.to_python({})
        self.assertEqual(self.default_production_config, observed)

    def test_parse(self):
        # Configuration can be parsed from a snippet of YAML.
        observed = Config.parse(b'logfile: "/some/where.log"\n')
        self.assertEqual("/some/where.log", observed["logfile"])

    def test_load(self):
        # Configuration can be loaded and parsed from a file.
        config = dedent("""
            logfile: "/some/where.log"
            """)
        filename = self.make_file(name="config.yaml", contents=config)
        observed = Config.load(filename)
        self.assertEqual("/some/where.log", observed["logfile"])

    def test_load_example(self):
        # The example configuration is designed for development.
        filename = os.path.join(
            os.path.dirname(__file__), os.pardir,
            os.pardir, os.pardir, "etc", "pserv.yaml")
        self.assertEqual(
            self.default_development_config,
            Config.load(filename))

    def test_load_from_cache(self):
        # A config loaded by Config.load_from_cache() is never reloaded.
        filename = self.make_file(name="config.yaml", contents='')
        config_before = Config.load_from_cache(filename)
        os.unlink(filename)
        config_after = Config.load_from_cache(filename)
        self.assertIs(config_before, config_after)

    def test_oops_directory_without_reporter(self):
        # It is an error to omit the OOPS reporter if directory is specified.
        config = (
            'oops:\n'
            '  directory: /tmp/oops\n'
            )
        expected = MatchesException(
            formencode.Invalid, "oops: You must give a value for reporter")
        self.assertThat(
            partial(Config.parse, config),
            Raises(expected))

    def test_field(self):
        self.assertIs(Config, Config.field())
        self.assertIs(Config.fields["tftp"], Config.field("tftp"))
        self.assertIs(
            Config.fields["tftp"].fields["root"],
            Config.field("tftp", "root"))
