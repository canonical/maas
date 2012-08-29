# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom test-case classes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'AdminLoggedInTestCase',
    'LoggedInTestCase',
    'TestCase',
    'TestModelTestCase',
    ]

from django.core.cache import cache as django_cache
from maasserver.testing.factory import factory
from maastesting.celery import CeleryFixture
import maastesting.djangotestcase
from provisioningserver.testing.worker_cache import WorkerCacheFixture


class TestCase(maastesting.djangotestcase.DjangoTestCase):
    """:class:`TestCase` variant with the basics for maasserver testing."""

    def setUp(self):
        super(TestCase, self).setUp()
        self.useFixture(WorkerCacheFixture())
        self.addCleanup(django_cache.clear)
        self.celery = self.useFixture(CeleryFixture())


class TestModelTestCase(TestCase,
                        maastesting.djangotestcase.TestModelTestCase):
    """:class:`TestCase` variant that lets you create testing models."""


class LoggedInTestCase(TestCase):
    """:class:`TestCase` variant with a logged-in web client.

    :ivar client: Django http test client, logged in for MAAS access.
    :ivar logged_in_user: User identity that `client` is authenticated for.
    """

    def setUp(self):
        super(LoggedInTestCase, self).setUp()
        self.logged_in_user = factory.make_user(password='test')
        self.client.login(
            username=self.logged_in_user.username, password='test')

    def become_admin(self):
        """Promote the logged-in user to admin."""
        self.logged_in_user.is_superuser = True
        self.logged_in_user.save()


class AdminLoggedInTestCase(LoggedInTestCase):
    """:class:`LoggedInTestCase` variant that is logged in as an admin."""

    def setUp(self):
        super(AdminLoggedInTestCase, self).setUp()
        self.become_admin()
