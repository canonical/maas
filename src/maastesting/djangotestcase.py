# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django-enabled test cases."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'DjangoTestCase',
    'TestModelTestCase',
    'TestModelTransactionalTestCase',
    'TransactionTestCase',
    ]

from django.conf import settings
from django.core.management import call_command
from django.core.management.commands import syncdb
from django.db import (
    connections,
    DEFAULT_DB_ALIAS,
    )
from django.db.models import loading
import django.test
from maastesting.testcase import TestCase
import testtools


class DjangoTestCase(TestCase, django.test.TestCase):
    """`TestCase` for Metal as a Service.

    Supports test resources and fixtures.
    """

    def assertAttributes(self, tested_object, attributes):
        """Check multiple attributes of `tested_objects` against a dict.

        :param tested_object: Any object whose attributes should be checked.
        :param attributes: A dict of attributes to test, and their expected
            values.  Only these attributes will be checked.
        """
        matcher = testtools.matchers.MatchesStructure.byEquality(**attributes)
        self.assertThat(tested_object, matcher)


class TransactionTestCase(TestCase, django.test.TransactionTestCase):
    """`TransactionTestCase` for Metal as a Service.

    A version of TestCase that supports transactions.

    The basic Django TestCase class uses transactions to speed up tests
    so this class should be used when tests involve transactions.
    """

    def _fixture_teardown(self):
        # Force a flush of the db: this is done by
        # django.test.TransactionTestCase at the beginning of each
        # TransactionTestCase test but not at the end.  The Django test runner
        # avoids any problem by running all the TestCase tests and *then*
        # all the TransactionTestCase tests.  Since we use nose, we don't
        # have that ordering and thus we need to manually flush the db after
        # each TransactionTestCase test.  Le Sigh.
        if getattr(self, 'multi_db', False):
            databases = connections
        else:
            databases = [DEFAULT_DB_ALIAS]
        for db in databases:
            call_command('flush', verbosity=0, interactive=False, database=db)


class TestModelMixin:
    # Set the appropriate application to be loaded.
    app = None

    def _pre_setup(self):
        # Add the models to the db.
        self._original_installed_apps = list(settings.INSTALLED_APPS)
        assert self.app is not None, "TestCase.app must be defined!"
        settings.INSTALLED_APPS.append(self.app)
        loading.cache.loaded = False
        # Use Django's 'syncdb' rather than South's.
        syncdb.Command().handle_noargs(verbosity=0, interactive=False)
        super(TestModelMixin, self)._pre_setup()

    def _post_teardown(self):
        super(TestModelMixin, self)._post_teardown()
        # Restore the settings.
        settings.INSTALLED_APPS = self._original_installed_apps
        loading.cache.loaded = False


class TestModelTestCase(TestModelMixin, TestCase):
    """A custom test case that adds support for test-only models.

    For instance, if you want to have a model object used solely for testing
    in your application 'myapp1' you would create a test case that uses
    TestModelTestCase as its base class and:
    - initialize self.app with 'myapp1.tests'
    - define the models used for testing in myapp1.tests.models

    This way the models defined in myapp1.tests.models will be available in
    this test case (and this test case only).
    """


class TestModelTransactionalTestCase(TestModelMixin, TransactionTestCase):
    """A TestCase Similar to `TestModelTestCase` but with transaction
    support.
    """
