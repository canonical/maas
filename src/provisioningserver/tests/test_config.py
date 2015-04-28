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

import contextlib
from copy import deepcopy
import errno
from functools import partial
from getpass import getuser
from io import BytesIO
from operator import methodcaller
import os.path
import random
import re
import sqlite3
from textwrap import dedent
from uuid import uuid4

from fixtures import EnvironmentVariableFixture
import formencode
import formencode.validators
from formencode.validators import Invalid
from maastesting import root
from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from mock import sentinel
from provisioningserver.config import (
    BootSources,
    ClusterConfiguration,
    Config,
    ConfigBase,
    ConfigMeta,
    Configuration,
    ConfigurationDatabase,
    ConfigurationFile,
    ConfigurationMeta,
    ConfigurationOption,
    Directory,
    ExtendedURL,
    UUID,
)
from provisioningserver.path import get_path
from provisioningserver.testing.config import ConfigFixtureBase
from provisioningserver.utils.fs import FileLockProxy
from testtools import ExpectedException
from testtools.matchers import (
    DirExists,
    FileContains,
    FileExists,
    Is,
    MatchesException,
    MatchesStructure,
    Raises,
)
from twisted.python.filepath import FilePath
import yaml


class TestUUID(MAASTestCase):
    """Tests for `Directory`."""

    def test__validation_succeeds_when_uuid_is_good(self):
        uuid = unicode(uuid4())
        validator = UUID(accept_python=False)
        self.assertEqual(uuid, validator.from_python(uuid))
        self.assertEqual(uuid, validator.to_python(uuid))

    def test__validation_fails_when_uuid_is_bad(self):
        uuid = unicode(uuid4()) + "can't-be-a-uuid"
        validator = UUID(accept_python=False)
        expected_exception = ExpectedException(
            formencode.validators.Invalid, "^%s$" % re.escape(
                "%r Failed to parse UUID" % uuid))
        with expected_exception:
            validator.from_python(uuid)
        with expected_exception:
            validator.to_python(uuid)


class TestDirectory(MAASTestCase):
    """Tests for `Directory`."""

    def test__validation_succeeds_when_directory_exists(self):
        directory = self.make_dir()
        validator = Directory(accept_python=False)
        self.assertEqual(directory, validator.from_python(directory))
        self.assertEqual(directory, validator.to_python(directory))

    def test__validation_fails_when_directory_does_not_exist(self):
        directory = os.path.join(self.make_dir(), "not-here")
        validator = Directory(accept_python=False)
        expected_exception = ExpectedException(
            formencode.validators.Invalid, "^%s$" % re.escape(
                "%r does not exist or is not a directory" % directory))
        with expected_exception:
            validator.from_python(directory)
        with expected_exception:
            validator.to_python(directory)


