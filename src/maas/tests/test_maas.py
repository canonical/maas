# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the maas package."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import new

from django.conf import settings
from django.db import connections
from maas import (
    find_settings,
    import_settings,
)
from maastesting.djangotestcase import DjangoTestCase
from maastesting.factory import factory
from psycopg2.extensions import ISOLATION_LEVEL_REPEATABLE_READ
from testtools.matchers import (
    ContainsDict,
    Equals,
    Is,
)


class TestSettingsHelpers(DjangoTestCase):
    """Test Django settings helper functions."""

    def test_find_settings(self):
        # find_settings() returns a dict of settings from a Django-like
        # settings file. It excludes settings beginning with underscores.
        module = new.module(b"example")
        module.SETTING = factory.make_string()
        module._NOT_A_SETTING = factory.make_string()
        expected = {"SETTING": module.SETTING}
        observed = find_settings(module)
        self.assertEqual(expected, observed)

    def test_import_settings(self):
        # import_settings() copies settings from another module into the
        # caller's global scope.
        source = new.module(b"source")
        source.SETTING = factory.make_string()
        target = new.module(b"target")
        target._source = source
        target._import_settings = import_settings
        eval("_import_settings(_source)", vars(target))
        expected = {"SETTING": source.SETTING}
        observed = find_settings(target)
        self.assertEqual(expected, observed)


class TestDatabaseConfiguration(DjangoTestCase):

    def test_transactionmiddleware_is_not_used(self):
        # The 'TransactionMiddleware' is not enabled (it has been
        # deprecated by the Django project).
        self.assertNotIn(
            'django.middleware.transaction.TransactionMiddleware',
            settings.MIDDLEWARE_CLASSES)

    def test_atomic_requests_are_enabled(self):
        # ATOMIC_REQUESTS *must* be set for the default connection.
        self.assertThat(
            connections.databases, ContainsDict({
                "default": ContainsDict({
                    "ATOMIC_REQUESTS": Is(False),
                }),
            }),
        )

    def test_isolation_level_is_serializable(self):
        # Transactions *must* be SERIALIZABLE for the default connection.
        self.assertThat(
            connections.databases, ContainsDict({
                "default": ContainsDict({
                    "OPTIONS": ContainsDict({
                        "isolation_level": Equals(
                            ISOLATION_LEVEL_REPEATABLE_READ),
                    }),
                }),
            }),
        )
