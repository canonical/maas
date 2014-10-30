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
    "import_settings",
    "import_local_settings",
    "log_sstreams",
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