class TestExtendedURL(MAASTestCase):
    def setUp(self):
        super(TestExtendedURL, self).setUp()
        self.validator = ExtendedURL(
            require_tld=False,
            accept_python=False)

    def test_takes_numbers_anywhere(self):
        # Could use factory.make_string() here, as it contains
        # digits, but this is a little bit more explicit and
        # clear to troubleshoot.

        hostname = '%dstart' % random.randint(0, 9)
        url = factory.make_simple_http_url(netloc=hostname)

        hostname = 'mid%ddle' % random.randint(0, 9)
        url = factory.make_simple_http_url(netloc=hostname)
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

        hostname = 'end%d' % random.randint(0, 9)
        url = factory.make_simple_http_url(netloc=hostname)
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

    def test_takes_hyphen_but_not_start_or_end(self):
        # Reject leading hyphen
        hostname = '-start'
        url = factory.make_simple_http_url(netloc=hostname)
        with ExpectedException(Invalid, 'That is not a valid URL'):
            self.assertEqual(url, self.validator.to_python(url),
                             "url: %s" % url)

        # Allow hyphens in the middle
        hostname = 'mid-dle'
        url = factory.make_simple_http_url(netloc=hostname)
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

        # Reject trailing hyphen
        hostname = 'end-'
        url = factory.make_simple_http_url(netloc=hostname)
        with ExpectedException(Invalid, 'That is not a valid URL'):
            self.assertEqual(url, self.validator.to_python(url),
                             "url: %s" % url)

    def test_allows_hostnames_as_short_as_a_single_char(self):
        # Single digit
        hostname = unicode(random.randint(0, 9))
        url = factory.make_simple_http_url(netloc=hostname)
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

        # Single char
        hostname = factory.make_string(1)
        url = factory.make_simple_http_url(netloc=hostname)
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

        # Reject single hyphen
        hostname = '-'
        url = factory.make_simple_http_url(netloc=hostname)
        with ExpectedException(Invalid, 'That is not a valid URL'):
            self.assertEqual(url, self.validator.to_python(url),
                             "url: %s" % url)

    def test_allows_hostnames_up_to_63_chars_long(self):
        max_length = 63

        # Alow 63 chars
        hostname = factory.make_string(max_length)
        url = factory.make_simple_http_url(netloc=hostname)
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

        # Reject 64 chars
        hostname = factory.make_string(max_length + 1)
        url = factory.make_simple_http_url(netloc=hostname)
        with ExpectedException(Invalid, 'That is not a valid URL'):
            self.assertEqual(url, self.validator.to_python(url),
                             "url: %s" % url)

    def test_allows_domain_names_up_to_63_chars_long(self):
        max_length = 63

        # Alow 63 chars without hypen
        hostname = '%s.example.com' % factory.make_string(max_length)
        url = factory.make_simple_http_url(netloc=hostname)
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

        # Reject 64 chars without hypen
        hostname = '%s.example.com' % factory.make_string(max_length + 1)
        url = factory.make_simple_http_url(netloc=hostname)
        with ExpectedException(Invalid, 'That is not a valid URL'):
            self.assertEqual(url, self.validator.to_python(url),
                             "url: %s" % url)

        # Alow 63 chars with hypen
        hyphen_loc = random.randint(1, max_length - 1)
        name = factory.make_string(max_length - 1)
        hname = name[:hyphen_loc] + '-' + name[hyphen_loc:]
        hostname = '%s.example.com' % (hname)
        url = factory.make_simple_http_url(netloc=hostname)
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

        # Reject 64 chars with hypen
        hyphen_loc = random.randint(1, max_length)
        name = factory.make_string(max_length)
        hname = name[:hyphen_loc] + '-' + name[hyphen_loc:]
        hostname = '%s.example.com' % (hname)
        url = factory.make_simple_http_url(netloc=hostname)
        with ExpectedException(Invalid, 'That is not a valid URL'):
            self.assertEqual(url, self.validator.to_python(url),
                             "url: %s" % url)


class ExampleConfig(ConfigBase, formencode.Schema):
    """An example configuration schema.

    It derives from :class:`ConfigBase` and has a metaclass derived from
    :class:`ConfigMeta`, just as a "real" schema must.
    """

    class __metaclass__(ConfigMeta):
        envvar = "MAAS_TESTING_SETTINGS"
        default = "example.yaml"

    something = formencode.validators.String(if_missing="*missing*")


