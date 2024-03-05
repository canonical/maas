# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS web."""


import sys
import warnings


def find_settings(whence):
    """Return settings from `whence`, which is assumed to be a module."""
    return {
        name: value
        for name, value in vars(whence).items()
        if not name.startswith("_")
    }


def import_settings(whence):
    """Import settings from `whence` into the caller's global scope."""
    source = find_settings(whence)
    target = sys._getframe(1).f_globals
    target.update(source)


def fix_up_databases(databases):
    """Increase isolation level, use atomic requests.

    Does not modify connections to non-PostgreSQL databases.
    """
    # Remove keys with null values from databases.
    databases.update(
        {
            alias: {
                key: value
                for key, value in database.items()
                if value is not None
            }
            for alias, database in databases.items()
        }
    )
    # Ensure that transactions are configured correctly.
    from psycopg2.extensions import ISOLATION_LEVEL_REPEATABLE_READ

    for _, database in databases.items():
        engine = database.get("ENGINE")
        if engine == "django.db.backends.postgresql":
            options = database.setdefault("OPTIONS", {})
            # Explicitly set the transaction isolation level. MAAS needs a
            # particular transaction isolation level, and it enforces it.
            if "isolation_level" in options:
                isolation_level = options["isolation_level"]
                if isolation_level != ISOLATION_LEVEL_REPEATABLE_READ:
                    warnings.warn(
                        "isolation_level is set to %r; overriding to %r."
                        % (isolation_level, ISOLATION_LEVEL_REPEATABLE_READ),
                        RuntimeWarning,
                        2,
                    )
            options["isolation_level"] = ISOLATION_LEVEL_REPEATABLE_READ
            # Enable ATOMIC_REQUESTS: MAAS manages transactions across the
            # whole request/response lifecycle including middleware (Django,
            # in its infinite wisdom, does not). However we enable this
            # setting to ensure that views run within _savepoints_ so that
            # middleware exception handlers that suppress exceptions don't
            # inadvertently allow failed requests to be committed.
            if "ATOMIC_REQUESTS" in database:
                atomic_requests = database["ATOMIC_REQUESTS"]
                if not atomic_requests:
                    warnings.warn(
                        "ATOMIC_REQUESTS is set to %r; overriding to True."
                        % (atomic_requests,),
                        RuntimeWarning,
                        2,
                    )
            database["ATOMIC_REQUESTS"] = True
