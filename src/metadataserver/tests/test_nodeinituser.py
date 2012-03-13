# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model tests for metadata server."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.contrib.auth.models import User
from maasserver.models import UserProfile
from maastesting.testcase import TestCase
from metadataserver.nodeinituser import (
    get_node_init_user,
    user_name,
    )


class TestNodeInitUser(TestCase):
    """Test the special "user" that makes metadata requests from nodes."""

    def test_always_returns_same_user(self):
        node_init_user = get_node_init_user()
        self.assertEqual(node_init_user.id, get_node_init_user().id)

    def test_holds_node_init_user(self):
        user = get_node_init_user()
        self.assertIsInstance(user, User)
        self.assertEqual(user_name, user.username)

    def test_node_init_user_has_no_profile(self):
        user = get_node_init_user()
        self.assertRaises(UserProfile.DoesNotExist, user.get_profile)
