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
from provisioningserver.cache import cache as pserv_cache


class TestCase(maastesting.djangotestcase.DjangoTestCase):

    def setUp(self):
        super(TestCase, self).setUp()
        self.addCleanup(django_cache.clear)
        self.addCleanup(pserv_cache.clear)
        self.celery = self.useFixture(CeleryFixture())


class TestModelTestCase(TestCase,
                        maastesting.djangotestcase.TestModelTestCase):
    pass


class LoggedInTestCase(TestCase):

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

    def setUp(self):
        super(AdminLoggedInTestCase, self).setUp()
        self.become_admin()
