#!/usr/bin/env python
# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test loader for the Django parts of MAAS."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "MAASDjangoTestRunner",
    "MAASDjangoTestSuite",
    "MAASDjangoTestLoader",
]

import threading
import unittest

from django.conf import settings
from django.test.simple import DjangoTestSuiteRunner
from django_nose import NoseTestSuiteRunner
from maastesting.loader import MAASTestLoader
from postgresfixture import ClusterFixture
import south.management.commands
from testtools import try_imports


reorder_suite = try_imports((
    "django.test.simple.reorder_suite",
    "django.test.runner.reorder_suite",
))


class MAASDjangoTestRunner(NoseTestSuiteRunner):
    """Custom test runner; ensures that the test database cluster is up."""

    def setup_databases(self, *args, **kwargs):
        """Fire up the db cluster, then punt to original implementation."""
        self.cluster = ClusterFixture("db", preserve=True)
        self.cluster.setUp()
        try:
            # Create a database in the PostgreSQL cluster for each database
            # connection configured in Django's settings that points to the
            # same datadir.
            for database in settings.DATABASES.values():
                if database["HOST"] == self.cluster.datadir:
                    self.cluster.createdb(database["NAME"])
            # Call-up to super-classes.
            up = super(MAASDjangoTestRunner, self)
            return up.setup_databases(*args, **kwargs)
        except:
            # Clean-up the cluster now, or it'll be left running; django-nose
            # does not know to clean it up itself, and lacks a fixture-like
            # mechanism to aid with reverting a half-configured environment.
            self.cluster.cleanUp()
            # Now we can let the original error wreak havoc.
            raise

    def teardown_databases(self, *args, **kwargs):
        """Tear-down the test database cluster.

        This is *not* called if there's a failure during bring-up of any of
        the test databases, hence there is also tear-down code embedded in
        `setup_databases`.
        """
        super(MAASDjangoTestRunner, self).teardown_databases(*args, **kwargs)
        self.cluster.cleanUp()


class MAASDjangoTestSuite(unittest.TestSuite):
    """A MAAS and Django-specific test suite.

    This ensures that PostgreSQL clusters are up and running, and calls
    into Django's test framework to ensure that fixtures and so forth
    are all in place.
    """

    # This lock guards against concurrent invocations of run_outer();
    # only the outermost suite should call run_outer(), all the others
    # should call up to the superclass's run() method.
    outer_lock = threading.Lock()

    def run_outer(self, result, debug=False):
        # This is how South ensures that migrations are run during test
        # setup. For real. This is not a joke.
        south.management.commands.patch_for_test_db_setup()
        # We create one of Django's runners for set-up and tear-down
        # methods; it's not used to run the tests.
        runner = DjangoTestSuiteRunner(verbosity=2, interactive=False)
        runner.setup_test_environment()
        try:
            with ClusterFixture("db", preserve=True) as cluster:
                # Create a database in the PostgreSQL cluster for each
                # database connection configured in Django's settings that
                # points to the same datadir.
                for database in settings.DATABASES.values():
                    if database["HOST"] == cluster.datadir:
                        cluster.createdb(database["NAME"])
                old_config = runner.setup_databases()
                try:
                    return super(MAASDjangoTestSuite, self).run(result, debug)
                finally:
                    runner.teardown_databases(old_config)
        finally:
            runner.teardown_test_environment()

    def run(self, result, debug=False):
        # `False` means don't block when acquiring the lock, and implies
        # that run_outer() is already being invoked. We must call up to
        # the superclass's run() instead.
        if self.outer_lock.acquire(False):
            try:
                self.run_outer(result, debug)
            finally:
                self.outer_lock.release()
        else:
            super(MAASDjangoTestSuite, self).run(result, debug)


class MAASDjangoTestLoader(MAASTestLoader):
    """A MAAS and Django-specific test loader.

    See `maastesting.loader.MAASTestLoader`.

    This also reorders the test suite, which is something that Django's
    test framework does. The purpose of this behaviour is not
    understood, but we reproduce it here anyway.
    """

    suiteClass = MAASDjangoTestSuite

    def loadTestsFromName(self, name, module=None):
        suite = super(MAASDjangoTestLoader, self).loadTestsFromName(name)
        return reorder_suite(suite, (unittest.TestCase,))
