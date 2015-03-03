# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django-enabled test cases."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'count_queries',
    'DjangoTestCase',
    'DjangoTransactionTestCase',
    'TestModelMixin',
    ]

from contextlib import closing

from django.conf import settings
from django.core.management.commands import syncdb
from django.core.signals import request_started
from django.db import (
    connection,
    connections,
    DEFAULT_DB_ALIAS,
    reset_queries,
    )
from django.db.models import loading
from django.db.utils import DatabaseError
import django.test
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
        self.old_debug_cursor = self.connection.use_debug_cursor
        self.connection.use_debug_cursor = True
        self.starting_count = len(self.connection.queries)
        request_started.disconnect(reset_queries)

    def __exit__(self, exc_type, exc_value, traceback):
        self.connection.use_debug_cursor = self.old_debug_cursor
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


class DjangoTestCase(
        MAASTestCase, django.test.TestCase):
    """A Django `TestCase` for MAAS.

    Supports test resources and (non-Django) fixtures.
    """

    def __get_connection_txid(self):
        """Get PostgreSQL's current transaction ID."""
        with closing(connection.cursor()) as cursor:
            cursor.execute("SELECT txid_current()")
            return cursor.fetchone()[0]

    def _fixture_setup(self):
        """Record the transaction ID before the test is run."""
        super(DjangoTestCase, self)._fixture_setup()
        self.__txid_before = self.__get_connection_txid()

    def _fixture_teardown(self):
        """Compare the transaction ID now to before the test ran.

        If they differ, do a full database flush because the new transaction
        could have been the result of a commit, and we don't want to leave
        stale test state around.
        """
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


class DjangoTransactionTestCase(
        MAASTestCase, django.test.TransactionTestCase):
    """A Django `TransactionTestCase` for MAAS.

    A version of `MAASTestCase` that supports transactions.

    The basic Django TestCase class uses transactions to speed up tests
    so this class should only be used when tests involve transactions.
    """


class TestModelMixin:
    """Mix-in for test cases that create their own models.

    Use this as a mix-in base class for test cases that need to create model
    classes that exist only in the scope of the tests.

    The `TestModelMixin` base class must come before the base `TestCase` class
    in the test case's list of base classes.

    :cvar app: The Django application that the test models should belong to.
        Typically either "maasserver.tests" or "metadataserver.tests".
    """
    app = None

    def _pre_setup(self):
        # Add the models to the db.
        self._original_installed_apps = settings.INSTALLED_APPS
        assert self.app is not None, "TestCase.app must be defined!"
        settings.INSTALLED_APPS = list(settings.INSTALLED_APPS)
        settings.INSTALLED_APPS.append(self.app)
        loading.cache.loaded = False
        # Use Django's 'syncdb' rather than South's.
        syncdb.Command().handle_noargs(
            verbosity=0, interactive=False, database=DEFAULT_DB_ALIAS)
        super(TestModelMixin, self)._pre_setup()

    def _post_teardown(self):
        super(TestModelMixin, self)._post_teardown()
        # Restore the settings.
        settings.INSTALLED_APPS = self._original_installed_apps
        loading.cache.loaded = False
