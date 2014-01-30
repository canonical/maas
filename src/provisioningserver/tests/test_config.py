# Copyright 2005-2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for provisioning configuration."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from copy import deepcopy
from functools import partial
from getpass import getuser
import os
from textwrap import dedent

from fixtures import EnvironmentVariableFixture
import formencode
from maastesting import root
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.config import Config
from provisioningserver.testing.config import ConfigFixture
from testtools.matchers import (
    DirExists,
    FileContains,
    FileExists,
    MatchesException,
    Raises,
    )
import yaml


class TestConfigFixture(MAASTestCase):
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


class TestConfig_DEFAULT_FILENAME(MAASTestCase):
    """Tests for `provisioningserver.config.Config.DEFAULT_FILENAME`."""

    def set_MAAS_PROVISIONING_SETTINGS(self, filepath=None):
        """Continue this test with a given `MAAS_PROVISIONING_SETTINGS`."""
        self.useFixture(EnvironmentVariableFixture(
            "MAAS_PROVISIONING_SETTINGS", filepath))

    def set_MAAS_CONFIG_DIR(self, dirpath=None):
        """Continue this test with a given `MAAS_CONFIG_DIR`."""
        self.useFixture(EnvironmentVariableFixture("MAAS_CONFIG_DIR", dirpath))

    def make_config(self, name='pserv.yaml'):
        """Create a `pserv.yaml` in a directory of its own."""
        return self.make_file(name=name)

    def test_gets_filename_from_MAAS_PROVISIONING_SETTNGS(self):
        dummy_filename = factory.make_name("config")
        self.set_MAAS_CONFIG_DIR(None)
        self.set_MAAS_PROVISIONING_SETTINGS(dummy_filename)
        self.assertEqual(dummy_filename, Config.DEFAULT_FILENAME)

    def test_falls_back_to_MAAS_CONFIG_DIR(self):
        config_file = self.make_config()
        self.set_MAAS_CONFIG_DIR(os.path.dirname(config_file))
        self.set_MAAS_PROVISIONING_SETTINGS(None)
        self.assertEqual(config_file, Config.DEFAULT_FILENAME)

    def test_MAAS_PROVISIONING_SETTINGS_trumps_MAAS_CONFIG_DIR(self):
        provisioning_settings = factory.make_name("config")
        self.set_MAAS_CONFIG_DIR(os.path.dirname(self.make_config()))
        self.set_MAAS_PROVISIONING_SETTINGS(provisioning_settings)
        self.assertEqual(provisioning_settings, Config.DEFAULT_FILENAME)

    def test_defaults_to_global_config(self):
        self.set_MAAS_CONFIG_DIR(None)
        self.set_MAAS_PROVISIONING_SETTINGS(None)
        self.assertEqual('/etc/maas/pserv.yaml', Config.DEFAULT_FILENAME)

    def test_set(self):
        dummy_filename = factory.make_name("config")
        Config.DEFAULT_FILENAME = dummy_filename
        self.assertEqual(dummy_filename, Config.DEFAULT_FILENAME)

    def test_delete(self):
        self.set_MAAS_CONFIG_DIR(None)
        self.set_MAAS_PROVISIONING_SETTINGS(None)
        Config.DEFAULT_FILENAME = factory.make_name("config")
        del Config.DEFAULT_FILENAME
        # The filename reverts; see test_get_with_environment_empty.
        self.assertEqual("/etc/maas/pserv.yaml", Config.DEFAULT_FILENAME)
        # The delete does not fail when called multiple times.
        del Config.DEFAULT_FILENAME


