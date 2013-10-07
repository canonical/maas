# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for helpers used to sanity-check South migrations."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from random import randint

from maasserver.testing import db_migrations
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase


def make_migration_name(number=None, name=None):
    """Create a migration name."""
    if number is None:
        number = randint(0, 9999)
    if name is None:
        name = factory.getRandomString()
    return '{0:=04}_{1}'.format(number, name)


class TestDBMigrations(MAASTestCase):

    def test_extract_number_returns_sequence_number(self):
        number = randint(0, 999999)
        self.assertEqual(
            number,
            db_migrations.extract_number(make_migration_name(number)))

    def test_get_duplicates_finds_duplicates(self):
        item = factory.make_name('item')
        self.assertEqual({item}, db_migrations.get_duplicates([item, item]))

    def test_get_duplicates_finds_all_duplicates(self):
        dup1 = factory.make_name('dup1')
        dup2 = factory.make_name('dup2')
        self.assertEqual(
            {dup1, dup2},
            db_migrations.get_duplicates(2 * [dup1, dup2]))

    def test_get_duplicates_ignores_unique_items(self):
        self.assertEqual(set(), db_migrations.get_duplicates(range(5)))

    def test_get_duplicates_ignores_ordering(self):
        dup = factory.make_name('dup')
        unique = factory.make_name('unique')
        self.assertEqual(
            {dup},
            db_migrations.get_duplicates([dup, unique, dup]))

    def test_list_migrations_lists_real_migrations(self):
        self.assertIn(
            '0001_initial',
            db_migrations.list_migrations('maasserver'))

    def test_detect_sequence_clashes_returns_list(self):
        self.assertIsInstance(
            db_migrations.detect_sequence_clashes('maasserver'),
            list)

    def test_detect_sequence_clashes_finds_clashes(self):
        number = randint(0, 999)
        names = tuple(make_migration_name(number) for counter in range(2))
        self.patch(db_migrations, 'list_migrations').return_value = names
        self.assertItemsEqual(
            [(number, name) for name in names],
            db_migrations.detect_sequence_clashes(factory.make_name('app')))

    def test_detect_sequence_clashes_ignores_unique_migrations(self):
        self.patch(db_migrations, 'list_migrations').return_value = tuple(
            make_migration_name(number)
            for number in range(5))
        self.assertItemsEqual(
            [],
            db_migrations.detect_sequence_clashes(factory.make_name('app')))
