# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS web."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "import_settings",
    "import_local_settings",
    ]

import sys


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
