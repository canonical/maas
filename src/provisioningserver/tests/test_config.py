# Copyright 2012-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for provisioning configuration."""

import contextlib
from operator import delitem, methodcaller, setitem
import os.path
import sqlite3
from unittest.mock import sentinel

from fixtures import EnvironmentVariableFixture
import formencode
import formencode.validators
from twisted.python.filepath import FilePath
import yaml

from maastesting.factory import factory
from maastesting.fixtures import ImportErrorFixture
from maastesting.testcase import MAASTestCase
from provisioningserver import config as config_module
from provisioningserver.config import (
    ClusterConfiguration,
    Configuration,
    ConfigurationDatabase,
    ConfigurationFile,
    ConfigurationImmutable,
    ConfigurationMeta,
    ConfigurationOption,
    debug_enabled,
    is_dev_environment,
)
from provisioningserver.path import get_data_path
from provisioningserver.testing.config import ClusterConfigurationFixture
from provisioningserver.utils.fs import RunLock

###############################################################################
# New configuration API follows.
###############################################################################


class ExampleConfigurationMeta(ConfigurationMeta):
    envvar = "MAAS_TESTING_SETTINGS"
    default = get_data_path("example.db")
    backend = None  # Define this in sub-classes.


class ExampleConfiguration(Configuration, metaclass=ExampleConfigurationMeta):
    """An example configuration object.

    It derives from :class:`ConfigurationBase` and has a metaclass derived
    from :class:`ConfigurationMeta`, just as a "real" configuration object
    must.
    """

    something = ConfigurationOption(
        "something",
        "Something alright, don't know what, just something.",
        formencode.validators.IPAddress(if_missing=sentinel.missing),
    )


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

    def set_envvar(self, filepath=None):
        """Set the env. variable named by `ExampleConfiguration.envvar"."""
        self.useFixture(
            EnvironmentVariableFixture(
                self.example_configuration.envvar, filepath
            )
        )

    def test_gets_filename_from_environment(self):
        dummy_filename = factory.make_name("config")
        self.set_envvar(dummy_filename)
        self.assertEqual(
            dummy_filename, self.example_configuration.DEFAULT_FILENAME
        )

    def test_falls_back_to_default(self):
        self.set_envvar(None)
        self.assertEqual(
            get_data_path(self.example_configuration.default),
            self.example_configuration.DEFAULT_FILENAME,
        )

    def test_set(self):
        dummy_filename = factory.make_name("config")
        self.example_configuration.DEFAULT_FILENAME = dummy_filename
        self.assertEqual(
            dummy_filename, self.example_configuration.DEFAULT_FILENAME
        )

    def test_delete(self):
        self.set_envvar(None)
        example_file = factory.make_name("config")
        self.example_configuration.DEFAULT_FILENAME = example_file
        del self.example_configuration.DEFAULT_FILENAME
        self.assertEqual(
            get_data_path(self.example_configuration.default),
            self.example_configuration.DEFAULT_FILENAME,
        )
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
        with self.assertRaisesRegex(
            AttributeError, "^'Configuration' object has no attribute 'foo'$"
        ):
            config.foo = "bar"

    def test_open_uses_backend_as_context_manager(self):
        config_file = self.make_file()
        backend = self.patch(ExampleConfiguration, "backend")
        with ExampleConfiguration.open(config_file) as config:
            # The backend was opened using open() too.
            backend.open.assert_called_once_with(config_file)
            # The object returned from backend.open() has been used as the
            # context manager, providing `config`.
            backend_ctx = backend.open.return_value
            self.assertIs(config.store, backend_ctx.__enter__.return_value)
            # We're within the context, as expected.
            backend_ctx.__exit__.assert_not_called()
        # The backend context has also been exited.
        backend_ctx.__exit__.assert_called_once_with(None, None, None)

    def test_open_for_update_uses_backend_as_context_manager(self):
        config_file = self.make_file()
        backend = self.patch(ExampleConfiguration, "backend")
        with ExampleConfiguration.open_for_update(config_file) as config:
            # The backend was opened using open_for_update() too.
            backend.open_for_update.assert_called_once_with(config_file)
            # The object returned from backend.open_for_update() has been used
            # as the context manager, providing `config`.
            backend_ctx = backend.open_for_update.return_value
            self.assertIs(config.store, backend_ctx.__enter__.return_value)
            # We're within the context, as expected.
            backend_ctx.__exit__.assert_not_called()
        # The backend context has also been exited.
        backend_ctx.__exit__.assert_called_once_with(None, None, None)


