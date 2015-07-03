# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
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
from operator import methodcaller
import os.path
import random
import re
import sqlite3
from uuid import uuid4

from fixtures import EnvironmentVariableFixture
import formencode
import formencode.validators
from formencode.validators import Invalid
from maastesting.factory import factory
from maastesting.fixtures import ImportErrorFixture
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from mock import sentinel
from provisioningserver.config import (
    ClusterConfiguration,
    Configuration,
    ConfigurationDatabase,
    ConfigurationFile,
    ConfigurationMeta,
    ConfigurationOption,
    Directory,
    ExtendedURL,
    is_dev_environment,
    UUID,
)
from provisioningserver.path import get_path
from provisioningserver.testing.config import ClusterConfigurationFixture
from provisioningserver.utils.fs import FileLockProxy
from testtools import ExpectedException
from testtools.matchers import (
    FileContains,
    FileExists,
    Is,
    MatchesStructure,
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
            self.assertEqual("rw-r-----", perms.shorthand())

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
            self.assertEqual("rw-r-----", perms.shorthand())

    def test_unmodified_database_retains_permissions(self):
        # ConfigurationFile.open() leaves the file permissions of existing
        # configuration databases if they're not modified.
        config_file = os.path.join(self.make_dir(), "config")
        open(config_file, "wb").close()  # touch.
        os.chmod(config_file, 0o644)  # u=rw,go=r
        with ConfigurationFile.open(config_file):
            perms = FilePath(config_file).getPermissions()
            self.assertEqual("rw-r--r--", perms.shorthand())
        perms = FilePath(config_file).getPermissions()
        self.assertEqual("rw-r--r--", perms.shorthand())

    def test_modified_database_retains_permissions(self):
        # ConfigurationFile.open() leaves the file permissions of existing
        # configuration databases if they're modified.
        config_file = os.path.join(self.make_dir(), "config")
        open(config_file, "wb").close()  # touch.
        os.chmod(config_file, 0o644)  # u=rw,go=r
        with ConfigurationFile.open(config_file) as config:
            perms = FilePath(config_file).getPermissions()
            self.assertEqual("rw-r--r--", perms.shorthand())
            config["foobar"] = "I am a modification"
        perms = FilePath(config_file).getPermissions()
        self.assertEqual("rw-r--r--", perms.shorthand())

    def test_modified_database_uses_safe_permissions_if_file_missing(self):
        # ConfigurationFile.open() uses a sensible u=rw,g=r file mode when
        # saving if the database file has been inexplicably removed. This is
        # the same mode as used when opening a new database.
        config_file = os.path.join(self.make_dir(), "config")
        open(config_file, "wb").close()  # touch.
        os.chmod(config_file, 0o644)  # u=rw,go=r
        with ConfigurationFile.open(config_file) as config:
            config["foobar"] = "I am a modification"
            os.unlink(config_file)
        perms = FilePath(config_file).getPermissions()
        self.assertEqual("rw-r-----", perms.shorthand())

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
        example_url = factory.make_simple_http_url()
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
        maas_root = os.getenv("MAAS_ROOT")
        self.assertIsNotNone(maas_root)
        config = ClusterConfiguration({})
        self.assertEqual(
            os.path.join(maas_root, "var/lib/maas/boot-resources/current"),
            config.tftp_root)

    def test_set_and_get_tftp_root(self):
        config = ClusterConfiguration({})
        example_dir = self.make_dir()
        config.tftp_root = example_dir
        self.assertEqual(example_dir, config.tftp_root)
        # It's also stored in the configuration database.
        self.assertEqual({"tftp_root": example_dir}, config.store)

    def test_default_cluster_uuid(self):
        config = ClusterConfiguration({})
        self.assertEqual("** UUID NOT SET **", config.cluster_uuid)

    def test_set_and_get_cluster_uuid(self):
        example_uuid = uuid4()
        config = ClusterConfiguration({})
        config.cluster_uuid = example_uuid
        self.assertEqual(unicode(example_uuid), config.cluster_uuid)
        # It's also stored in the configuration database.
        self.assertEqual({"cluster_uuid": unicode(example_uuid)}, config.store)


class TestClusterConfigurationTFTPGeneratorURL(MAASTestCase):
    """Tests for `ClusterConfiguration.tftp_generator_url`."""

    def test__is_relative_to_maas_url(self):
        random_url = factory.make_simple_http_url()
        self.useFixture(ClusterConfigurationFixture(maas_url=random_url))
        with ClusterConfiguration.open() as configuration:
            self.assertEqual(
                random_url + "/api/1.0/pxeconfig/",
                configuration.tftp_generator_url)

    def test__strips_trailing_slashes_from_maas_url(self):
        random_url = factory.make_simple_http_url(path="foobar/")
        self.useFixture(ClusterConfigurationFixture(maas_url=random_url))
        with ClusterConfiguration.open() as configuration:
            self.assertEqual(
                random_url.rstrip("/") + "/api/1.0/pxeconfig/",
                configuration.tftp_generator_url)


class TestClusterConfigurationGRUBRoot(MAASTestCase):
    """Tests for `ClusterConfiguration.grub_root`."""

    def test__is_relative_to_tftp_root_without_trailing_slash(self):
        random_dir = self.make_dir().rstrip("/")
        self.useFixture(ClusterConfigurationFixture(tftp_root=random_dir))
        with ClusterConfiguration.open() as configuration:
            self.assertEqual(random_dir + "/grub", configuration.grub_root)

    def test__is_relative_to_tftp_root_with_trailing_slash(self):
        random_dir = self.make_dir().rstrip("/") + "/"
        self.useFixture(ClusterConfigurationFixture(tftp_root=random_dir))
        with ClusterConfiguration.open() as configuration:
            self.assertEqual(random_dir + "grub", configuration.grub_root)


class TestConfig(MAASTestCase):
    """Tests for `maasserver.config`."""

    def test_is_dev_environment_returns_false(self):
        self.useFixture(ImportErrorFixture('maastesting', 'root'))
        self.assertFalse(is_dev_environment())

    def test_is_dev_environment_returns_true(self):
        self.assertTrue(is_dev_environment())
