# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test runner for maas and its applications."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "TestRunner",
    ]

from django.conf import settings
from django_nose import NoseTestSuiteRunner
from postgresfixture import ClusterFixture


class TestRunner(NoseTestSuiteRunner):
    """Custom test runner; ensures that the test database cluster is up."""

    def setup_databases(self, *args, **kwargs):
        """Fire up the db cluster, then punt to original implementation."""
        self.cluster = ClusterFixture("db", preserve=True)
        self.cluster.setUp()
        for database in settings.DATABASES.values():
            if database["HOST"] == self.cluster.datadir:
                self.cluster.createdb(database["NAME"])
        return super(TestRunner, self).setup_databases(*args, **kwargs)

    def teardown_databases(self, *args, **kwargs):
        super(TestRunner, self).teardown_databases(*args, **kwargs)
        self.cluster.cleanUp()