class ExampleConfigFixture(ConfigFixtureBase):
    """A fixture to help with testing :class:`ExampleConfig`."""

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

    def make_config_data(self):
        """Return random config data for `ExampleConfig`."""
        return {'something': factory.make_name('value')}

    def make_config_file(self, name=None, data=None):
        """Write a YAML config file, and return its path."""
        if name is None:
            name = factory.make_name('config') + '.yaml'
        if data is None:
            data = self.make_config_data()
        return self.make_file(name=name, contents=yaml.safe_dump(data))

    def test_get_defaults_returns_default_config(self):
        # The default configuration is production-ready.
        observed = ExampleConfig.get_defaults()
        self.assertEqual({"something": "*missing*"}, observed)

    def test_get_defaults_ignores_settings(self):
        self.useFixture(ExampleConfigFixture(self.make_config_data()))
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
        filename = self.make_file(contents=config)
        observed = ExampleConfig.load(filename)
        self.assertEqual({"something": "important"}, observed)

    def test_load_defaults_to_default_filename(self):
        data = self.make_config_data()
        filename = self.make_config_file(name='config.yaml', data=data)
        self.patch(ExampleConfig, 'DEFAULT_FILENAME', filename)
        self.assertEqual(data, ExampleConfig.load())

    def test_load_from_cache_loads_config(self):
        data = self.make_config_data()
        filename = self.make_config_file(data=data)
        self.assertEqual(data, ExampleConfig.load_from_cache(filename))

    def test_load_from_cache_uses_defaults(self):
        filename = self.make_file(contents='')
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
        filename = self.make_config_file()
        config_before = ExampleConfig.load_from_cache(filename)
        os.unlink(filename)
        config_after = ExampleConfig.load_from_cache(filename)
        self.assertEqual(config_before, config_after)

    def test_load_from_cache_caches_immutable_copy(self):
        filename = self.make_config_file()

        first_load = ExampleConfig.load_from_cache(filename)
        second_load = ExampleConfig.load_from_cache(filename)

        self.assertEqual(first_load, second_load)
        self.assertIsNot(first_load, second_load)
        first_load['something'] = factory.make_name('newthing')
        self.assertNotEqual(first_load['something'], second_load['something'])

    def test_flush_cache_without_filename_empties_cache(self):
        filename = self.make_config_file()
        ExampleConfig.load_from_cache(filename)
        os.unlink(filename)
        ExampleConfig.flush_cache()
        error = self.assertRaises(
            IOError,
            ExampleConfig.load_from_cache, filename)
        self.assertEqual(errno.ENOENT, error.errno)

    def test_flush_cache_flushes_specific_file(self):
        filename = self.make_config_file()
        ExampleConfig.load_from_cache(filename)
        os.unlink(filename)
        ExampleConfig.flush_cache(filename)
        error = self.assertRaises(
            IOError,
            ExampleConfig.load_from_cache, filename)
        self.assertEqual(errno.ENOENT, error.errno)

    def test_flush_cache_retains_other_files(self):
        flushed_file = self.make_config_file()
        cached_file = self.make_config_file()
        ExampleConfig.load_from_cache(flushed_file)
        cached_config = ExampleConfig.load_from_cache(cached_file)
        os.unlink(cached_file)
        ExampleConfig.flush_cache(flushed_file)
        self.assertEqual(
            cached_config,
            ExampleConfig.load_from_cache(cached_file))

    def test_flush_cache_ignores_uncached_files(self):
        data = self.make_config_data()
        filename = self.make_config_file(data=data)
        ExampleConfig.flush_cache(filename)
        self.assertEqual(data, ExampleConfig.load_from_cache(filename))

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
            # The "root" setting is obsolete; resource_root replaces it.
            'root': "/var/lib/maas/tftp",
            'resource_root': "/var/lib/maas/boot-resources/current/",
        },
        # Legacy section.  Became unused in MAAS 1.5.
        'boot': {
            'architectures': None,
            'ephemeral': {
                'images_directory': None,
                'releases': None,
            },
        },
    }

    default_development_config = deepcopy(default_production_config)
    default_development_config.update(logfile="/dev/null")
    default_development_config["tftp"].update(
        port=5244, generator="http://localhost:5240/MAAS/api/1.0/pxeconfig/")

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

    def test_accepts_1_4_config_file(self):
        # A config file that was valid with MAAS 1.4 still loads, even though
        # its "boot" section is no longer used.
        broker_password = factory.make_name('pass')
        config = Config.parse(dedent("""\
            logfile: "/dev/null"
            oops:
              directory: "logs/oops"
              reporter: "maas-pserv"
            broker:
              host: "localhost"
              port: 5673
              username: brokeruser
              password: "%s"
              vhost: "/"
            tftp:
              root: /var/lib/maas/tftp
              port: 5244
              generator: http://localhost:5240/api/1.0/pxeconfig/
            boot:
              architectures: ['i386', 'armhf']
              ephemeral:
                images_directory: /var/lib/maas/ephemeral
                releases: ['precise', 'saucy']
            """) % broker_password)
        # This does not fail.
        self.assertEqual(broker_password, config['broker']['password'])


