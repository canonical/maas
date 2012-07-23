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

from functools import partial
from getpass import getuser
import os
from textwrap import dedent

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


class TestConfig(TestCase):
    """Tests for `provisioningserver.config.Config`."""

    def test_defaults(self):
        mandatory = {
            'password': 'killing_joke',
            }
        expected = {
            'broker': {
                'host': 'localhost',
                'port': 5673,
                'username': getuser(),
                'password': 'test',
                'vhost': '/',
                },
            'cobbler': {
                'url': 'http://localhost/cobbler_api',
                'username': getuser(),
                'password': 'test',
                },
            'logfile': 'pserv.log',
            'oops': {
                'directory': '',
                'reporter': '',
                },
            'tftp': {
                'generator': 'http://localhost:5243/api/1.0/pxeconfig',
                'port': 5244,
                'root': "/var/lib/tftpboot",
                },
            'interface': '127.0.0.1',
            'port': 5241,
            'username': getuser(),
            }
        expected.update(mandatory)
        observed = Config.to_python(mandatory)
        self.assertEqual(expected, observed)

    def test_parse(self):
        # Configuration can be parsed from a snippet of YAML.
        observed = Config.parse(
            b'logfile: "/some/where.log"\n'
            b'password: "black_sabbath"\n'
            )
        self.assertEqual("/some/where.log", observed["logfile"])

    def test_load(self):
        # Configuration can be loaded and parsed from a file.
        config = dedent("""
            logfile: "/some/where.log"
            password: "megadeth"
            """)
        filename = self.make_file(name="config.yaml", contents=config)
        observed = Config.load(filename)
        self.assertEqual("/some/where.log", observed["logfile"])

    def test_load_example(self):
        # The example configuration can be loaded and validated.
        filename = os.path.join(
            os.path.dirname(__file__), os.pardir,
            os.pardir, os.pardir, "etc", "pserv.yaml")
        Config.load(filename)

    def test_load_from_cache(self):
        # A config loaded by Config.load_from_cache() is never reloaded.
        filename = self.make_file(
            name="config.yaml", contents='password: irrelevant')
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
