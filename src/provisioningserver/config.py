# Copyright 2012-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration for the MAAS cluster.

This module also contains the common library code that's used for
configuration in both the region and the cluster.

There are two styles of configuration object, one older and deprecated, and
one new.


The Old Way
-----------

Configuration can be obtained through subclassing this module's `ConfigBase`
validator class. It's pretty simple. Typical usage is::

  >>> config = MyConfig.load_from_cache()
  {...}

This reads in a configuration file from `MyConfig.DEFAULT_FILENAME` (see a note
about that later). The configuration file is parsed as YAML, and a plain `dict`
is returned with configuration nested within it. The configuration is validated
at load time using `formencode`. The policy for validation is laid out in this
module; see the various `formencode.Schema` subclasses.

Configuration should be optional, and a sensible default should be provided in
every instance. The defaults can be obtained from `MyConfig.get_defaults()`.

An alternative to `MyConfig.load_from_cache()` is `MyConfig.load()`, which
loads and validates a configuration file while bypassing the cache. See
`ConfigBase` for other useful functions.

`MyConfig.DEFAULT_FILENAME` is a class property, so does not need to be
referenced via an instance of `MyConfig`. It refers to an environment variable
named by `MyConfig.envvar` in the first instance, but should have a sensible
default too. You can write to this property and it will update the environment
so that child processes will also use the same configuration filename. To
revert to the default - i.e. erase the environment variable - you can `del
MyConfig.DEFAULT_FILENAME`.

When testing, see `provisioningserver.testing.config.ConfigFixtureBase` to
temporarily use a different configuration.


The New Way
-----------

There are two subclasses of this module's `Configuration` class, one for the
region (`RegionConfiguration`) and for the cluster (`ClusterConfiguration`).
Each defines a set of attributes which are the configuration variables:

* If an attribute is declared as a `ConfigurationOption` then it's a
  read-write configuration option, and should have a sensible default if
  possible.

* If an attribute is declared as a standard Python `property` then it's a
  read-only configuration option.

A metaclass is also defined, which must inherit from `ConfigurationMeta`, to
define a few other important options:

* ``default`` is the default filename for the configuration database.

* ``envvar`` is the name of an environment variable that, if defined, provides
  the filename for the configuration database. This is used in preference to
  ``default``.

* ``backend`` is a factory that provides the storage mechanism. Currently you
  can choose from `ConfigurationFile` or `ConfigurationDatabase`. The latter
  is strongly recommended in preference to the former.

An example::

  class MyConfiguration(Configuration):

      class __metaclass__(ConfigurationMeta):
          envvar = "CONFIG_FILE"
          default = "/etc/myapp.conf"
          backend = ConfigurationDatabase

      images_dir = ConfigurationOption(
          "images_dir", "The directory in which to store images.",
          DirectoryString(if_missing="/var/lib/myapp/images"))

      @property
      def png_dir(self):
          "The directory in which to store PNGs."
          return os.path.join(self.images_dir, "png")

      @property
      def gif_dir(self):
          "The directory in which to store GIFs."
          return os.path.join(self.images_dir, "gif")

It can be used like so::

  with MyConfiguration.open() as config:
      config.images_dir = "/var/www/example.com/images"
      print(config.png_dir, config.gif_dir)