class TestBootSources(MAASTestCase):
    """Tests for `provisioningserver.config.BootSources`."""

    default_source = {
        'url': (
            'http://maas.ubuntu.com/images/ephemeral-v2/releases/'
        ),
        'keyring': (
            '/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg'),
        'keyring_data': None,
        'selections': [
            {
                'os': '*',
                'release': '*',
                'labels': ['*'],
                'arches': ['*'],
                'subarches': ['*'],
            },
        ],
    }

    def make_source(self):
        """Create a dict defining an arbitrary `BootSource`."""
        return {
            'url': 'http://example.com/' + factory.make_name('path'),
            'keyring': factory.make_name('keyring'),
            'keyring_data': factory.make_string(),
            'selections': [{
                'os': factory.make_name('os'),
                'release': factory.make_name('release'),
                'labels': [factory.make_name('label')],
                'arches': [factory.make_name('arch')],
                'subarches': [factory.make_name('sub') for _ in range(3)],
            }],
        }

    def test_parse_parses_source(self):
        sources = [self.make_source()]
        self.assertEqual(
            sources,
            BootSources.parse(BytesIO(yaml.safe_dump(sources))))

    def test_parse_parses_multiple_sources(self):
        sources = [self.make_source() for _ in range(2)]
        self.assertEqual(
            sources,
            BootSources.parse(BytesIO(yaml.safe_dump(sources))))

    def test_parse_uses_defaults(self):
        self.assertEqual(
            [self.default_source],
            BootSources.parse(BytesIO(b'[{}]')))

    def test_load_parses_file(self):
        sources = [self.make_source()]
        self.assertEqual(
            sources,
            BootSources.load(self.make_file(contents=yaml.safe_dump(sources))))


###############################################################################
# New configuration API follows.
###############################################################################


class ExampleConfiguration(Configuration):
    """An example configuration object.

    It derives from :class:`ConfigurationBase` and has a metaclass derived
    from :class:`ConfigurationMeta`, just as a "real" configuration object
    must.
    """

    class __metaclass__(ConfigurationMeta):
        envvar = "MAAS_TESTING_SETTINGS"
        default = get_path("example.db")
        backend = None  # Define this in sub-classes.

    something = ConfigurationOption(
        "something", "Something alright, don't know what, just something.",
        formencode.validators.IPAddress(if_missing=sentinel.missing))


class ExampleConfigurationForDatabase(ExampleConfiguration):
    """An example configuration object using an SQLite3 database."""
    backend = ConfigurationDatabase


class ExampleConfigurationForFile(ExampleConfiguration):
    """An example configuration object using a file."""
    backend = ConfigurationFile


class TestConfigurationMeta(MAASTestCase):
    """Tests for `ConfigurationMeta`."""

    scenarios = (
        ("db", dict(example_configuration=ExampleConfigurationForDatabase)),
        ("file", dict(example_configuration=ExampleConfigurationForFile)),
    )

    def setUp(self):
        super(TestConfigurationMeta, self).setUp()
        self.useFixture(EnvironmentVariableFixture(
            "MAAS_ROOT", self.make_dir()))

    def set_envvar(self, filepath=None):
        """Set the env. variable named by `ExampleConfiguration.envvar"."""
        self.useFixture(EnvironmentVariableFixture(
            self.example_configuration.envvar, filepath))

    def test_gets_filename_from_environment(self):
        dummy_filename = factory.make_name("config")
        self.set_envvar(dummy_filename)
        self.assertEqual(
            dummy_filename, self.example_configuration.DEFAULT_FILENAME)

    def test_falls_back_to_default(self):
        self.set_envvar(None)
        self.assertEqual(
            get_path(self.example_configuration.default),
            self.example_configuration.DEFAULT_FILENAME)

    def test_set(self):
        dummy_filename = factory.make_name("config")
        self.example_configuration.DEFAULT_FILENAME = dummy_filename
        self.assertEqual(
            dummy_filename, self.example_configuration.DEFAULT_FILENAME)

    def test_delete(self):
        self.set_envvar(None)
        example_file = factory.make_name("config")
        self.example_configuration.DEFAULT_FILENAME = example_file
        del self.example_configuration.DEFAULT_FILENAME
        self.assertEqual(
            get_path(self.example_configuration.default),
            self.example_configuration.DEFAULT_FILENAME)
        # The delete does not fail when called multiple times.
        del self.example_configuration.DEFAULT_FILENAME


