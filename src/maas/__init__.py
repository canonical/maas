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
    ]

import sys


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
            # Increase the transaction isolation level.
            options["isolation_level"] = ISOLATION_LEVEL_SERIALIZABLE
            # Wrap each HTTP request in a transaction.
            database["ATOMIC_REQUESTS"] = True


try:
    import maasfascist
    maasfascist  # Silence lint.
except ImportError:
    pass
