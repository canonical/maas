# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django-enabled test cases."""

__all__ = [
    'count_queries',
    'DjangoTestCase',
    'DjangoTransactionTestCase',
    ]

from contextlib import closing
from time import (
    sleep,
    time,
)

from django.apps import apps as django_apps
from django.core.management import call_command
from django.core.signals import request_started
from django.db import (
    connection,
    connections,
    DEFAULT_DB_ALIAS,
    reset_queries,
)
from django.db.utils import DatabaseError
import django.test
from maastesting.djangoclient import SensibleClient
from maastesting.testcase import MAASTestCase


class CountQueries:
    """Context manager: count number of database queries issued in context.

    :ivar num_queries: The number of database queries that were performed while
        this context was active.
    """

    def __init__(self):
        self.connection = connections[DEFAULT_DB_ALIAS]
        self.num_queries = 0

    def __enter__(self):
        self.force_debug_cursor = self.connection.force_debug_cursor
        self.connection.force_debug_cursor = True
        self.starting_count = len(self.connection.queries)
        request_started.disconnect(reset_queries)

    def __exit__(self, exc_type, exc_value, traceback):
        self.connection.force_debug_cursor = self.force_debug_cursor
        request_started.connect(reset_queries)
        if exc_type is not None:
            return
        final_count = len(self.connection.queries)
        self.num_queries = final_count - self.starting_count


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
    return counter.num_queries, result


def get_rogue_database_activity():
    """Return details of rogue database activity.

    This excludes itself, naturally, and also auto-vacuum activity which is
    governed by PostgreSQL and not something to be concerned about.

    :return: A list of dicts, where each dict represents a complete row from
        the ``pg_stat_activity`` table, mapping column names to values.
    """
    with connection.temporary_connection() as cursor:
        cursor.execute("""\
        SELECT * FROM pg_stat_activity
         WHERE pid != pg_backend_pid()
           AND query NOT LIKE 'autovacuum:%'
        """)
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
        cursor.execute("""\
        SELECT pid, pg_terminate_backend(pid) FROM pg_stat_activity
         WHERE pid != pg_backend_pid()
           AND query NOT LIKE 'autovacuum:%'
        """)
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
            not_terminated_message = (
                "Rogue activity successfully terminated.")
        else:
            not_terminated_message = (
                "Rogue activity NOT all terminated (pids: %s)." % " ".join(
                    str(pid) for pid in sorted(not_terminated)))
        test.fail(
            "Rogue database activity:\n--\n" + "\n--\n".join(
                "\n".join(
                    "%s=%s" % (name, activity[name])
                    for name in sorted(activity)
                )
                for activity in database_activity
            ) + "\n--\n" + not_terminated_message + "\n"
        )


class InstallDjangoAppsMixin:
    """Mixin provides the ability to install extra applications into the
    Djanog INSTALLED_APPS setting."""

    def _setup_apps(self, apps):
        self._did_set_apps = False
        if len(apps) > 0:
            # Inject the apps into django now that the fixture is setup.
            self._did_set_apps = True
            current_apps = [
                current_app.name
                for current_app in django_apps.get_app_configs()
            ]
            need_to_add = [
                new_app
                for new_app in apps
                if new_app not in current_apps
            ]
            for app in need_to_add:
                current_apps.append(app)
            # Set the installed applications in django. This requires another
            # call to unset_installed_apps to reset to the previous value.
            django_apps.set_installed_apps(current_apps)
            # Call migrate that will actual perform the migrations for this
            # applications and if no migrations exists then it will fallback
            # to performing 'syncdb'.
            call_command("migrate")

    def _teardown_apps(self):
        # Check that the internal __set_apps is set so that the required
        # unset_installed_apps can be called.
        if self._did_set_apps:
            django_apps.unset_installed_apps()


class DjangoTestCase(
        django.test.TestCase, MAASTestCase, InstallDjangoAppsMixin):
    """A Django `TestCase` for MAAS.

    Supports test resources and (non-Django) fixtures.
    """

    client_class = SensibleClient

    # The database may be used in tests. See `MAASTestCase` for details.
    database_use_permitted = True

    # List of extra applications that should be added to the INSTALLED_APPS
    # for django. These applications will have syncdb performed so the models
    # exist in the database.
    apps = []

    def __get_connection_txid(self):
        """Get PostgreSQL's current transaction ID."""
        with closing(connection.cursor()) as cursor:
            cursor.execute("SELECT txid_current()")
            return cursor.fetchone()[0]

    def _fixture_setup(self):
        """Record the transaction ID before the test is run."""
        super(DjangoTestCase, self)._fixture_setup()
        self._setup_apps(self.apps)
        self.__txid_before = self.__get_connection_txid()

    def _fixture_teardown(self):
        """Compare the transaction ID now to before the test ran.

        If they differ, do a full database flush because the new transaction
        could have been the result of a commit, and we don't want to leave
        stale test state around.
        """
        self._teardown_apps()
        try:
            self.__txid_after = self.__get_connection_txid()
        except DatabaseError:
            # We don't know if a transaction was committed to disk or if the
            # transaction simply broke, so assume the worse and flush all
            # databases.
            super(DjangoTestCase, self)._fixture_teardown()
            django.test.TransactionTestCase._fixture_teardown(self)
        else:
            super(DjangoTestCase, self)._fixture_teardown()
            if self.__txid_after != self.__txid_before:
                # We're in a different transaction now to the one we started
                # in, so force a flush of all databases to ensure all's well.
                django.test.TransactionTestCase._fixture_teardown(self)
        # TODO blake_r: Fix so this is not disabled. Currently not
        # working with Django 1.8.
        # Don't let unfinished database activity get away with it.
        # check_for_rogue_database_activity(self)


class DjangoTransactionTestCase(
        django.test.TransactionTestCase, MAASTestCase, InstallDjangoAppsMixin):
    """A Django `TransactionTestCase` for MAAS.

    A version of `MAASTestCase` that supports transactions.

    The basic Django TestCase class uses transactions to speed up tests
    so this class should only be used when tests involve transactions.
    """

    client_class = SensibleClient

    # The database may be used in tests. See `MAASTestCase` for details.
    database_use_permitted = True

    # List of extra applications that should be added to the INSTALLED_APPS
    # for django. These applications will have syncdb performed so the models
    # exist in the database.
    apps = []

    def _fixture_setup(self):
        super(DjangoTransactionTestCase, self)._fixture_setup()
        self._setup_apps(self.apps)

    def _fixture_teardown(self):
        self._teardown_apps()
        super(DjangoTransactionTestCase, self)._fixture_teardown()
        # TODO blake_r: Fix so this is not disabled. Currently not
        # working with Django 1.8.
        # Don't let unfinished database activity get away with it.
        # check_for_rogue_database_activity(self)