class TestConfiguration(MAASTestCase):
    """Tests for `Configuration`.

    The most interesting tests that exercise `Configuration` are actually in
    `TestConfigurationOption`.
    """

    def test_create(self):
        config = Configuration({})
        self.assertEqual({}, config.store)

    def test_cannot_set_attributes(self):
        config = Configuration({})
        expected_exception = ExpectedException(
            AttributeError, "^'Configuration' object has no attribute 'foo'$")
        with expected_exception:
            config.foo = "bar"

    def test_opens_using_backend(self):
        config_file = self.make_file()
        backend = self.patch(ExampleConfiguration, "backend")
        with backend.open(config_file) as config:
            backend_ctx = backend.open.return_value
            # The object returned from backend.open() has been used as the
            # context manager, providing `config`.
            self.assertThat(config, Is(backend_ctx.__enter__.return_value))
            # We're within the context, as expected.
            self.assertThat(backend_ctx.__exit__, MockNotCalled())
        # The context has been exited.
        self.assertThat(
            backend_ctx.__exit__,
            MockCalledOnceWith(None, None, None))


class TestConfigurationOption(MAASTestCase):
    """Tests for `ConfigurationOption`."""

    scenarios = (
        ("db", dict(make_store=methodcaller("make_database_store"))),
        ("file", dict(make_store=methodcaller("make_file_store"))),
    )

    def make_database_store(self):
        database = sqlite3.connect(":memory:")
        self.addCleanup(database.close)
        return ConfigurationDatabase(database)

    def make_file_store(self):
        return ConfigurationFile(self.make_file())

    def make_config(self):
        store = self.make_store(self)
        return ExampleConfiguration(store)

    def test_getting_something(self):
        config = self.make_config()
        self.assertIs(sentinel.missing, config.something)

    def test_getting_something_is_not_validated(self):
        # The value in the database is trusted.
        config = self.make_config()
        example_value = factory.make_name('not-an-ip-address')
        config.store[config.__class__.something.name] = example_value
        self.assertEqual(example_value, config.something)

    def test_setting_something(self):
        config = self.make_config()
        example_value = factory.make_ipv4_address()
        config.something = example_value
        self.assertEqual(example_value, config.something)

    def test_setting_something_is_validated(self):
        config = self.make_config()
        with ExpectedException(formencode.validators.Invalid):
            config.something = factory.make_name("not-an-ip-address")

    def test_deleting_something(self):
        config = self.make_config()
        config.something = factory.make_ipv4_address()
        del config.something
        self.assertIs(sentinel.missing, config.something)


