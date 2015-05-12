# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS web."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "fix_up_databases",
    "import_local_settings",
    "import_settings",
    "import_local_settings",
    ]

import sys
import warnings

import django.conf


def find_settings(whence):
    """Return settings from `whence`, which is assumed to be a module."""
    # XXX 2012-10-11 JeroenVermeulen, bug=1065456: We thought this would be
    # a good shared location for this helper, but we can't get at it during
    # cluster installation.  So it's currently duplicated.  Put it in a
    # properly shared location.
    return {
        name: value
        for name, value in vars(whence).items()
        if not name.startswith("_")
        }


def import_settings(whence):
    """Import settings from `whence` into the caller's global scope."""
    # XXX 2012-10-11 JeroenVermeulen, bug=1065456: We thought this would be
    # a good shared location for this helper, but we can't get at it during
    # cluster installation.  So it's currently duplicated.  Put it in a
    # properly shared location.
    source = find_settings(whence)
    target = sys._getframe(1).f_globals
    target.update(source)


def import_local_settings():
    """Import local settings into the caller's global scope.

    Local settings means settings defined in a `maas_local_settings` module.
    """
    try:
        import maas_local_settings as whence
    except ImportError:
        pass
    else:
        source = find_settings(whence)
        target = sys._getframe(1).f_globals
        target.update(source)


def fix_up_databases(databases):
    """Increase isolation level, use atomic requests.

    Does not modify connections to non-PostgreSQL databases.
    """
    from psycopg2.extensions import ISOLATION_LEVEL_REPEATABLE_READ
    for _, database in databases.viewitems():
        engine = database.get("ENGINE")
        if engine == 'django.db.backends.postgresql_psycopg2':
            options = database.setdefault("OPTIONS", {})
            # Explicitly set the transaction isolation level. MAAS needs a
            # particular transaction isolation level, and it enforces it.
            if "isolation_level" in options:
                isolation_level = options["isolation_level"]
                if isolation_level != ISOLATION_LEVEL_REPEATABLE_READ:
                    warnings.warn(
                        "isolation_level is set to %r; overriding to %r."
                        % (isolation_level, ISOLATION_LEVEL_REPEATABLE_READ),
                        RuntimeWarning, 2)
            options["isolation_level"] = ISOLATION_LEVEL_REPEATABLE_READ
            # Disable ATOMIC_REQUESTS: MAAS manually manages this so it can
            # retry transactions that fail with serialisation errors.
            if "ATOMIC_REQUESTS" in database:
                atomic_requests = database["ATOMIC_REQUESTS"]
                if atomic_requests:
                    warnings.warn(
                        "ATOMIC_REQUESTS is set to %r; overriding to False."
                        % (atomic_requests,), RuntimeWarning, 2)
            database["ATOMIC_REQUESTS"] = False


class LazySettings(django.conf.LazySettings):
    """Prevent Django from mangling warnings settings.

    At present, Django adds a single filter that surfaces all deprecation
    warnings, but MAAS handles them differently. Django doesn't appear to give
    a way to prevent it from doing its thing, so we must undo its changes.

    Deprecation warnings in production environments are not desirable as they
    are a developer tool, and not something an end user can reasonably do
    something about. This brings control of warnings back into MAAS's control.
    """

    def _configure_logging(self):
        # This is a copy of *half* of Django's `_configure_logging`, omitting
        # the problematic bits.
        if self.LOGGING_CONFIG:
            from django.utils.log import DEFAULT_LOGGING
            from django.utils.module_loading import import_by_path
            # First find the logging configuration function ...
            logging_config_func = import_by_path(self.LOGGING_CONFIG)
            logging_config_func(DEFAULT_LOGGING)
            # ... then invoke it with the logging settings
            if self.LOGGING:
                logging_config_func(self.LOGGING)


# Install our `LazySettings` as the Django-global settings class. First,
# ensure that Django hasn't yet loaded its settings.
assert not django.conf.settings.configured
# This is needed because Django's `LazySettings` overrides `__setattr__`.
object.__setattr__(django.conf.settings, "__class__", LazySettings)


try:
    import maasfascist
    maasfascist  # Silence lint.
except ImportError:
    pass
