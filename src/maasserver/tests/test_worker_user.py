# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test for the system user that represents node-group workers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.contrib.auth.models import User
from maasserver.models import UserProfile
from maasserver.models.user import SYSTEM_USERS
from maasserver.testing.testcase import TestCase
from maasserver.worker_user import (
    get_worker_user,
    user_name,
    )


class TestNodeGroupUser(TestCase):
    """Test the special "user" that celery workers use to access the API."""

    def test_get_worker_user_always_returns_same_user(self):
        self.assertEqual(get_worker_user().id, get_worker_user().id)

    def test_get_worker_user_holds_the_worker_user(self):
        worker_user = get_worker_user()
        self.assertIsInstance(worker_user, User)
        self.assertEqual(user_name, worker_user.username)

    def test_worker_user_is_system_user(self):
        worker_user = get_worker_user()
        self.assertIn(worker_user.username, SYSTEM_USERS)
        self.assertRaises(UserProfile.DoesNotExist, worker_user.get_profile)