class TestConfigurationOption(MAASTestCase):
    """Tests for `ConfigurationOption`."""

    scenarios = (
        ("db", dict(make_store=methodcaller("make_database_store"))),
        ("file", dict(make_store=methodcaller("make_file_store"))),
    )

    def make_database_store(self):
        database = sqlite3.connect(":memory:")
        self.addCleanup(database.close)
        return ConfigurationDatabase(database, mutable=True)

    def make_file_store(self):
        return ConfigurationFile(self.make_file(), mutable=True)

    def make_config(self):
        store = self.make_store(self)
        return ExampleConfiguration(store)

    def test_getting_something(self):
        config = self.make_config()
        self.assertIs(sentinel.missing, config.something)

    def test_getting_something_is_not_validated(self):
        # The value in the database is trusted.
        config = self.make_config()
        example_value = factory.make_name("not-an-ip-address")
        config.store[config.__class__.something.name] = example_value
        self.assertEqual(example_value, config.something)

    def test_setting_something(self):
        config = self.make_config()
        example_value = factory.make_ipv4_address()
        config.something = example_value
        self.assertEqual(example_value, config.something)

    def test_setting_something_is_validated(self):
        config = self.make_config()
        with self.assertRaisesRegex(
            formencode.validators.Invalid, "^Please enter a valid IP address"
        ):
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
                    "   AND name = 'configuration'"
                ).fetchone(),
                (1,),
            )

    def test_configuration_pristine(self):
        # A pristine configuration has no entries.
        database = sqlite3.connect(":memory:")
        config = ConfigurationDatabase(database)
        self.assertSetEqual(set(), set(config))

    def test_adding_configuration_option(self):
        database = sqlite3.connect(":memory:")
        config = ConfigurationDatabase(database, mutable=True)
        config["alice"] = {"abc": 123}
        self.assertEqual({"alice"}, set(config))
        self.assertEqual({"abc": 123}, config["alice"])

    def test_replacing_configuration_option(self):
        database = sqlite3.connect(":memory:")
        config = ConfigurationDatabase(database, mutable=True)
        config["alice"] = {"abc": 123}
        config["alice"] = {"def": 456}
        self.assertEqual({"alice"}, set(config))
        self.assertEqual({"def": 456}, config["alice"])

    def test_getting_configuration_option(self):
        database = sqlite3.connect(":memory:")
        config = ConfigurationDatabase(database, mutable=True)
        config["alice"] = {"abc": 123}
        self.assertEqual({"abc": 123}, config["alice"])

    def test_getting_non_existent_configuration_option(self):
        database = sqlite3.connect(":memory:")
        config = ConfigurationDatabase(database)
        self.assertRaises(KeyError, lambda: config["alice"])

    def test_removing_configuration_option(self):
        database = sqlite3.connect(":memory:")
        config = ConfigurationDatabase(database, mutable=True)
        config["alice"] = {"abc": 123}
        del config["alice"]
        self.assertEqual(set(), set(config))

    def test_open_and_close(self):
        # ConfigurationDatabase.open() returns a context manager that closes
        # the database on exit.
        config_file = os.path.join(self.make_dir(), "config")
        config = ConfigurationDatabase.open_for_update(config_file)
        self.assertIsInstance(config, contextlib._GeneratorContextManager)
        with config as config:
            self.assertIsInstance(config, ConfigurationDatabase)
            with config.cursor() as cursor:
                self.assertEqual((1,), cursor.execute("SELECT 1").fetchone())
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
        with ConfigurationDatabase.open_for_update(config_file) as config:
            config[config_key] = config_value
        with ConfigurationDatabase.open(config_file) as config:
            self.assertEqual(config_value, config[config_key])

    def test_opened_database_rolls_back_on_unclean_exit(self):
        config_file = os.path.join(self.make_dir(), "config")
        config_key = factory.make_name("key")
        config_value = factory.make_name("value")
        exception_type = factory.make_exception_type()
        # Set a configuration option, then crash.
        with self.assertRaisesRegex(exception_type, "^$"):
            with ConfigurationDatabase.open_for_update(config_file) as config:
                config[config_key] = config_value
                raise exception_type()
        # No value has been saved for `config_key`.
        with ConfigurationDatabase.open(config_file) as config:
            self.assertRaises(KeyError, lambda: config[config_key])

    def test_as_string(self):
        database = sqlite3.connect(":memory:")
        config = ConfigurationDatabase(database)
        self.assertEqual("ConfigurationDatabase(main=:memory:)", str(config))


