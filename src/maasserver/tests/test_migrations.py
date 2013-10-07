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


EXISTING_DUPES = [
    (2, '0002_add_token_to_node'),
    (2, '0002_macaddress_unique'),
    (39, '0039_add_filestorage_content'),
    (39, '0039_add_nodegroup_to_bootimage'),
    ]


class TestMigrations(MAASTestCase):

    def test_migrations_mostly_have_unique_numbers(self):
        # Apart from some duplicates that predate this test and had to
        # be grandfathered in, database migrations have unique numbers.
        self.assertEqual(
            EXISTING_DUPES,
            detect_sequence_clashes('maasserver'))
