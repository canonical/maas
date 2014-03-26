# Copyright 2005-2014 Canonical Ltd.  This software is licensed under the
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
import formencode.validators
from maastesting import root
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.config import (
    BootConfig,
    Config,
    ConfigBase,
    ConfigMeta,
    )
from provisioningserver.testing.config import ConfigFixtureBase
from testtools.matchers import (
    DirExists,
    FileContains,
    FileExists,
    MatchesException,
    Raises,
    )
import yaml


class ExampleConfig(ConfigBase):

    class __metaclass__(ConfigMeta):
        envvar = "MAAS_TESTING_SETTINGS"
        default = "example.yaml"

    something = formencode.validators.String(if_missing="*missing*")


class ExampleConfigFixture(ConfigFixtureBase):

    schema = ExampleConfig


class TestConfigFixtureBase(MAASTestCase):
    """Tests for `ConfigFixtureBase`."""

    def exercise_fixture(self, fixture):
        # ConfigFixtureBase arranges a minimal configuration on disk,
        # and exports the configuration filename to the environment so
        # that subprocesses can find it.
        with fixture:
            self.assertThat(fixture.dir, DirExists())
            self.assertThat(fixture.filename, FileExists())
            self.assertEqual(
                {fixture.schema.envvar: fixture.filename},
                fixture.environ)
            self.assertEqual(
                fixture.filename, os.environ[fixture.schema.envvar])
            with open(fixture.filename, "rb") as stream:
                self.assertEqual(fixture.config, yaml.safe_load(stream))

    def test_use_minimal(self):
        # With no arguments, ConfigFixtureBase arranges a minimal
        # configuration.
        fixture = ExampleConfigFixture()
        self.exercise_fixture(fixture)

    def test_use_with_config(self):
        # Given a configuration, ConfigFixtureBase can arrange a minimal
        # global configuration with the additional options merged in.
        something = self.getUniqueString("something")
        fixture = ExampleConfigFixture({"something": something})
        self.assertEqual(something, fixture.config["something"])
        self.exercise_fixture(fixture)


class TestConfigMeta_DEFAULT_FILENAME(MAASTestCase):
    """Tests for `provisioningserver.config.ConfigBase.DEFAULT_FILENAME`."""

    def set_envvar(self, filepath=None):
        """Continue this test with a given environment variable."""
        self.useFixture(EnvironmentVariableFixture(
            ExampleConfig.envvar, filepath))

    def set_MAAS_CONFIG_DIR(self, dirpath=None):
        """Continue this test with a given `MAAS_CONFIG_DIR`."""
        self.useFixture(EnvironmentVariableFixture("MAAS_CONFIG_DIR", dirpath))

    def make_config(self):
        """Create a config file in a directory of its own."""
        return self.make_file(name=ExampleConfig.default)

    def test_gets_filename_from_MAAS_PROVISIONING_SETTNGS(self):
        dummy_filename = factory.make_name("config")
        self.set_MAAS_CONFIG_DIR(None)
        self.set_envvar(dummy_filename)
        self.assertEqual(dummy_filename, ExampleConfig.DEFAULT_FILENAME)

    def test_falls_back_to_MAAS_CONFIG_DIR(self):
        config_file = self.make_config()
        self.set_MAAS_CONFIG_DIR(os.path.dirname(config_file))
        self.set_envvar(None)
        self.assertEqual(config_file, ExampleConfig.DEFAULT_FILENAME)

    def test_MAAS_PROVISIONING_SETTINGS_trumps_MAAS_CONFIG_DIR(self):
        provisioning_settings = factory.make_name("config")
        self.set_MAAS_CONFIG_DIR(os.path.dirname(self.make_config()))
        self.set_envvar(provisioning_settings)
        self.assertEqual(
            provisioning_settings,
            ExampleConfig.DEFAULT_FILENAME)

    def test_defaults_to_global_config(self):
        self.set_MAAS_CONFIG_DIR(None)
        self.set_envvar(None)
        self.assertEqual(
            '/etc/maas/%s' % ExampleConfig.default,
            ExampleConfig.DEFAULT_FILENAME)

    def test_set(self):
        dummy_filename = factory.make_name("config")
        ExampleConfig.DEFAULT_FILENAME = dummy_filename
        self.assertEqual(dummy_filename, ExampleConfig.DEFAULT_FILENAME)

    def test_delete(self):
        self.set_MAAS_CONFIG_DIR(None)
        self.set_envvar(None)
        ExampleConfig.DEFAULT_FILENAME = factory.make_name("config")
        del ExampleConfig.DEFAULT_FILENAME
        # The filename reverts; see test_get_with_environment_empty.
        self.assertEqual(
            "/etc/maas/%s" % ExampleConfig.default,
            ExampleConfig.DEFAULT_FILENAME)
        # The delete does not fail when called multiple times.
        del ExampleConfig.DEFAULT_FILENAME