class TestConfig(MAASTestCase):
    """Tests for `provisioningserver.config.Config`."""

    default_production_config = {
        'boot': {
            'architectures': None,
            'ephemeral': {
                'images_directory': '/var/lib/maas/ephemeral',
                'releases': None,
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
            'root': "/var/lib/maas/tftp",
            },
        }

    default_development_config = deepcopy(default_production_config)
    default_development_config.update(logfile="/dev/null")
    default_development_config["oops"].update(
        directory="logs/oops", reporter="maas-pserv")
    default_development_config["tftp"].update(
        port=5244, generator="http://localhost:5243/api/1.0/pxeconfig/")

    def test_get_defaults_returns_default_config(self):
        # The default configuration is production-ready.
        observed = Config.get_defaults()
        self.assertEqual(self.default_production_config, observed)

    def test_get_defaults_ignores_settings(self):
        self.useFixture(ConfigFixture({'logfile': self.make_file()}))

        self.assertEqual(
            self.default_production_config['logfile'],
            Config.get_defaults()['logfile'])

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

    def test_load_defaults_to_default_filename(self):
        logfile = self.make_file(name='test.log')
        config = yaml.safe_dump({'logfile': logfile})
        filename = self.make_file(name="config.yaml", contents=config)
        self.patch(Config, 'DEFAULT_FILENAME', filename)

        observed = Config.load()

        self.assertEqual(logfile, observed['logfile'])

    def test_load_example(self):
        # The example configuration is designed for development.
        filename = os.path.join(root, "etc", "maas", "pserv.yaml")
        self.assertEqual(
            self.default_development_config,
            Config.load(filename))

    def test_load_from_cache_loads_config(self):
        logfile = self.make_file()
        filename = self.make_file(
            name="config.yaml", contents=yaml.safe_dump({'logfile': logfile}))
        loaded_config = Config.load_from_cache(filename)
        self.assertEqual(logfile, loaded_config['logfile'])

    def test_load_from_cache_uses_defaults(self):
        filename = self.make_file(name='config.yaml', contents='')
        self.assertEqual(
            Config.get_defaults(),
            Config.load_from_cache(filename))

    def test_load_from_cache_caches_each_file_separately(self):
        log1, log2 = self.make_file(), self.make_file()
        config1 = self.make_file(contents=yaml.safe_dump({'logfile': log1}))
        config2 = self.make_file(contents=yaml.safe_dump({'logfile': log2}))

        self.assertEqual(log1, Config.load_from_cache(config1)['logfile'])
        self.assertEqual(log2, Config.load_from_cache(config2)['logfile'])

    def test_load_from_cache_reloads_from_cache_not_from_file(self):
        # A config loaded by Config.load_from_cache() is never reloaded.
        filename = self.make_file(name="config.yaml", contents='')
        config_before = Config.load_from_cache(filename)
        os.unlink(filename)
        config_after = Config.load_from_cache(filename)
        self.assertEqual(config_before, config_after)

    def test_load_from_cache_caches_immutable_copy(self):
        logfile = self.make_file()
        filename = self.make_file(
            name="config.yaml", contents=yaml.safe_dump({'logfile': logfile}))

        first_load = Config.load_from_cache(filename)
        second_load = Config.load_from_cache(filename)

        self.assertEqual(first_load, second_load)
        self.assertIsNot(first_load, second_load)
        first_load['logfile'] = factory.make_name('otherlog')
        self.assertNotEqual(first_load['logfile'], second_load['logfile'])
        self.assertEqual(logfile, second_load['logfile'])
        self.assertIsNot(first_load['boot'], second_load['boot'])
        first_load['boot']['architectures'] = [factory.make_name('otherarch')]
        self.assertNotEqual(
            first_load['boot']['architectures'],
            second_load['boot']['architectures'])

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

    def test_save_and_load_interoperate(self):
        logfile = self.make_file(name='test.log')
        saved_file = self.make_file()

        Config.save({'logfile': logfile}, saved_file)
        loaded_config = Config.load(saved_file)
        self.assertEqual(logfile, loaded_config['logfile'])

    def test_save_saves_yaml_file(self):
        config = {'logfile': self.make_file()}
        saved_file = self.make_file()

        Config.save(config, saved_file)

        with open(saved_file, 'rb') as written_file:
            loaded_config = yaml.load(written_file)
        self.assertEqual(config, loaded_config)

    def test_save_defaults_to_default_filename(self):
        logfile = self.make_file(name='test.log')
        filename = self.make_file(name="config.yaml")
        self.patch(Config, 'DEFAULT_FILENAME', filename)

        Config.save({'logfile': logfile})

        self.assertEqual(logfile, Config.load(filename)['logfile'])

    def test_create_backup_creates_backup(self):
        logfile = self.make_file(name='test.log')
        filename = self.make_file(name="config.yaml")
        config = {'logfile': logfile}
        yaml_config = yaml.safe_dump(config)
        self.patch(Config, 'DEFAULT_FILENAME', filename)
        Config.save(config)

        Config.create_backup('test')

        backup_name = "%s.%s.bak" % (filename, 'test')
        self.assertThat(backup_name, FileContains(yaml_config))
