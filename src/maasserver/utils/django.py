# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django related utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'has_builtin_migrations',
    ]

import django


def has_builtin_migrations():
    """Return True if django supports builtin migrations."""
    return django.VERSION >= (1, 7)