class TestConfigBase(MAASTestCase):
    """Tests for `provisioningserver.config.ConfigBase`."""

    def test_get_defaults_returns_default_config(self):
        # The default configuration is production-ready.
        observed = ExampleConfig.get_defaults()
        self.assertEqual({"something": "*missing*"}, observed)

    def test_get_defaults_ignores_settings(self):
        self.useFixture(ExampleConfigFixture({'something': self.make_file()}))
        observed = ExampleConfig.get_defaults()
        self.assertEqual({"something": "*missing*"}, observed)

    def test_parse(self):
        # Configuration can be parsed from a snippet of YAML.
        observed = ExampleConfig.parse(b'something: "important"\n')
        self.assertEqual("important", observed["something"])

    def test_load(self):
        # Configuration can be loaded and parsed from a file.
        config = dedent("""
            something: "important"
            """)
        filename = self.make_file(name="config.yaml", contents=config)
        observed = ExampleConfig.load(filename)
        self.assertEqual({"something": "important"}, observed)

    def test_load_defaults_to_default_filename(self):
        something = self.getUniqueString()
        config = yaml.safe_dump({'something': something})
        filename = self.make_file(name="config.yaml", contents=config)
        self.patch(ExampleConfig, 'DEFAULT_FILENAME', filename)
        observed = ExampleConfig.load()
        self.assertEqual({"something": something}, observed)

    def test_load_from_cache_loads_config(self):
        contents = yaml.safe_dump({'something': 'or other'})
        filename = self.make_file(name="config.yaml", contents=contents)
        loaded_config = ExampleConfig.load_from_cache(filename)
        self.assertEqual({"something": "or other"}, loaded_config)

    def test_load_from_cache_uses_defaults(self):
        filename = self.make_file(name='config.yaml', contents='')
        self.assertEqual(
            ExampleConfig.get_defaults(),
            ExampleConfig.load_from_cache(filename))

    def test_load_from_cache_caches_each_file_separately(self):
        config1 = self.make_file(contents=yaml.safe_dump({'something': "1"}))
        config2 = self.make_file(contents=yaml.safe_dump({'something': "2"}))

        self.assertEqual(
            {"something": "1"},
            ExampleConfig.load_from_cache(config1))
        self.assertEqual(
            {"something": "2"},
            ExampleConfig.load_from_cache(config2))

    def test_load_from_cache_reloads_from_cache_not_from_file(self):
        # A config loaded by Config.load_from_cache() is never reloaded.
        filename = self.make_file(name="config.yaml", contents='')
        config_before = ExampleConfig.load_from_cache(filename)
        os.unlink(filename)
        config_after = ExampleConfig.load_from_cache(filename)
        self.assertEqual(config_before, config_after)

    def test_load_from_cache_caches_immutable_copy(self):
        filename = self.make_file(
            name="config.yaml", contents=yaml.safe_dump(
                {"something": "somewhere"}))

        first_load = ExampleConfig.load_from_cache(filename)
        second_load = ExampleConfig.load_from_cache(filename)

        self.assertEqual(first_load, second_load)
        self.assertIsNot(first_load, second_load)
        first_load['something'] = factory.make_name('newthing')
        self.assertNotEqual(first_load['something'], second_load['something'])

    def test_field(self):
        self.assertIs(ExampleConfig, ExampleConfig.field())
        self.assertIs(
            ExampleConfig.fields["something"],
            ExampleConfig.field("something"))

    def test_save_and_load_interoperate(self):
        something = self.getUniqueString()
        saved_file = self.make_file()

        ExampleConfig.save({'something': something}, saved_file)
        loaded_config = ExampleConfig.load(saved_file)
        self.assertEqual(something, loaded_config['something'])

    def test_save_saves_yaml_file(self):
        config = {'something': self.getUniqueString()}
        saved_file = self.make_file()

        ExampleConfig.save(config, saved_file)

        with open(saved_file, 'rb') as written_file:
            loaded_config = yaml.safe_load(written_file)
        self.assertEqual(config, loaded_config)

    def test_save_defaults_to_default_filename(self):
        something = self.getUniqueString()
        filename = self.make_file(name="config.yaml")
        self.patch(ExampleConfig, 'DEFAULT_FILENAME', filename)

        ExampleConfig.save({'something': something})

        self.assertEqual(
            {'something': something},
            ExampleConfig.load(filename))

    def test_create_backup_creates_backup(self):
        something = self.getUniqueString()
        filename = self.make_file(name="config.yaml")
        config = {'something': something}
        yaml_config = yaml.safe_dump(config)
        self.patch(ExampleConfig, 'DEFAULT_FILENAME', filename)
        ExampleConfig.save(config)

        ExampleConfig.create_backup('test')

        backup_name = "%s.%s.bak" % (filename, 'test')
        self.assertThat(backup_name, FileContains(yaml_config))


