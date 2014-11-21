# Copyright 2012 Canonical Ltd.  This software is licensed under the
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
    "log_sstreams",
    ]

import sys
import warnings


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
    from psycopg2.extensions import ISOLATION_LEVEL_SERIALIZABLE
    for _, database in databases.viewitems():
        engine = database.get("ENGINE")
        if engine == 'django.db.backends.postgresql_psycopg2':
            options = database.setdefault("OPTIONS", {})
            # Explicitly set the transaction isolation level. MAAS needs a
            # particular transaction isolation level, and it enforces it.
            if "isolation_level" in options:
                isolation_level = options["isolation_level"]
                if isolation_level != ISOLATION_LEVEL_SERIALIZABLE:
                    warnings.warn(
                        "isolation_level is set to %r; overriding to %r."
                        % (isolation_level, ISOLATION_LEVEL_SERIALIZABLE),
                        RuntimeWarning, 2)
            options["isolation_level"] = ISOLATION_LEVEL_SERIALIZABLE
            # Disable ATOMIC_REQUESTS: MAAS manually manages this so it can
            # retry transactions that fail with serialisation errors.
            if "ATOMIC_REQUESTS" in database:
                atomic_requests = database["ATOMIC_REQUESTS"]
                if atomic_requests:
                    warnings.warn(
                        "ATOMIC_REQUESTS is set to %r; overriding to False."
                        % (atomic_requests,), RuntimeWarning, 2)
            database["ATOMIC_REQUESTS"] = False


def log_sstreams(LOGGING):
    """Turn on simplestreams logging.

    Copies the exact logging configuration for maasserver into sstreams,
    unless a sstreams config already exists.
    """
    if 'loggers' not in LOGGING:
        # No loggers in LOGGING, can't do anthing.
        return
    if 'sstreams' in LOGGING['loggers']:
        # Already have a simplestreams config for logging.
        return
    if 'maasserver' not in LOGGING['loggers']:
        # No maasserver logger present to copy, no way of know what it
        # should be set to.
        return
    LOGGING['loggers']['sstreams'] = LOGGING['loggers']['maasserver']


try:
    import maasfascist
    maasfascist  # Silence lint.
except ImportError:
    pass
