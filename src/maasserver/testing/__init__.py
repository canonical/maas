# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""Test maasserver API."""

__metaclass__ = type
__all__ = []

from maasserver.testing.factory import factory
from maastesting import TestCase


class LoggedInTestCase(TestCase):

    def setUp(self):
        super(LoggedInTestCase, self).setUp()
        self.logged_in_user = factory.make_user(password='test')
        self.client.login(
            username=self.logged_in_user.username, password='test')
