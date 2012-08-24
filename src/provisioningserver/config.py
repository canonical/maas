# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS Provisioning Configuration."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "Config",
    ]

from getpass import getuser
from os import environ
import os.path
from threading import RLock

from formencode import Schema
from formencode.declarative import DeclarativeMeta
from formencode.validators import (
    Int,
    RequireIfPresent,
    String,
    )
import yaml


class ConfigOops(Schema):
    """Configuration validator for OOPS options."""

    if_key_missing = None

    directory = String(if_missing=b"")
    reporter = String(if_missing=b"")

    chained_validators = (
        RequireIfPresent("reporter", present="directory"),
        )


class ConfigBroker(Schema):
    """Configuration validator for message broker options."""

    if_key_missing = None

    host = String(if_missing=b"localhost")
    port = Int(min=1, max=65535, if_missing=5673)
    username = String(if_missing=getuser())
    password = String(if_missing=b"test")
    vhost = String(if_missing="/")


class ConfigTFTP(Schema):
    """Configuration validator for the TFTP service."""

    if_key_missing = None

    root = String(if_missing="/var/lib/tftpboot")
    port = Int(min=1, max=65535, if_missing=69)
    generator = String(if_missing=b"http://localhost/MAAS/api/1.0/pxeconfig/")


class ConfigBootEphemeral(Schema):
    """Configuration validator for ephemeral boot configuration."""

    if_key_missing = None

    directory = String(if_missing="/var/lib/maas/ephemeral")


class ConfigBoot(Schema):
    """Configuration validator for boot configuration."""

    if_key_missing = None

    ephemeral = ConfigBootEphemeral


class ConfigMeta(DeclarativeMeta):
    """Metaclass for the root configuration schema."""

    def _get_default_filename(cls):
        # Get the configuration filename from the environment. Failing that,
        # look for the configuration in its default locations.
        configured_location = environ.get("MAAS_PROVISIONING_SETTINGS")
        if configured_location is not None:
            return configured_location
        for filename in ['etc/pserv.yaml', '/etc/maas/pserv.yaml']:
            if os.path.isfile(filename):
                return filename
        # Oh well.  Just return the last filename we tried, and let the
        # caller report that that file was not found.
        return filename

    def _set_default_filename(cls, filename):
        # Set the configuration filename in the environment.
        environ["MAAS_PROVISIONING_SETTINGS"] = filename

    def _delete_default_filename(cls):
        # Remove any setting of the configuration filename from the
        # environment.
        environ.pop("MAAS_PROVISIONING_SETTINGS", None)

    DEFAULT_FILENAME = property(
        _get_default_filename, _set_default_filename,
        _delete_default_filename, doc=(
            "The default config file to load. Refers to "
            "MAAS_PROVISIONING_SETTINGS in the environment."))


class Config(Schema):
    """Configuration validator."""

    __metaclass__ = ConfigMeta

    if_key_missing = None

    logfile = String(if_empty=b"pserv.log", if_missing=b"pserv.log")
    oops = ConfigOops
    broker = ConfigBroker
    tftp = ConfigTFTP
    boot = ConfigBoot

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

    _cache = {}
    _cache_lock = RLock()

    @classmethod
    def load_from_cache(cls, filename=None):
        """Load or return a previously loaded configuration.

        This is thread-safe, so is okay to use from Django, for example.
        """
        if filename is None:
            filename = cls.DEFAULT_FILENAME
        filename = os.path.abspath(filename)
        with cls._cache_lock:
            if filename not in cls._cache:
                with open(filename, "rb") as stream:
                    cls._cache[filename] = cls.parse(stream)
            return cls._cache[filename]

    @classmethod
    def field(target, *steps):
        """Obtain a field by following `steps`."""
        for step in steps:
            target = target.fields[step]
        return target
