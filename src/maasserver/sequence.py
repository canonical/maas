# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""SQL Sequence."""

__all__ = [
    'BIGINT_MAX',
    'INT_MAX',
    'Sequence',
]

from textwrap import dedent

from django.db import (
    connection,
    transaction,
)
from provisioningserver.utils import typed


BIGINT_MAX = (2 ** 63) - 1
INT_MAX = (2 ** 32) - 1


class Sequence:
    """PostgreSQL sequence.

    This permits creating and dropping sequences in a PostgreSQL database with
    many difference options. The only limitations are that you cannot create a
    temporary sequence, nor can you specify cache parameters, but these could
    be added without difficulty.

    See http://www.postgresql.org/docs/9.4/interactive/sql-createsequence.html
    for details.
    """

    @typed
    def __init__(
            self, name: str, *, increment: int=1, minvalue: int=None,
            maxvalue: int=None, start: int=None, cycle: bool=True,
            owner: str=None):
        """Initialise a new `Sequence`.

        :param name: The name of this sequence, a valid PostgreSQL identifier.
        :param increment: The amount by which this sequence should increment.
        :param minvalue: The minimum value for this sequence.
        :param manvalue: The maximum value for this sequence.
        :param start: The starting value for this sequence.
        :param cycle: If this sequence should cycle or not.
        :param owner: The table.column that owns this sequence.
        """
        super(Sequence, self).__init__()
        self.name = name
        self.increment = increment
        self.minvalue = minvalue
        self.maxvalue = maxvalue
        self.start = start
        self.cycle = cycle
        self.owner = owner

    _sql_create = dedent("""\
        DO
        $$
        BEGIN
            CREATE SEQUENCE {name} INCREMENT BY {increment:d}
            {minvalue} {maxvalue} {start} {cycle} OWNED BY {owner};
        EXCEPTION WHEN duplicate_table THEN
            -- Do nothing, it already exists.
        END
        $$ LANGUAGE plpgsql;
    """)
    _sql_drop = (
        "DROP SEQUENCE {name}"
    )

    def create(self):
        """Create this sequence in the database if it doesn't already exist."""
        minv, maxv = self.minvalue, self.maxvalue
        statement = self._sql_create.format(
            name=self.name, increment=self.increment,
            minvalue=("NO MINVALUE" if minv is None else "MINVALUE %d" % minv),
            maxvalue=("NO MAXVALUE" if maxv is None else "MAXVALUE %d" % maxv),
            start=("" if self.start is None else "START WITH %d" % self.start),
            owner=("NONE" if self.owner is None else self.owner),
            cycle=("CYCLE" if self.cycle else "NO CYCLE"))
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(statement)

    def drop(self):
        """Drop this sequence from the database."""
        statement = self._sql_drop.format(name=self.name)
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(statement)

    def __iter__(self):
        """Return an iterator for this sequence."""
        return self

    def __next__(self):
        """Return the next value of this sequence.

        :return: The sequence value.
        :rtype: int
        """
        with connection.cursor() as cursor:
            cursor.execute("SELECT nextval(%s)", [self.name])
            return cursor.fetchone()[0]