class TestConfigurationDatabase(MAASTestCase):
    """Tests for `ConfigurationDatabase`."""

    def test_init(self):
        database = sqlite3.connect(":memory:")
        config = ConfigurationDatabase(database)
        with config.cursor() as cursor:
            # The "configuration" table has been created.
            self.assertEqual(
                cursor.execute(
                    "SELECT COUNT(*) FROM sqlite_master"
                    " WHERE type = 'table'"
                    "   AND name = 'configuration'").fetchone(),
                (1,))

    def test_configuration_pristine(self):
        # A pristine configuration has no entries.
        database = sqlite3.connect(":memory:")
        config = ConfigurationDatabase(database)
        self.assertSetEqual(set(), set(config))

    def test_adding_configuration_option(self):
        database = sqlite3.connect(":memory:")
        config = ConfigurationDatabase(database)
        config["alice"] = {"abc": 123}
        self.assertEqual({"alice"}, set(config))
        self.assertEqual({"abc": 123}, config["alice"])

    def test_replacing_configuration_option(self):
        database = sqlite3.connect(":memory:")
        config = ConfigurationDatabase(database)
        config["alice"] = {"abc": 123}
        config["alice"] = {"def": 456}
        self.assertEqual({"alice"}, set(config))
        self.assertEqual({"def": 456}, config["alice"])

    def test_getting_configuration_option(self):
        database = sqlite3.connect(":memory:")
        config = ConfigurationDatabase(database)
        config["alice"] = {"abc": 123}
        self.assertEqual({"abc": 123}, config["alice"])

    def test_getting_non_existent_configuration_option(self):
        database = sqlite3.connect(":memory:")
        config = ConfigurationDatabase(database)
        self.assertRaises(KeyError, lambda: config["alice"])

    def test_removing_configuration_option(self):
        database = sqlite3.connect(":memory:")
        config = ConfigurationDatabase(database)
        config["alice"] = {"abc": 123}
        del config["alice"]
        self.assertEqual(set(), set(config))

    def test_open_and_close(self):
        # ConfigurationDatabase.open() returns a context manager that closes
        # the database on exit.
        config_file = os.path.join(self.make_dir(), "config")
        config = ConfigurationDatabase.open(config_file)
        self.assertIsInstance(config, contextlib.GeneratorContextManager)
        with config as config:
            self.assertIsInstance(config, ConfigurationDatabase)
            with config.cursor() as cursor:
                self.assertEqual(
                    (1,), cursor.execute("SELECT 1").fetchone())
        self.assertRaises(sqlite3.ProgrammingError, config.cursor)

    def test_open_permissions_new_database(self):
        # ConfigurationDatabase.open() applies restrictive file permissions to
        # newly created configuration databases.
        config_file = os.path.join(self.make_dir(), "config")
        with ConfigurationDatabase.open(config_file):
            perms = FilePath(config_file).getPermissions()
            self.assertEqual("rw-------", perms.shorthand())

    def test_open_permissions_existing_database(self):
        # ConfigurationDatabase.open() leaves the file permissions of existing
        # configuration databases.
        config_file = os.path.join(self.make_dir(), "config")
        open(config_file, "wb").close()  # touch.
        os.chmod(config_file, 0o644)  # u=rw,go=r
        with ConfigurationDatabase.open(config_file):
            perms = FilePath(config_file).getPermissions()
            self.assertEqual("rw-r--r--", perms.shorthand())

    def test_opened_database_commits_on_exit(self):
        config_file = os.path.join(self.make_dir(), "config")
        config_key = factory.make_name("key")
        config_value = factory.make_name("value")
        with ConfigurationDatabase.open(config_file) as config:
            config[config_key] = config_value
        with ConfigurationDatabase.open(config_file) as config:
            self.assertEqual(config_value, config[config_key])

    def test_opened_database_rolls_back_on_unclean_exit(self):
        config_file = os.path.join(self.make_dir(), "config")
        config_key = factory.make_name("key")
        config_value = factory.make_name("value")
        exception_type = factory.make_exception_type()
        # Set a configuration option, then crash.
        with ExpectedException(exception_type):
            with ConfigurationDatabase.open(config_file) as config:
                config[config_key] = config_value
                raise exception_type()
        # No value has been saved for `config_key`.
        with ConfigurationDatabase.open(config_file) as config:
            self.assertRaises(KeyError, lambda: config[config_key])