class TestConfigurationDatabaseMutability(MAASTestCase):
    """Tests for `ConfigurationDatabase` mutability."""

    def test_immutable(self):
        database = sqlite3.connect(":memory:")
        config = ConfigurationDatabase(database, mutable=False)
        self.assertRaises(ConfigurationImmutable, setitem, config, "alice", 1)
        self.assertRaises(ConfigurationImmutable, delitem, config, "alice")

    def test_mutable(self):
        database = sqlite3.connect(":memory:")
        config = ConfigurationDatabase(database, mutable=True)
        config["alice"] = 1234
        del config["alice"]

    def test_open_yields_immutable_backend(self):
        config_file = os.path.join(self.make_dir(), "config")
        config_key = factory.make_name("key")
        with ConfigurationDatabase.open(config_file) as config:
            with self.assertRaisesRegex(
                ConfigurationImmutable, f"Cannot set `{config_key}'"
            ):
                config[config_key] = factory.make_name("value")
            with self.assertRaisesRegex(
                ConfigurationImmutable, f"Cannot set `{config_key}'"
            ):
                del config[config_key]

    def test_open_for_update_yields_mutable_backend(self):
        config_file = os.path.join(self.make_dir(), "config")
        config_key = factory.make_name("key")
        with ConfigurationDatabase.open_for_update(config_file) as config:
            config[config_key] = factory.make_name("value")
            del config[config_key]


class TestConfigurationFile(MAASTestCase):
    """Tests for `ConfigurationFile`."""

    def test_configuration_pristine(self):
        # A pristine configuration has no entries.
        config = ConfigurationFile(sentinel.filename)
        self.assertEqual(config.config, {})
        self.assertFalse(config.dirty)
        self.assertEqual(config.path, sentinel.filename)

    def test_adding_configuration_option(self):
        config = ConfigurationFile(sentinel.filename, mutable=True)
        config["alice"] = {"abc": 123}
        self.assertEqual({"alice"}, set(config))
        self.assertEqual({"abc": 123}, config["alice"])
        self.assertTrue(config.dirty)

    def test_replacing_configuration_option(self):
        config = ConfigurationFile(sentinel.filename, mutable=True)
        config["alice"] = {"abc": 123}
        config["alice"] = {"def": 456}
        self.assertEqual({"alice"}, set(config))
        self.assertEqual({"def": 456}, config["alice"])
        self.assertTrue(config.dirty)

    def test_getting_configuration_option(self):
        config = ConfigurationFile(sentinel.filename, mutable=True)
        config["alice"] = {"abc": 123}
        self.assertEqual({"abc": 123}, config["alice"])

    def test_getting_non_existent_configuration_option(self):
        config = ConfigurationFile(sentinel.filename)
        self.assertRaises(KeyError, lambda: config["alice"])

    def test_removing_configuration_option(self):
        config = ConfigurationFile(sentinel.filename, mutable=True)
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
        with open(config_file, "w"):
            pass  # Write nothing to the file.
        config = ConfigurationFile(config_file)
        config.load()
        self.assertEqual(set(config), set())

    def test_load_file_with_non_mapping_crashes(self):
        config_file = os.path.join(self.make_dir(), "config")
        with open(config_file, "w") as fd:
            yaml.safe_dump([1, 2, 3], stream=fd)
        config = ConfigurationFile(config_file)
        error = self.assertRaises(ValueError, config.load)
        self.assertEqual(
            f"Configuration in {config_file} is not a mapping: [1, 2, 3]",
            str(error),
        )

    def test_open_and_close(self):
        # ConfigurationFile.open() returns a context manager.
        config_file = os.path.join(self.make_dir(), "config")
        config_ctx = ConfigurationFile.open(config_file)
        self.assertIsInstance(config_ctx, contextlib._GeneratorContextManager)
        with config_ctx as config:
            self.assertIsInstance(config, ConfigurationFile)
            self.assertTrue(os.path.isfile(config_file))
            self.assertEqual({}, config.config)
            self.assertFalse(config.dirty)
        with open(config_file, "r") as fh:
            self.assertEqual(fh.read(), "")

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
        with ConfigurationFile.open_for_update(config_file):
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
        with ConfigurationFile.open_for_update(config_file) as config:
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
        with ConfigurationFile.open_for_update(config_file) as config:
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
        with ConfigurationFile.open_for_update(config_file) as config:
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
        with self.assertRaisesRegex(exception_type, "foo"):
            with ConfigurationFile.open_for_update(config_file) as config:
                config[config_key] = config_value
                raise exception_type("foo")
        # No value has been saved for `config_key`.
        with ConfigurationFile.open(config_file) as config:
            self.assertRaises(KeyError, lambda: config[config_key])

    def test_open_takes_exclusive_lock(self):
        config_file = os.path.join(self.make_dir(), "config")
        config_lock = RunLock(config_file)
        self.assertFalse(config_lock.is_locked())
        with ConfigurationFile.open_for_update(config_file):
            self.assertTrue(config_lock.is_locked())
        self.assertFalse(config_lock.is_locked())

    def test_as_string(self):
        config_file = os.path.join(self.make_dir(), "config")
        config = ConfigurationFile(config_file)
        self.assertEqual("ConfigurationFile(%r)" % config_file, str(config))