class TestConfig(MAASTestCase):
    """Tests for `provisioningserver.config.Config`."""

    default_production_config = {
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
        'rpc': {},
        'tftp': {
            'generator': 'http://localhost/MAAS/api/1.0/pxeconfig/',
            'port': 69,
            'root': "/var/lib/maas/boot-resources/current/",
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

    def test_load_example(self):
        # The example configuration is designed for development.
        filename = os.path.join(root, "etc", "maas", "pserv.yaml")
        self.assertEqual(
            self.default_development_config,
            Config.load(filename))

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


class TestBootConfig(MAASTestCase):
    """Tests for `provisioningserver.config.BootConfig`."""

    default_production_config = {
        'boot': {
            # XXX jtv 2014-03-21, bug=1295479: Obsolete once we start using
            # the new import script.
            'architectures': None,
            'ephemeral': {
                'images_directory': '/var/lib/maas/ephemeral',
                'releases': None,
            },
            'sources': [
                {
                    'path': (
                        'http://maas.ubuntu.com/images/ephemeral/releases/'),
                    'keyring': (
                        '/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg'),
                    'selections': [
                        {
                            'arches': ['*'],
                            'release': '*',
                            'subarches': ['*'],
                        },
                    ],
                },
            ],
            'storage': '/var/lib/maas/boot-resources/',
            'configure_me': False,
        },
    }

    default_development_config = {
        'boot': {
            'architectures': None,
            'ephemeral': {
                'images_directory': '/var/lib/maas/ephemeral',
                'releases': None,
            },
            'sources': [
                {
                    'path': (
                        'http://maas.ubuntu.com/images/ephemeral-v2/daily/'),
                    'keyring': (
                        '/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg'),
                    'selections': [
                        {
                            'arches': ['i386', 'amd64'],
                            'release': 'trusty',
                            'subarches': ['generic'],
                        },
                        {
                            'arches': ['i386', 'amd64'],
                            'release': 'precise',
                            'subarches': ['generic'],
                        },
                    ],
                },
            ],
            'storage': '/var/lib/maas/boot-resources/',
            'configure_me': True,
        },
    }

    def test_get_defaults_returns_default_config(self):
        # The default configuration is production-ready.
        observed = BootConfig.get_defaults()
        self.assertEqual(self.default_production_config, observed)

    def test_load_example(self):
        # The example configuration is designed for development.
        filename = os.path.join(root, "etc", "maas", "bootresources.yaml")
        self.assertEqual(
            self.default_development_config,
            BootConfig.load(filename))
