# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django-enabled test cases."""

from time import sleep, time

from django.core.signals import request_started
from django.db import connection, connections, DEFAULT_DB_ALIAS, reset_queries
from django.http.response import HttpResponseBase
import django.test

from maastesting.djangoclient import SensibleClient
from maastesting.testcase import MAASTestCase

# Patch django.http.response.HttpResponseBase to type check that status can be
# converted to a str and then to an integer. Django converts the `status` from
# an integer to a string causing issues where status is not an integer. Any
# class that is passed to status that implements __str__ that does not equal
# the HTTP status code value will cause the wsgi application to error.
# See lp:1524883 for the issue this causes without this check.
original_HttpResponseBase__init__ = HttpResponseBase.__init__


def patched_HttpResponseBase__init__(
    self,
    content_type=None,
    status=None,
    reason=None,
    charset=None,
    headers=None,
):
    # This will raise a ValueError if this status cannot be converted to str
    # and then into integer.
    if status is not None:
        int(str(status))

    # Made it this far then the status is usable.
    original_HttpResponseBase__init__(
        self,
        content_type=content_type,
        status=status,
        reason=reason,
        charset=charset,
    )


HttpResponseBase.__init__ = patched_HttpResponseBase__init__


class CountQueries:
    """Context manager for counting database queries issued in context.

    If `reset` is true, also reset query count at enter.

    """

    def __init__(self, reset=False):
        self.reset = reset
        self.connection = connections[DEFAULT_DB_ALIAS]
        self._start_count = 0
        self._end_count = 0

    def __enter__(self):
        self.force_debug_cursor = self.connection.force_debug_cursor
        self.connection.force_debug_cursor = True
        if self.reset:
            reset_queries()
        self._start_count = self._end_count = len(self.connection.queries)
        request_started.disconnect(reset_queries)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.connection.force_debug_cursor = self.force_debug_cursor
        request_started.connect(reset_queries)
        if exc_type is not None:
            return
        self._end_count = len(self.connection.queries)

    @property
    def count(self):
        """Number of queries."""
        return self._end_count - self._start_count

    @property
    def queries(self):
        """Return the list of performed queries."""
        count = self.count
        if not count:
            return []
        return self.connection.queries[-count:]


def count_queries(func, *args, **kwargs):
    """Execute `func`, and count the number of database queries performed.

    :param func: Callable to be executed.
    :param *args: Positional arguments to `func`.
    :param **kwargs: Keyword arguments to `func`.
    :return: A tuple of: the number of queries performed while `func` was
        executing, and the value it returned.
    """
    counter = CountQueries()
    with counter:
        result = func(*args, **kwargs)
    return counter.count, result


def get_rogue_database_activity():
    """Return details of rogue database activity.

    This excludes itself, naturally, and also auto-vacuum activity which is
    governed by PostgreSQL and not something to be concerned about.

    :return: A list of dicts, where each dict represents a complete row from
        the ``pg_stat_activity`` table, mapping column names to values.
    """
    with connection.temporary_connection() as cursor:
        cursor.execute(
            """\
        SELECT * FROM pg_stat_activity
         WHERE pid != pg_backend_pid()
           AND query NOT LIKE 'autovacuum:%'
        """
        )
        names = tuple(column.name for column in cursor.description)
        return [dict(zip(names, row)) for row in cursor]


def terminate_rogue_database_activity():
    """Terminate rogue database activity.

    This excludes itself, naturally, and also auto-vacuum activity which is
    governed by PostgreSQL and not something to be concerned about.

    :return: A set of PIDs that could not be terminated, presumably because
        they're running under a different role and we're not a superuser.
    """
    with connection.temporary_connection() as cursor:
        cursor.execute(
            """\
        SELECT pid, pg_terminate_backend(pid) FROM pg_stat_activity
         WHERE pid != pg_backend_pid()
           AND query NOT LIKE 'autovacuum:%'
        """
        )
        return {pid for pid, success in cursor if not success}


def check_for_rogue_database_activity(test):
    """Check for rogue database activity and fail the test if found.

    All database activity outside of this thread should have terminated by the
    time this is called, but in practice it won't have. We have unconsciously
    lived with this situation for a long time, so we give it a few seconds to
    finish up before failing.

    This also attempts to terminate rogue activity, and reports on its success
    or failure.

    """
    cutoff = time() + 5.0  # Give it 5 seconds.
    while time() < cutoff:
        database_activity = get_rogue_database_activity()
        if len(database_activity) == 0:
            break  # All quiet on the database front.
        else:
            pause = max(0.0, min(0.2, cutoff - time()))
            sleep(pause)  # Somat's still wriggling.
    else:
        not_terminated = terminate_rogue_database_activity()
        if len(not_terminated) == 0:
            not_terminated_message = "Rogue activity successfully terminated."
        else:
            not_terminated_message = (
                "Rogue activity NOT all terminated (pids: %s)."
                % " ".join(str(pid) for pid in sorted(not_terminated))
            )
        test.fail(
            "Rogue database activity:\n--\n"
            + "\n--\n".join(
                "\n".join(
                    f"{name}={activity[name]}" for name in sorted(activity)
                )
                for activity in database_activity
            )
            + "\n--\n"
            + not_terminated_message
            + "\n"
        )


class DjangoTestCase(django.test.TestCase, MAASTestCase):
    """A Django `TestCase` for MAAS.

    Generally you should NOT directly subclass this for tests; use an
    application-specific subclass like `MAASServerTestCase`.

    Supports test resources and (non-Django) fixtures.

    :deprecated: Do NOT use in new tests.
    """

    client_class = SensibleClient

    # The database may be used in tests. See `MAASTestCase` for details.
    database_use_permitted = True

    # List of extra applications that should be added to the INSTALLED_APPS
    # for django. These applications will have syncdb performed so the models
    # exist in the database.
    apps = []

    # This attribute is used as a tag with Nose.
    legacy = True

    def _fixture_teardown(self):
        super()._fixture_teardown()
        # TODO blake_r: Fix so this is not disabled. Currently not
        # working with Django 1.8.
        # Don't let unfinished database activity get away with it.
        # check_for_rogue_database_activity(self)


class DjangoTransactionTestCase(django.test.TransactionTestCase, MAASTestCase):
    """A Django `TransactionTestCase` for MAAS.

    A version of `MAASTestCase` that supports transactions.

    Generally you should NOT directly subclass this for tests; use an
    application-specific subclass like `MAASServerTestCase`.

    The basic Django TestCase class uses transactions to speed up tests
    so this class should only be used when tests involve transactions.

    :deprecated: Do NOT use in new tests.
    """

    client_class = SensibleClient

    # The database may be used in tests. See `MAASTestCase` for details.
    database_use_permitted = True

    # List of extra applications that should be added to the INSTALLED_APPS
    # for django. These applications will have syncdb performed so the models
    # exist in the database.
    apps = []

    # This attribute is used as a tag with Nose.
    legacy = True

    def _fixture_teardown(self):
        super()._fixture_teardown()
        # TODO blake_r: Fix so this is not disabled. Currently not
        # working with Django 1.8.
        # Don't let unfinished database activity get away with it.
        # check_for_rogue_database_activity(self)
