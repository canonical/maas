# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Sanity checks for database migrations.

These tests need to be included in each of the MAAS applications that has
South-managed database migrations.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.testing.db_migrations import detect_sequence_clashes
from maastesting.testcase import MAASTestCase


class TestMigrations(MAASTestCase):

    def test_migrations_have_unique_numbers(self):
        self.assertEqual([], detect_sequence_clashes('metadataserver'))
