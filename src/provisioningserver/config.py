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
from os import (
    environ,
    urandom,
    )
from os.path import abspath
from threading import RLock

from formencode import Schema
from formencode.declarative import DeclarativeMeta
from formencode.validators import (
    Int,
    RequireIfPresent,
    String,
    URL,
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


class ConfigCobbler(Schema):
    """Configuration validator for connecting to Cobbler."""

    if_key_missing = None

    url = URL(
        add_http=True, require_tld=False,
        if_missing=b"http://localhost/cobbler_api",
        )
    username = String(if_missing=getuser())
    password = String(if_missing=b"test")


class ConfigTFTP(Schema):
    """Configuration validator for the TFTP service."""

    if_key_missing = None

    root = String(if_missing="/var/lib/tftpboot")
    port = Int(min=1, max=65535, if_missing=5244)
    generator = URL(
        add_http=True, require_tld=False,
        if_missing=b"http://localhost:5243/api/1.0/pxeconfig",
        )


class ConfigMeta(DeclarativeMeta):
    """Metaclass for the root configuration schema."""

    def _get_default_filename(cls):
        # Get the configuration filename from the environment. Failing that,
        # return a hard-coded default.
        return environ.get(
            "MAAS_PROVISIONING_SETTINGS",
            "/etc/maas/pserv.yaml")

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

    interface = String(if_empty=b"", if_missing=b"127.0.0.1")
    port = Int(min=1, max=65535, if_missing=5241)
    username = String(not_empty=True, if_missing=getuser())
    password = String(not_empty=True, if_missing=urandom(12))
    logfile = String(if_empty=b"pserv.log", if_missing=b"pserv.log")
    oops = ConfigOops
    broker = ConfigBroker
    cobbler = ConfigCobbler
    tftp = ConfigTFTP

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
        filename = abspath(filename)
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
