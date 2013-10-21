# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for testing South database migrations.

Each Django application in MAAS tests the basic sanity of its own South
database migrations.  To minimize repetition, this single module provides all
the code those tests need.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'detect_sequence_clashes',
    ]

from collections import Counter
import re

from south.migration.base import Migrations
from south.utils import ask_for_it_by_name


def extract_number(migration_name):
    """Extract the sequence number from a migration module name."""
    return int(re.match('([0-9]+)_', migration_name).group(1))


def get_duplicates(numbers):
    """Return set of those items that occur more than once."""
    return {
        numbers
        for numbers, count in Counter(numbers).items()
        if count > 1
    }


def list_migrations(app_name):
    """List schema migrations in the given app."""
    app = ask_for_it_by_name(app_name)
    return [migration.name() for migration in Migrations(app)]


def detect_sequence_clashes(app_name):
    """List numbering clashes among database migrations in given app.

    :param app_name: Name of a MAAS Django application, e.g. "metadataserver"
    :return: A sorted `list` of tuples `(number, name)` representing all
        migration modules in the app that have clashing sequence numbers.
        The `number` is as found in `name`, but in `int` form.
    """
    migrations = list_migrations(app_name)
    numbers_and_names = [(extract_number(name), name) for name in migrations]
    duplicates = get_duplicates(number for number, name in numbers_and_names)
    return sorted(
        (number, name)
        for number, name in numbers_and_names
        if number in duplicates
    )
