# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom test-case classes."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'LoggedInTestCase',
    'TestCase',
    'TestModelTestCase',
    ]

from maasserver.testing import reset_fake_provisioning_api_proxy
from maasserver.testing.factory import factory
import maastesting.testcase


class TestCase(maastesting.testcase.TestCase):

    def setUp(self):
        super(TestCase, self).setUp()
        self.addCleanup(reset_fake_provisioning_api_proxy)


class TestModelTestCase(TestCase, maastesting.testcase.TestModelTestCase):
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