class TestConfigurationFileMutability(MAASTestCase):
    """Tests for `ConfigurationFile` mutability."""

    def test_immutable(self):
        config_file = os.path.join(self.make_dir(), "config")
        config = ConfigurationFile(config_file, mutable=False)
        self.assertRaises(ConfigurationImmutable, setitem, config, "alice", 1)
        self.assertRaises(ConfigurationImmutable, delitem, config, "alice")

    def test_mutable(self):
        config_file = os.path.join(self.make_dir(), "config")
        config = ConfigurationFile(config_file, mutable=True)
        config["alice"] = 1234
        del config["alice"]

    def test_open_yields_immutable_backend(self):
        config_file = os.path.join(self.make_dir(), "config")
        config_key = factory.make_name("key")
        with ConfigurationFile.open(config_file) as config:
            with self.assertRaisesRegex(ConfigurationImmutable, config_key):
                config[config_key] = factory.make_name("value")
            with self.assertRaisesRegex(ConfigurationImmutable, config_key):
                del config[config_key]

    def test_open_for_update_yields_mutable_backend(self):
        config_file = os.path.join(self.make_dir(), "config")
        config_key = factory.make_name("key")
        with ConfigurationFile.open_for_update(config_file) as config:
            config[config_key] = factory.make_name("value")
            del config[config_key]


