# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities related to table row counts."""


from django.db import connection
from testtools.matchers import Annotate, Equals, GreaterThan, MatchesDict

from maastesting.matchers import GreaterThanOrEqual

# These are the expected row counts for tables in MAAS; those not mentioned
# are assumed to have zero rows.
expected_table_counts = {
    "auth_permission": GreaterThan(0),
    "auth_user": GreaterThanOrEqual(0),
    # Tests do not use migrations, but were they to do so the
    # django_content_type table would contain 10s of rows.
    "django_content_type": GreaterThan(0),
    # Tests do not use migrations; they're way too slow.
    "django_migrations": Equals(0),
    # Mystery Django stuff here. No idea what django_site does; it seems to
    # only ever contain a single row referring to "example.com".
    "django_site": Equals(1),
    # Tests do not use migrations, but were they to do so the following
    # maasserver_* tables would have one row or more each.
    "maasserver_dnspublication": Equals(0),
    "maasserver_domain": Equals(0),
    "maasserver_fabric": Equals(0),
    "maasserver_vlan": Equals(0),
    "maasserver_zone": Equals(0),
}


def check_table_row_counts(test, _last=[None]):
    """Check that all tables have expected row counts.

    This considers only tables in the database's public schema, which, for
    MAAS, means only application tables.

    :param test: An instance of :class:`testtools.TestCase`.
    """
    culprit, _last[0] = _last[0], test.id()
    observed = get_table_row_counts()
    expected = dict.fromkeys(observed, Equals(0))
    expected.update(expected_table_counts)
    test.assertThat(
        observed,
        Annotate(
            "Table counts are unexpected; most likely culprit "
            "is %s." % culprit,
            MatchesDict(expected),
        ),
    )


def get_table_row_counts():
    """Return a mapping of table names to row counts.

    For all tables in the public schema. It can do this in two queries: one to
    discover all tables, another to count all the rows therein.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables" " WHERE schemaname = 'public'"
        )
        tables = [table for table, in cursor]
        counts = map("(SELECT %s, COUNT(*) FROM {})".format, tables)
        cursor.execute(" UNION ALL ".join(counts), tables)
        return {table: count for table, count in cursor}
