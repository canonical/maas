# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""SQL Sequence."""


from textwrap import dedent

from django.db import connection, transaction, utils
from psycopg2.errorcodes import (
    DUPLICATE_TABLE,
    OBJECT_NOT_IN_PREREQUISITE_STATE,
    UNDEFINED_TABLE,
)

from maasserver.utils.orm import get_psycopg2_exception
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
        self,
        name: str,
        *,
        increment: int = 1,
        minvalue: int = None,
        maxvalue: int = None,
        start: int = None,
        cycle: bool = True,
        owner: str = None
    ):
        """Initialise a new `Sequence`.

        :param name: The name of this sequence, a valid PostgreSQL identifier.
        :param increment: The amount by which this sequence should increment.
        :param minvalue: The minimum value for this sequence.
        :param manvalue: The maximum value for this sequence.
        :param start: The starting value for this sequence.
        :param cycle: If this sequence should cycle or not.
        :param owner: The table.column that owns this sequence.
        """
        super().__init__()
        self.name = name
        self.increment = increment
        self.minvalue = minvalue
        self.maxvalue = maxvalue
        self.start = start
        self.cycle = cycle
        self.owner = owner

    _sql_create = dedent(
        """\
        CREATE SEQUENCE {name} INCREMENT BY {increment:d}
        {minvalue} {maxvalue} {start} {cycle} OWNED BY {owner};
    """
    )
    _sql_drop = "DROP SEQUENCE {name}"

    def create(self):
        """Create this sequence in the database."""
        minv, maxv = self.minvalue, self.maxvalue
        statement = self._sql_create.format(
            name=self.name,
            increment=self.increment,
            minvalue=("NO MINVALUE" if minv is None else "MINVALUE %d" % minv),
            maxvalue=("NO MAXVALUE" if maxv is None else "MAXVALUE %d" % maxv),
            start=("" if self.start is None else "START WITH %d" % self.start),
            owner=("NONE" if self.owner is None else self.owner),
            cycle=("CYCLE" if self.cycle else "NO CYCLE"),
        )
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(statement)

    def create_if_not_exists(self):
        """Create this sequence in the database.

        If it already exists, fine.
        """
        try:
            self.create()
        except utils.ProgrammingError as error:
            if is_postgres_error(error, DUPLICATE_TABLE):
                pass  # Sequence already exists.
            else:
                raise

    def drop(self):
        """Drop this sequence from the database."""
        statement = self._sql_drop.format(name=self.name)
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(statement)

    def drop_if_exists(self):
        """Drop this sequence from the database.

        If it doesn't exist, fine.
        """
        try:
            self.drop()
        except utils.ProgrammingError as error:
            if is_postgres_error(error, UNDEFINED_TABLE):
                pass  # Sequence already dropped.
            else:
                raise

    def __iter__(self):
        """Return an iterator for this sequence."""
        return self

    def __next__(self):
        """Return the next value of this sequence.

        This will create the sequence if it does not exist. This is dirty and
        nasty but it's a compromise. We can create sequences in migrations,
        but running tests with migrations is mind-bendinly slow, so we want to
        run tests outside of migrations... but Django without migrations does
        not grok sequences. So, for the sake of tests and our collective
        sanity we just create the wretched sequence.

        :return: The sequence value.
        :rtype: int
        """
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SELECT nextval(%s)", [self.name])
                    return cursor.fetchone()[0]
        except utils.ProgrammingError as error:
            if is_postgres_error(error, UNDEFINED_TABLE):
                # The sequence does not exist. For the sake of tests we'll
                # create it on the fly because: we can create sequences in
                # migrations, running tests with migrations is mind-bendinly
                # slow, but tests without migrations do not grok sequences.
                # Suppress DUPLICATE_TABLE errors from races here.
                self.create_if_not_exists()
                return next(self)
            else:
                raise

    def current(self):
        """Return the current value of this sequence, or `None`.

        :return: The sequence value, or None if there is no current value for
            the sequence in the database session or if the sequence does not
            exist.
        :rtype: int / None
        """
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SELECT currval(%s)", [self.name])
                    return cursor.fetchone()[0]
        except utils.OperationalError as error:
            if is_postgres_error(error, OBJECT_NOT_IN_PREREQUISITE_STATE):
                # There is no current value for the sequence in this session.
                return None
            else:
                raise
        except utils.ProgrammingError as error:
            if is_postgres_error(error, UNDEFINED_TABLE):
                # The sequence does not exist, hence has no current value.
                return None
            else:
                raise

    def set_value(self, next_value):
        """Restart the sequence at a specific value.

        This will cause the next value for the sequence to be the one
        specified.

        :param next_value: The value to return next.
        :return: None
        """
        statement = "ALTER SEQUENCE {name} RESTART WITH %s;"
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(statement.format(name=self.name), [next_value])


def is_postgres_error(error, *pgcodes):
    # Unwrap Django's lowest-common-denominator exception.
    error = get_psycopg2_exception(error)
    if error is None:
        # A Django error, not from the database.
        return False
    elif error.pgcode in pgcodes:
        # A matching database-side error.
        return True
    else:
        # Some other database-side error.
        return False