class TestClusterConfiguration(MAASTestCase):
    """Tests for `ClusterConfiguration`."""

    def test_default_maas_url(self):
        config = ClusterConfiguration({})
        self.assertEqual(["http://localhost:5240/MAAS"], config.maas_url)

    def test_set_and_get_maas_url(self):
        config = ClusterConfiguration({})
        example_url = factory.make_simple_http_url()
        config.maas_url = example_url
        self.assertEqual([example_url], config.maas_url)
        # It's also stored in the configuration database.
        self.assertEqual({"maas_url": [example_url]}, config.store)

    def test_set_maas_url_accepts_hostnames(self):
        config = ClusterConfiguration({})
        example_url = factory.make_simple_http_url()
        config.maas_url = example_url
        self.assertEqual([example_url], config.maas_url)
        self.assertEqual({"maas_url": [example_url]}, config.store)

    def test_set_maas_url_accepts_very_short_hostnames(self):
        config = ClusterConfiguration({})
        example_url = factory.make_simple_http_url(
            netloc=factory.make_string(size=1)
        )
        config.maas_url = example_url
        self.assertEqual([example_url], config.maas_url)
        self.assertEqual({"maas_url": [example_url]}, config.store)

    def test_set_maas_url_rejects_bare_ipv6_addresses(self):
        config = ClusterConfiguration({})
        example_url = factory.make_simple_http_url(
            netloc=factory.make_ipv6_address()
        )
        with self.assertRaisesRegex(formencode.api.Invalid, "valid URL"):
            config.maas_url = example_url

    def test_set_maas_url_accepts_ipv6_addresses_with_brackets(self):
        config = ClusterConfiguration({})
        example_url = factory.make_simple_http_url(
            netloc="[%s]" % factory.make_ipv6_address()
        )
        config.maas_url = example_url
        self.assertEqual([example_url], config.maas_url)
        self.assertEqual({"maas_url": [example_url]}, config.store)

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
        self.assertTrue(config.tftp_root.endswith("tftp_root"))

    def test_set_and_get_tftp_root(self):
        config = ClusterConfiguration({})
        example_dir = self.make_dir()
        config.tftp_root = example_dir
        self.assertEqual(example_dir, config.tftp_root)
        # It's also stored in the configuration database.
        self.assertEqual({"tftp_root": example_dir}, config.store)

    def test_default_debug(self):
        config = ClusterConfiguration({})
        self.assertFalse(config.debug)

    def test_set_and_get_debug_false(self):
        config = ClusterConfiguration({})
        config.debug = False
        self.assertFalse(config.debug)

    def test_set_and_get_debug_false_str(self):
        config = ClusterConfiguration({})
        config.debug = "false"
        self.assertFalse(config.debug)

    def test_set_and_get_debug_true(self):
        config = ClusterConfiguration({})
        config.debug = True
        self.assertTrue(config.debug)

    def test_set_and_get_debug_true_str(self):
        config = ClusterConfiguration({})
        config.debug = "true"
        self.assertTrue(config.debug)


class TestClusterConfigurationGRUBRoot(MAASTestCase):
    """Tests for `ClusterConfiguration.grub_root`."""

    def test_is_relative_to_tftp_root_without_trailing_slash(self):
        random_dir = self.make_dir().rstrip("/")
        self.useFixture(ClusterConfigurationFixture(tftp_root=random_dir))
        with ClusterConfiguration.open() as configuration:
            self.assertEqual(random_dir + "/grub", configuration.grub_root)

    def test_is_relative_to_tftp_root_with_trailing_slash(self):
        random_dir = self.make_dir().rstrip("/") + "/"
        self.useFixture(ClusterConfigurationFixture(tftp_root=random_dir))
        with ClusterConfiguration.open() as configuration:
            self.assertEqual(random_dir + "grub", configuration.grub_root)


class TestConfig(MAASTestCase):
    """Tests for `maasserver.config`."""

    def test_is_dev_environment_returns_false(self):
        self.useFixture(ImportErrorFixture("maastesting", "dev_root"))
        self.assertFalse(is_dev_environment())

    def test_is_dev_environment_returns_true(self):
        self.assertTrue(is_dev_environment())


class TestDebugEnabled(MAASTestCase):
    """Tests for `debug_enabled`."""

    def setUp(self):
        super().setUp()
        # Make sure things aren't pulled from cache
        debug_enabled.cache_clear()

    def test_debug_enabled_false(self):
        # Verifies that the default state of debug is false.
        self.assertFalse(debug_enabled())

    def test_debug_enabled(self):
        debug = factory.pick_bool()
        self.useFixture(ClusterConfigurationFixture(debug=debug))
        self.assertEqual(debug, debug_enabled())

    def test_debug_enabled_cached(self):
        debug = factory.pick_bool()
        self.useFixture(ClusterConfigurationFixture(debug=debug))
        # Prime cache
        debug_enabled()
        mock_open = self.patch(config_module.ClusterConfiguration, "open")
        self.assertEqual(debug, debug_enabled())
        mock_open.assert_not_called()