class TestConfigurationFile(MAASTestCase):
    """Tests for `ConfigurationFile`."""

    def test_configuration_pristine(self):
        # A pristine configuration has no entries.
        config = ConfigurationFile(sentinel.filename)
        self.assertThat(
            config, MatchesStructure.byEquality(
                config={}, dirty=False, path=sentinel.filename))

    def test_adding_configuration_option(self):
        config = ConfigurationFile(sentinel.filename)
        config["alice"] = {"abc": 123}
        self.assertEqual({"alice"}, set(config))
        self.assertEqual({"abc": 123}, config["alice"])
        self.assertTrue(config.dirty)

    def test_replacing_configuration_option(self):
        config = ConfigurationFile(sentinel.filename)
        config["alice"] = {"abc": 123}
        config["alice"] = {"def": 456}
        self.assertEqual({"alice"}, set(config))
        self.assertEqual({"def": 456}, config["alice"])
        self.assertTrue(config.dirty)

    def test_getting_configuration_option(self):
        config = ConfigurationFile(sentinel.filename)
        config["alice"] = {"abc": 123}
        self.assertEqual({"abc": 123}, config["alice"])

    def test_getting_non_existent_configuration_option(self):
        config = ConfigurationFile(sentinel.filename)
        self.assertRaises(KeyError, lambda: config["alice"])

    def test_removing_configuration_option(self):
        config = ConfigurationFile(sentinel.filename)
        config["alice"] = {"abc": 123}
        del config["alice"]
        self.assertEqual(set(), set(config))
        self.assertTrue(config.dirty)

    def test_load_non_existent_file_crashes(self):
        config_file = os.path.join(self.make_dir(), "config")
        config = ConfigurationFile(config_file)
        self.assertRaises(IOError, config.load)

    def test_load_empty_file_results_in_empty_config(self):
        config_file = os.path.join(self.make_dir(), "config")
        with open(config_file, "wb"):
            pass  # Write nothing to the file.
        config = ConfigurationFile(config_file)
        config.load()
        self.assertItemsEqual(set(config), set())

    def test_load_file_with_non_mapping_crashes(self):
        config_file = os.path.join(self.make_dir(), "config")
        with open(config_file, "wb") as fd:
            yaml.safe_dump([1, 2, 3], stream=fd)
        config = ConfigurationFile(config_file)
        error = self.assertRaises(ValueError, config.load)
        self.assertDocTestMatches(
            "Configuration in /.../config is not a mapping: [1, 2, 3]",
            unicode(error))

    def test_open_and_close(self):
        # ConfigurationFile.open() returns a context manager.
        config_file = os.path.join(self.make_dir(), "config")
        config_ctx = ConfigurationFile.open(config_file)
        self.assertIsInstance(config_ctx, contextlib.GeneratorContextManager)
        with config_ctx as config:
            self.assertIsInstance(config, ConfigurationFile)
            self.assertThat(config_file, FileExists())
            self.assertEqual({}, config.config)
            self.assertFalse(config.dirty)
        self.assertThat(config_file, FileContains(""))

    def test_open_permissions_new_database(self):
        # ConfigurationFile.open() applies restrictive file permissions to
        # newly created configuration databases.
        config_file = os.path.join(self.make_dir(), "config")
        with ConfigurationFile.open(config_file):
            perms = FilePath(config_file).getPermissions()
            self.assertEqual("rw-------", perms.shorthand())

    def test_open_permissions_existing_database(self):
        # ConfigurationFile.open() leaves the file permissions of existing
        # configuration databases.
        config_file = os.path.join(self.make_dir(), "config")
        open(config_file, "wb").close()  # touch.
        os.chmod(config_file, 0o644)  # u=rw,go=r
        with ConfigurationFile.open(config_file):
            perms = FilePath(config_file).getPermissions()
            self.assertEqual("rw-r--r--", perms.shorthand())

    def test_opened_configuration_file_saves_on_exit(self):
        # ConfigurationFile.open() returns a context manager that will save an
        # updated configuration on a clean exit.
        config_file = os.path.join(self.make_dir(), "config")
        config_key = factory.make_name("key")
        config_value = factory.make_name("value")
        with ConfigurationFile.open(config_file) as config:
            config[config_key] = config_value
            self.assertEqual({config_key: config_value}, config.config)
            self.assertTrue(config.dirty)
        with ConfigurationFile.open(config_file) as config:
            self.assertEqual(config_value, config[config_key])

    def test_opened_configuration_file_does_not_save_on_unclean_exit(self):
        config_file = os.path.join(self.make_dir(), "config")
        config_key = factory.make_name("key")
        config_value = factory.make_name("value")
        exception_type = factory.make_exception_type()
        # Set a configuration option, then crash.
        with ExpectedException(exception_type):
            with ConfigurationFile.open(config_file) as config:
                config[config_key] = config_value
                raise exception_type()
        # No value has been saved for `config_key`.
        with ConfigurationFile.open(config_file) as config:
            self.assertRaises(KeyError, lambda: config[config_key])

    def test_open_takes_exclusive_lock(self):
        config_file = os.path.join(self.make_dir(), "config")
        config_lock = FileLockProxy(config_file)
        self.assertFalse(config_lock.is_locked())
        with ConfigurationFile.open(config_file):
            self.assertTrue(config_lock.is_locked())
            self.assertTrue(config_lock.i_am_locking())
        self.assertFalse(config_lock.is_locked())


