# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the UserProfile model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.contrib.auth.models import User
from maasserver.exceptions import CannotDeleteUserException
from maasserver.models import UserProfile
from maasserver.models.user import (
    GENERIC_CONSUMER,
    get_auth_tokens,
    SYSTEM_USERS,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from piston.models import (
    Consumer,
    Token,
    )


class UserProfileTest(TestCase):

    def test_profile_creation(self):
        # A profile is created each time a user is created.
        user = factory.make_user()
        self.assertIsInstance(user.get_profile(), UserProfile)
        self.assertEqual(user, user.get_profile().user)

    def test_consumer_creation(self):
        # A generic consumer is created each time a user is created.
        user = factory.make_user()
        consumers = Consumer.objects.filter(user=user, name=GENERIC_CONSUMER)
        self.assertEqual([user], [consumer.user for consumer in consumers])

    def test_token_creation(self):
        # A token is created each time a user is created.
        user = factory.make_user()
        [token] = get_auth_tokens(user)
        self.assertEqual(user, token.user)

    def test_create_authorisation_token(self):
        # UserProfile.create_authorisation_token calls create_auth_token.
        user = factory.make_user()
        profile = user.get_profile()
        consumer, token = profile.create_authorisation_token()
        self.assertEqual(user, token.user)
        self.assertEqual(user, consumer.user)

    def test_get_authorisation_tokens(self):
        # UserProfile.get_authorisation_tokens calls get_auth_tokens.
        user = factory.make_user()
        consumer, token = user.get_profile().create_authorisation_token()
        self.assertIn(token, user.get_profile().get_authorisation_tokens())

    def test_delete(self):
        # Deleting a profile also deletes the related user.
        profile = factory.make_user().get_profile()
        profile_id = profile.id
        user_id = profile.user.id
        self.assertTrue(User.objects.filter(id=user_id).exists())
        self.assertTrue(
            UserProfile.objects.filter(id=profile_id).exists())
        profile.delete()
        self.assertFalse(User.objects.filter(id=user_id).exists())
        self.assertFalse(
            UserProfile.objects.filter(id=profile_id).exists())

    def test_delete_consumers_tokens(self):
        # Deleting a profile deletes the related tokens and consumers.
        profile = factory.make_user().get_profile()
        token_ids = []
        consumer_ids = []
        for i in range(3):
            token, consumer = profile.create_authorisation_token()
            token_ids.append(token.id)
            consumer_ids.append(consumer.id)
        profile.delete()
        self.assertFalse(Consumer.objects.filter(id__in=consumer_ids).exists())
        self.assertFalse(Token.objects.filter(id__in=token_ids).exists())

    def test_delete_attached_nodes(self):
        # Cannot delete a user with nodes attached to it.
        profile = factory.make_user().get_profile()
        factory.make_node(owner=profile.user)
        self.assertRaises(CannotDeleteUserException, profile.delete)

    def test_manager_all_users(self):
        users = set(factory.make_user() for i in range(3))
        all_users = set(UserProfile.objects.all_users())
        self.assertEqual(users, all_users)

    def test_manager_all_users_no_system_user(self):
        for i in range(3):
            factory.make_user()
        usernames = set(
            user.username for user in UserProfile.objects.all_users())
        self.assertTrue(set(SYSTEM_USERS).isdisjoint(usernames))
