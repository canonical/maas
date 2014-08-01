# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests configuration."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from django.conf import settings
from django.db import connections
from maasserver.testing.testcase import MAASServerTestCase
from psycopg2.extensions import ISOLATION_LEVEL_SERIALIZABLE
from testtools.matchers import (
    ContainsDict,
    Equals,
    Is,
    )


class TestConfiguration(MAASServerTestCase):

    def test_transactionmiddleware(self):
        # The 'TransactionMiddleware' is not enabled (it has been
        # deprecated by the Django project).
        self.assertNotIn(
            'django.middleware.transaction.TransactionMiddleware',
            settings.MIDDLEWARE_CLASSES)

    def test_atomic_requests(self):
        # ATOMIC_REQUESTS *must* be set for the default connection.
        self.assertThat(
            connections.databases, ContainsDict({
                "default": ContainsDict({
                    "ATOMIC_REQUESTS": Is(True),
                }),
            }),
        )

    def test_isolation_level(self):
        # Transactions *must* be serialisable for the default connection.
        self.assertThat(
            connections.databases, ContainsDict({
                "default": ContainsDict({
                    "OPTIONS": ContainsDict({
                        "isolation_level": Equals(
                            ISOLATION_LEVEL_SERIALIZABLE),
                    }),
                }),
            }),
        )