class TestClusterConfiguration(MAASTestCase):
    """Tests for `ClusterConfiguration`."""

    def test_default_maas_url(self):
        config = ClusterConfiguration({})
        self.assertEqual("http://localhost:5240/MAAS", config.maas_url)

    def test_set_and_get_maas_url(self):
        config = ClusterConfiguration({})
        example_url = factory.make_simple_http_url()
        config.maas_url = example_url
        self.assertEqual(example_url, config.maas_url)
        # It's also stored in the configuration database.
        self.assertEqual({"maas_url": example_url}, config.store)

    def test_set_maas_url_accepts_hostnames(self):
        config = ClusterConfiguration({})
        example_url = factory.make_simple_http_url(
            netloc="%s:%d" % (factory.make_hostname(), factory.pick_port()))
        config.maas_url = example_url
        self.assertEqual(example_url, config.maas_url)
        self.assertEqual({"maas_url": example_url}, config.store)

    def test_set_maas_url_accepts_very_short_hostnames(self):
        config = ClusterConfiguration({})
        example_url = factory.make_simple_http_url(
            netloc=factory.make_string(size=1))
        config.maas_url = example_url
        self.assertEqual(example_url, config.maas_url)
        self.assertEqual({"maas_url": example_url}, config.store)

    def test_set_maas_url_accepts_ipv6_addresses(self):
        config = ClusterConfiguration({})
        example_url = factory.make_simple_http_url(
            netloc=factory.make_ipv6_address())
        config.maas_url = example_url
        self.assertEqual(example_url, config.maas_url)
        self.assertEqual({"maas_url": example_url}, config.store)

    def test_set_maas_url_accepts_ipv6_addresses_with_brackets(self):
        config = ClusterConfiguration({})
        example_url = factory.make_simple_http_url(
            netloc="[%s]" % factory.make_ipv6_address())
        config.maas_url = example_url
        self.assertEqual(example_url, config.maas_url)
        self.assertEqual({"maas_url": example_url}, config.store)

    def test_default_tftp_port(self):
        config = ClusterConfiguration({})
        self.assertEqual(69, config.tftp_port)

    def test_set_and_get_tftp_port(self):
        config = ClusterConfiguration({})
        example_port = factory.pick_port()
        config.tftp_port = example_port
        self.assertEqual(example_port, config.tftp_port)
        # It's also stored in the configuration database.
        self.assertEqual({"tftp_port": example_port}, config.store)

    def test_default_tftp_root(self):
        config = ClusterConfiguration({})
        self.assertEqual(
            "/var/lib/maas/boot-resources/current/", config.tftp_root)

    def test_set_and_get_tftp_root(self):
        config = ClusterConfiguration({})
        example_dir = self.make_dir()
        config.tftp_root = example_dir
        self.assertEqual(example_dir, config.tftp_root)
        # It's also stored in the configuration database.
        self.assertEqual({"tftp_root": example_dir}, config.store)
