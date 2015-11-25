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
    "import_settings",
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
                        % (atomic_requests,), RuntimeWarning, 2)
            database["ATOMIC_REQUESTS"] = True


try:
    import maasfascist
    maasfascist  # Silence lint.
except ImportError:
    pass
