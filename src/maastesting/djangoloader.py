#!/usr/bin/env python
# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test loader for the Django parts of MAAS."""

from django.conf import settings
from django_nose import NoseTestSuiteRunner
from postgresfixture import ClusterFixture


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
            up = super()
            return up.setup_databases(*args, **kwargs)
        except Exception:
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
        super().teardown_databases(*args, **kwargs)
        self.cluster.cleanUp()