"""

from contextlib import closing, contextmanager
from copy import deepcopy
from functools import lru_cache
from itertools import islice
import json
import logging
import os
from os import environ
import os.path
from shutil import copyfile, disk_usage
import sqlite3
from threading import RLock
from time import time
import traceback

from formencode import ForEach, Schema
from formencode.api import is_validator, NoDefault
from formencode.declarative import DeclarativeMeta
from formencode.validators import Number, Set
import yaml

from provisioningserver.path import get_maas_data_path, get_tentative_data_path
from provisioningserver.utils.config import (
    DirectoryString,
    ExtendedURL,
    OneWayStringBool,
    UnicodeString,
)
from provisioningserver.utils.fs import atomic_write, get_root_path, RunLock

logger = logging.getLogger(__name__)

# Default result for cluster UUID if not set
UUID_NOT_SET = None

# Default images URL can be overridden by the environment.
DEFAULT_IMAGES_URL = os.getenv(
    "MAAS_DEFAULT_IMAGES_URL", "http://images.maas.io/ephemeral-v3/stable/"
)

# Default images keyring filepath can be overridden by the environment.
DEFAULT_KEYRINGS_PATH = os.getenv(
    "MAAS_IMAGES_KEYRING_FILEPATH",
    "/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg",
)


class BootSourceSelection(Schema):
    """Configuration validator for boot source selection configuration."""

    if_key_missing = None

    os = UnicodeString(if_missing="*")
    release = UnicodeString(if_missing="*")
    arches = Set(if_missing=["*"])
    subarches = Set(if_missing=["*"])
    labels = Set(if_missing=["*"])


class BootSource(Schema):
    """Configuration validator for boot source configuration."""

    if_key_missing = None

    url = UnicodeString(if_missing=DEFAULT_IMAGES_URL)
    keyring = UnicodeString(if_missing=DEFAULT_KEYRINGS_PATH)
    keyring_data = UnicodeString(if_missing="")
    selections = ForEach(
        BootSourceSelection, if_missing=[BootSourceSelection.to_python({})]
    )


class ConfigBase:
    """Base configuration validator."""

    @classmethod
    def parse(cls, stream):
        """Load a YAML configuration from `stream` and validate."""
        return cls.to_python(yaml.safe_load(stream))

    @classmethod
    def load(cls, filename=None):
        """Load a YAML configuration from `filename` and validate."""
        if filename is None:
            filename = cls.DEFAULT_FILENAME
        with open(filename, "rb") as stream:
            return cls.parse(stream)

    @classmethod
    def _get_backup_name(cls, message, filename=None):
        if filename is None:
            filename = cls.DEFAULT_FILENAME
        return f"{filename}.{message}.bak"

    @classmethod
    def create_backup(cls, message, filename=None):
        """Create a backup of the YAML configuration.

        The given 'message' will be used in the name of the backup file.
        """
        backup_name = cls._get_backup_name(message, filename)
        if filename is None:
            filename = cls.DEFAULT_FILENAME
        copyfile(filename, backup_name)

    @classmethod
    def save(cls, config, filename=None):
        """Save a YAML configuration to `filename`, or to the default file."""
        if filename is None:
            filename = cls.DEFAULT_FILENAME
        dump = yaml.safe_dump(config, encoding="utf-8")
        atomic_write(dump, filename)

    _cache = {}
    _cache_lock = RLock()

    @classmethod
    def load_from_cache(cls, filename=None):
        """Load or return a previously loaded configuration.

        Keeps an internal cache of config files.  If the requested config file
        is not in cache, it is loaded and inserted into the cache first.

        Each call returns a distinct (deep) copy of the requested config from
        the cache, so the caller can modify its own copy without affecting what
        other call sites see.

        This is thread-safe, so is okay to use from Django, for example.
        """
        if filename is None:
            filename = cls.DEFAULT_FILENAME
        filename = os.path.abspath(filename)
        with cls._cache_lock:
            if filename not in cls._cache:
                with open(filename, "rb") as stream:
                    cls._cache[filename] = cls.parse(stream)
            return deepcopy(cls._cache[filename])

    @classmethod
    def flush_cache(cls, filename=None):
        """Evict a config file, or any cached config files, from cache."""
        with cls._cache_lock:
            if filename is None:
                cls._cache.clear()
            else:
                if filename in cls._cache:
                    del cls._cache[filename]

    @classmethod
    def field(target, *steps):
        """Obtain a field by following `steps`."""
        for step in steps:
            target = target.fields[step]
        return target

    @classmethod
    def get_defaults(cls):
        """Return the default configuration."""
        return cls.to_python({})


class ConfigMeta(DeclarativeMeta):
    """Metaclass for the root configuration schema."""

    envvar = None  # Set this in subtypes.
    default = None  # Set this in subtypes.

    def _get_default_filename(cls):
        # Avoid circular imports.
        from provisioningserver.utils import locate_config

        # Get the configuration filename from the environment. Failing that,
        # look for the configuration in its default locations.
        return environ.get(cls.envvar, locate_config(cls.default))

    def _set_default_filename(cls, filename):
        # Set the configuration filename in the environment.
        environ[cls.envvar] = filename

    def _delete_default_filename(cls):
        # Remove any setting of the configuration filename from the
        # environment.
        environ.pop(cls.envvar, None)

    DEFAULT_FILENAME = property(
        _get_default_filename,
        _set_default_filename,
        _delete_default_filename,
        doc=(
            "The default config file to load. Refers to "
            "`cls.envvar` in the environment."
        ),
    )


class BootSourcesMeta(ConfigMeta):
    """Meta-configuration for boot sources."""

    envvar = "MAAS_BOOT_SOURCES_SETTINGS"
    default = "sources.yaml"


class BootSources(ConfigBase, ForEach, metaclass=BootSourcesMeta):
    """Configuration for boot sources."""

    validators = [BootSource]


###############################################################################
# New configuration API follows.
###############################################################################


# Permit reads by members of the same group.
default_file_mode = 0o640


def touch(path, mode=default_file_mode):
    """Ensure that `path` exists."""
    os.close(os.open(path, os.O_CREAT | os.O_APPEND, mode))


class ConfigurationImmutable(Exception):
    """The configuration is read-only; it cannot be mutated."""


class ConfigurationDatabase:
    """Store configuration in an sqlite3 database."""

    def __init__(self, database, *, mutable=False):
        self.database = database
        self.mutable = mutable
        with self.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS configuration "
                "(id INTEGER PRIMARY KEY,"
                " name TEXT NOT NULL UNIQUE,"
                " data BLOB)"
            )

    def cursor(self):
        return closing(self.database.cursor())

    def __iter__(self):
        with self.cursor() as cursor:
            results = cursor.execute(
                "SELECT name FROM configuration"
            ).fetchall()
        return (name for (name,) in results)

    def __getitem__(self, name):
        with self.cursor() as cursor:
            data = cursor.execute(
                "SELECT data FROM configuration WHERE name = ?", (name,)
            ).fetchone()
        if data is None:
            raise KeyError(name)
        else:
            return json.loads(data[0])

    def __setitem__(self, name, data):
        if self.mutable:
            with self.cursor() as cursor:
                cursor.execute(
                    "INSERT OR REPLACE INTO configuration (name, data) "
                    "VALUES (?, ?)",
                    (name, json.dumps(data)),
                )
        else:
            raise ConfigurationImmutable(f"{self}: Cannot set `{name}'.")

    def __delitem__(self, name):
        if self.mutable:
            with self.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM configuration WHERE name = ?", (name,)
                )
        else:
            raise ConfigurationImmutable(f"{self}: Cannot set `{name}'.")

    def __str__(self):
        with self.cursor() as cursor:
            # https://www.sqlite.org/pragma.html#pragma_database_list
            databases = "; ".join(
                "{}={}".format(name, ":memory:" if path == "" else path)
                for (_, name, path) in cursor.execute("PRAGMA database_list")
            )
        return f"{self.__class__.__qualname__}({databases})"

    @classmethod
    @contextmanager
    def open(cls, dbpath: str):
        """Open a configuration database.

        **Note** that this returns a context manager which will open the
        database READ-ONLY.
        """
        # Ensure `dbpath` exists...
        touch(dbpath)
        # before opening it with sqlite.
        database = sqlite3.connect(dbpath)
        try:
            yield cls(database, mutable=False)
        except Exception:
            raise
        else:
            database.rollback()
        finally:
            database.close()

    @classmethod
    @contextmanager
    def open_for_update(cls, dbpath: str):
        """Open a configuration database.

        **Note** that this returns a context manager which will close the
        database on exit, COMMITTING changes if the exit is clean.
        """
        # Ensure `dbpath` exists...
        touch(dbpath)
        # before opening it with sqlite.
        database = sqlite3.connect(dbpath)
        try:
            yield cls(database, mutable=True)
        except Exception:
            raise
        else:
            database.commit()
        finally:
            database.close()


class ConfigurationFile:
    """Store configuration as YAML in a file.

    You should almost always prefer the `ConfigurationDatabase` variant above
    this. It provides things like transactions with optimistic write locking,
    synchronisation between processes, and all the goodies that come with a
    mature and battle-tested piece of kit such as SQLite3.

    This, by comparison, will clobber changes made in another thread or
    process without warning. We could add support for locking, even optimistic
    locking, but, you know, that's already been done: `ConfigurationDatabase`
    preceded this. Just use that. Really. Unless, you know, you've absolutely
    got to use this.
    """

    def __init__(self, path, *, mutable=False):
        super().__init__()
        self.config = {}
        self.dirty = False
        self.path = path
        self.mutable = mutable

    def __iter__(self):
        return iter(self.config)

    def __getitem__(self, name):
        return self.config[name]

    def __setitem__(self, name, data):
        if self.mutable:
            self.config[name] = data
            self.dirty = True
        else:
            raise ConfigurationImmutable(f"{self}: Cannot set `{name}'.")

    def __delitem__(self, name):
        if self.mutable:
            if name in self.config:
                del self.config[name]
                self.dirty = True
        else:
            raise ConfigurationImmutable(f"{self}: Cannot set `{name}'.")

    def load(self):
        """Load the configuration."""
        with open(self.path, "rb") as fd:
            config = yaml.safe_load(fd)
        if config is None:
            self.config.clear()
            self.dirty = False
        elif isinstance(config, dict):
            self.config = config
            self.dirty = False
        else:
            raise ValueError(
                "Configuration in %s is not a mapping: %r"
                % (self.path, config)
            )

    def save(self):
        """Save the configuration."""
        try:
            stat = os.stat(self.path)
        except OSError:
            mode = default_file_mode
        else:
            mode = stat.st_mode
        # Write, retaining the file's mode.
        atomic_write(
            yaml.safe_dump(
                self.config, default_flow_style=False, encoding="utf-8"
            ),
            self.path,
            mode=mode,
        )
        self.dirty = False

    def __str__(self):
        return f"{self.__class__.__qualname__}({self.path!r})"

    @classmethod
    @contextmanager
    def open(cls, path: str):
        """Open a configuration file read-only.

        This avoids all the locking that happens in `open_for_update`. However,
        it will create the configuration file if it does not yet exist.

        **Note** that this returns a context manager which will DISCARD
        changes to the configuration on exit.
        """
        # Ensure `path` exists...
        touch(path)
        # before loading it in.
        configfile = cls(path, mutable=False)
        configfile.load()
        yield configfile

    @classmethod
    @contextmanager
    def open_for_update(cls, path: str):
        """Open a configuration file.

        Locks are taken so that there can only be *one* reader or writer for a
        configuration file at a time. Where configuration files can be read by
        multiple concurrent processes it follows that each process should hold
        the file open for the shortest time possible.

        **Note** that this returns a context manager which will SAVE changes
        to the configuration on a clean exit.
        """
        time_opened = None
        try:
            # Only one reader or writer at a time.
            with RunLock(path).wait(timeout=5.0):
                time_opened = time()
                # Ensure `path` exists...
                touch(path)
                # before loading it in.
                configfile = cls(path, mutable=True)
                configfile.load()
                try:
                    yield configfile
                except Exception:
                    raise
                else:
                    if configfile.dirty:
                        configfile.save()
        finally:
            if time_opened is not None:
                time_open = time() - time_opened
                if time_open >= 2.5:
                    mini_stack = ", from ".join(
                        "%s:%d" % (fn, lineno)
                        for fn, lineno, _, _ in islice(
                            reversed(traceback.extract_stack()), 2, 5
                        )
                    )
                    logger.warning(
                        "Configuration file %s locked for %.1f seconds; this "
                        "may starve other processes. Called from %s.",
                        path,
                        time_open,
                        mini_stack,
                    )


class ConfigurationMeta(type):
    """Metaclass for configuration objects.

    :cvar envvar: The name of the environment variable which will be used to
        store the filename of the configuration file. This can be passed in
        from the caller's environment. Setting `DEFAULT_FILENAME` updates this
        environment variable so that it's available to sub-processes.
    :cvar default: If the environment variable named by `envvar` is not set,
        this is used as the filename.
    :cvar backend: The class used to load the configuration. This must provide
        an ``open(filename)`` method that returns a context manager. This
        context manager must provide an object with a dict-like interface.
    """

    envvar = None  # Set this in subtypes.
    default = None  # Set this in subtypes.
    backend = None  # Set this in subtypes.

    def _get_default_filename(cls):
        # Get the configuration filename from the environment. Failing that,
        # look for the configuration in its default locations.
        filename = environ.get(cls.envvar)
        if filename is None or len(filename) == 0:
            return get_tentative_data_path(cls.default)
        else:
            return filename

    def _set_default_filename(cls, filename):
        # Set the configuration filename in the environment.
        environ[cls.envvar] = filename

    def _delete_default_filename(cls):
        # Remove any setting of the configuration filename from the
        # environment.
        environ.pop(cls.envvar, None)

    DEFAULT_FILENAME = property(
        _get_default_filename,
        _set_default_filename,
        _delete_default_filename,
        doc=(
            "The default configuration file to load. Refers to "
            "`cls.envvar` in the environment."
        ),
    )


class Configuration:
    """An object that holds configuration options.

    Configuration options should be defined by creating properties using
    `ConfigurationOption`. For example::

        class ApplicationConfiguration(Configuration):

            application_name = ConfigurationOption(
                "application_name", "The name for this app, used in the UI.",
                validator=UnicodeString())

    This can then be used like so::

        config = ApplicationConfiguration(database)  # database is dict-like.
        config.application_name = "Metal On A Plate"
        print(config.application_name)

    """

    # Define this class variable in sub-classes. Using `ConfigurationMeta` as
    # a metaclass is a good way to achieve this.
    DEFAULT_FILENAME = None

    def __init__(self, store):
        """Initialise a new `Configuration` object.

        :param store: A dict-like object.
        """
        super().__init__()
        # Use the super-class's __setattr__() because it's redefined later on
        # to prevent accidentally setting attributes that are not options.
        super().__setattr__("store", store)

    def __setattr__(self, name, value):
        """Prevent setting unrecognised options.

        Only options that have been declared on the class, using the
        `ConfigurationOption` descriptor for example, can be set.

        This is as much about preventing typos as anything else.
        """
        if hasattr(self.__class__, name):
            super().__setattr__(name, value)
        else:
            raise AttributeError(
                "%r object has no attribute %r"
                % (self.__class__.__name__, name)
            )

    @classmethod
    @contextmanager
    def open(cls, filepath=None):
        if filepath is None:
            filepath = cls.DEFAULT_FILENAME
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with cls.backend.open(filepath) as store:
            yield cls(store)

    @classmethod
    @contextmanager
    def open_for_update(cls, filepath=None):
        if filepath is None:
            filepath = cls.DEFAULT_FILENAME
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with cls.backend.open_for_update(filepath) as store:
            yield cls(store)


class ConfigurationOption:
    """Define a configuration option.

    This is for use with `Configuration` and its subclasses.
    """

    def __init__(self, name, doc, validator):
        """Initialise a new `ConfigurationOption`.

        :param name: The name for this option. This is the name as which this
            option will be stored in the underlying `Configuration` object.
        :param doc: A description of the option. This is mandatory.
        :param validator: A `formencode.validators.Validator`.
        """
        super().__init__()

        assert isinstance(name, str)
        assert isinstance(doc, str)
        assert is_validator(validator)
        assert validator.if_missing is not NoDefault

        self.name = name
        self.__doc__ = doc
        self.validator = validator

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        else:
            try:
                value = obj.store[self.name]
            except KeyError:
                return self.validator.if_missing
            else:
                return self.validator.from_python(value)

    def __set__(self, obj, value):
        obj.store[self.name] = self.validator.to_python(value)

    def __delete__(self, obj):
        del obj.store[self.name]


class ClusterConfigurationMeta(ConfigurationMeta):
    """Local meta-configuration for the MAAS cluster."""

    envvar = "MAAS_CLUSTER_CONFIG"
    default = "/etc/maas/rackd.conf"
    backend = ConfigurationFile


class ClusterConfiguration(Configuration, metaclass=ClusterConfigurationMeta):
    """Local configuration for the MAAS cluster."""

    maas_url = ConfigurationOption(
        "maas_url",
        "The HTTP URL(s) for the MAAS region.",
        ForEach(
            ExtendedURL(require_tld=False),
            convert_to_list=True,
            if_missing=["http://localhost:5240/MAAS"],
        ),
    )

    # RPC Connection Pool options
    max_idle_rpc_connections = ConfigurationOption(
        "max_idle_rpc_connections",
        "The nominal number of connections to have per endpoint",
        Number(min=1, max=1024, if_missing=1),
    )
    max_rpc_connections = ConfigurationOption(
        "max_rpc_connections",
        "The maximum number of connections to scale to when under load",
        Number(min=1, max=1024, if_missing=4),
    )
    rpc_keepalive = ConfigurationOption(
        "rpc_keepalive",
        "The duration in miliseconds to keep added connections alive",
        Number(min=1, max=5000, if_missing=1000),
    )

    # TFTP options.
    tftp_port = ConfigurationOption(
        "tftp_port",
        "The UDP port on which to listen for TFTP requests.",
        Number(min=0, max=(2**16) - 1, if_missing=69),
    )
    tftp_root = ConfigurationOption(
        "tftp_root",
        "The root directory for TFTP resources.",
        DirectoryString(
            # Don't validate values that are already stored.
            accept_python=True,
            if_missing=get_maas_data_path("tftp_root"),
        ),
    )

    # GRUB options.

    @property
    def grub_root(self):
        "The root directory for GRUB resources."
        return os.path.join(self.tftp_root, "grub")

    # Debug options.
    debug = ConfigurationOption(
        "debug",
        "Enable debug mode for detailed error and log reporting.",
        OneWayStringBool(if_missing=False),
    )

    # MAAS Agent options
    httpproxy_cache_size = ConfigurationOption(
        "httpproxy_cache_size",
        "The size of a cache used by HTTP proxy",
        Number(min=1, if_missing=disk_usage(get_root_path()).total * 0.3),
    )


def is_dev_environment():
    """Is this the development environment, or production?"""
    try:
        from maastesting import dev_root  # noqa
    except Exception:
        return False
    else:
        return True


@lru_cache(maxsize=1)
def debug_enabled():
    """Return and cache whether debug has been enabled."""
    with ClusterConfiguration.open() as config:
        return config.debug
