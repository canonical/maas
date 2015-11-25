# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""SQL Sequence."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'Sequence',
    'INT_MAX',
    ]


from textwrap import dedent

from django.db import (
    connection,
    transaction,
)


BIGINT_MAX = 2 ** 63 - 1

INT_MAX = 2 ** 32 - 1


class Sequence:
    """SQL sequence."""

    def __init__(self, name, incr=1, minvalue=1, maxvalue=BIGINT_MAX):
        self.name = name
        self.incr = incr
        self.minvalue = minvalue
        self.maxvalue = maxvalue

    def create(self):
        """Create this sequence in the database if it doesn't already exist."""
        with transaction.atomic():
            cursor = connection.cursor()
            query = dedent("""\
                DO
                $$
                BEGIN
                    CREATE SEQUENCE {name}
                    INCREMENT BY %s MINVALUE %s MAXVALUE %s CYCLE;
                EXCEPTION WHEN duplicate_table THEN
                    -- do nothing, already exists
                END
                $$ LANGUAGE plpgsql;
                """).format(name=self.name)
            cursor.execute(
                query, [self.incr, self.minvalue, self.maxvalue])

    def nextval(self):
        """Return the next value of this sequence.

        :return: The sequence value.
        :rtype: int
        """
        cursor = connection.cursor()
        cursor.execute(
            "SELECT nextval(%s)", [self.name])
        return cursor.fetchone()[0]

    def drop(self):
        """Drop this sequence from the database."""
        with transaction.atomic():
            cursor = connection.cursor()
            cursor.execute(
                "DROP SEQUENCE %s" % self.name)
